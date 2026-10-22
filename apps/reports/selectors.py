from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.projects.selectors import visible_projects
from apps.tasks.models import Task
from apps.tasks.permissions import TASK_WRITE_ROLES

S = Task.Status
P = Task.Priority
DUE_SOON_DAYS = 7


def visible_tasks(*, user, membership):
    """Tasks in projects the user may see. Everything in reports starts here."""
    projects = visible_projects(user=user, membership=membership)
    return Task.objects.filter(project__in=projects.values("pk"))


def overdue_tasks(*, user, membership):
    """Visible tasks whose due date has passed and that are not done."""
    return (
        visible_tasks(user=user, membership=membership)
        .filter(due_date__lt=timezone.localdate())
        .exclude(status=S.DONE)
    )


def dashboard_stats(*, user, membership):
    today = timezone.localdate()
    tasks = visible_tasks(user=user, membership=membership)

    is_open = ~Q(status=S.DONE)
    is_overdue = Q(due_date__lt=today) & is_open
    is_due_soon = (
        Q(due_date__gte=today, due_date__lte=today + timedelta(days=DUE_SOON_DAYS))
        & is_open
    )

    totals = tasks.aggregate(
        total=Count("id"),
        todo=Count("id", filter=Q(status=S.TODO)),
        in_progress=Count("id", filter=Q(status=S.IN_PROGRESS)),
        in_review=Count("id", filter=Q(status=S.IN_REVIEW)),
        done=Count("id", filter=Q(status=S.DONE)),
        overdue=Count("id", filter=is_overdue),
        due_soon=Count("id", filter=is_due_soon),
        unassigned=Count("id", filter=Q(assignee__isnull=True) & is_open),
        low=Count("id", filter=is_open & Q(priority=P.LOW)),
        medium=Count("id", filter=is_open & Q(priority=P.MEDIUM)),
        high=Count("id", filter=is_open & Q(priority=P.HIGH)),
        urgent=Count("id", filter=is_open & Q(priority=P.URGENT)),
        mine_open=Count("id", filter=Q(assignee=user) & is_open),
        mine_overdue=Count("id", filter=Q(assignee=user) & is_overdue),
    )
    total = totals["total"]
    completion_rate = round(totals["done"] / total * 100, 1) if total else 0.0

    stats = {
        "projects": visible_projects(user=user, membership=membership).count(),
        "tasks": {
            "total": total,
            "by_status": {
                "todo": totals["todo"],
                "in_progress": totals["in_progress"],
                "in_review": totals["in_review"],
                "done": totals["done"],
            },
            "overdue": totals["overdue"],
            "due_soon": totals["due_soon"],
            "unassigned": totals["unassigned"],
            "completion_rate": completion_rate,
        },
        "open_by_priority": {
            "low": totals["low"],
            "medium": totals["medium"],
            "high": totals["high"],
            "urgent": totals["urgent"],
        },
        "my_tasks": {
            "open": totals["mine_open"],
            "overdue": totals["mine_overdue"],
        },
    }

    # Who is carrying how much: visible to leads and above only.
    if membership.role in TASK_WRITE_ROLES:
        rows = (
            tasks.filter(assignee__isnull=False)
            .values("assignee__email")
            .annotate(
                open=Count("id", filter=is_open),
                overdue=Count("id", filter=is_overdue),
                done=Count("id", filter=Q(status=S.DONE)),
            )
            .order_by("assignee__email")
        )
        stats["workload"] = [
            {
                "email": row["assignee__email"],
                "open": row["open"],
                "overdue": row["overdue"],
                "done": row["done"],
            }
            for row in rows
        ]
    return stats
