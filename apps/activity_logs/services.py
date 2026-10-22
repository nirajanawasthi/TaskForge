from .models import ActivityLog


def log_activity(*, task, actor, action, details=None):
    return ActivityLog.objects.create(
        task=task, actor=actor, action=action, details=details or {}
    )
