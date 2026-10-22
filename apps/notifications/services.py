from django.utils import timezone

from apps.organizations.models import Membership
from apps.projects.selectors import visible_projects

from .models import Notification


def _may_see(user, task):
    """True if the user can currently see the task's project."""
    membership = Membership.objects.filter(
        organization_id=task.project.organization_id, user=user
    ).first()
    if membership is None:
        return False
    return (
        visible_projects(user=user, membership=membership)
        .filter(pk=task.project_id)
        .exists()
    )


def notify(*, task, actor, recipients, kind, message):
    """Notify each recipient once, never the actor, never someone who cannot see the task."""
    seen = set()
    notifications = []
    for user in recipients:
        if user is None or user.pk == actor.pk or user.pk in seen:
            continue
        seen.add(user.pk)
        if not _may_see(user, task):
            continue
        notifications.append(
            Notification(recipient=user, task=task, kind=kind, message=message)
        )
    Notification.objects.bulk_create(notifications)
    return notifications


def mark_read(notification):
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
    return notification


def mark_all_read(user):
    return Notification.objects.filter(recipient=user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
