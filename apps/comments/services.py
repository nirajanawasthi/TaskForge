from django.db import transaction

from apps.activity_logs.models import ActivityLog
from apps.activity_logs.services import log_activity
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import Comment


@transaction.atomic
def add_comment(*, task, author, body):
    comment = Comment.objects.create(task=task, author=author, body=body)
    log_activity(
        task=task,
        actor=author,
        action=ActivityLog.Action.COMMENT_ADDED,
        details={"comment_id": comment.pk},
    )
    notify(
        task=task,
        actor=author,
        recipients=[task.assignee, task.created_by],
        kind=Notification.Kind.COMMENT_ADDED,
        message=f'{author.email} commented on "{task.title}"',
    )
    return comment
