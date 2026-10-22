from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.activity_logs.models import ActivityLog
from apps.activity_logs.services import log_activity
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.projects.models import ProjectMember

from .models import Task

UNSET = object()


def _text(value):
    """Turn a field value into something JSON can store."""
    return value.isoformat() if hasattr(value, "isoformat") else value


def _email(user):
    return user.email if user else None


def _notify_assigned(task, actor, assignee):
    notify(
        task=task,
        actor=actor,
        recipients=[assignee],
        kind=Notification.Kind.TASK_ASSIGNED,
        message=f'{actor.email} assigned you "{task.title}"',
    )


def _resolve_assignee(project, email):
    """Return the project member's user for this email, or None to unassign."""
    if email is None:
        return None
    project_member = (
        ProjectMember.objects.select_related("user")
        .filter(project=project, user__email__iexact=email.strip())
        .first()
    )
    if project_member is None:
        raise ValidationError(
            {"assignee_email": "The assignee must be a member of this project."}
        )
    return project_member.user


@transaction.atomic
def create_task(*, project, user, assignee_email=None, **fields):
    assignee = _resolve_assignee(project, assignee_email)
    task = Task.objects.create(
        project=project, created_by=user, assignee=assignee, **fields
    )
    log_activity(
        task=task,
        actor=user,
        action=ActivityLog.Action.TASK_CREATED,
        details={"title": task.title, "assignee": _email(assignee)},
    )
    if assignee:
        _notify_assigned(task, user, assignee)
    return task


@transaction.atomic
def update_task(*, task, user, assignee_email=UNSET, **fields):
    changes = {}
    for name, value in fields.items():
        old = getattr(task, name)
        if old != value:
            changes[name] = {"from": _text(old), "to": _text(value)}
            setattr(task, name, value)

    assignee_change = None
    new_assignee = None
    if assignee_email is not UNSET:
        new_assignee = _resolve_assignee(task.project, assignee_email)
        if getattr(new_assignee, "pk", None) != task.assignee_id:
            assignee_change = {
                "from": _email(task.assignee),
                "to": _email(new_assignee),
            }
            task.assignee = new_assignee

    if changes or assignee_change:
        task.save()
    if changes:
        log_activity(
            task=task,
            actor=user,
            action=ActivityLog.Action.TASK_UPDATED,
            details={"changes": changes},
        )
    if assignee_change:
        log_activity(
            task=task,
            actor=user,
            action=ActivityLog.Action.ASSIGNEE_CHANGED,
            details=assignee_change,
        )
        if new_assignee:
            _notify_assigned(task, user, new_assignee)
    return task
