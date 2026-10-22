from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """Append-only record of what happened to a task. Never edited through the API."""

    class Action(models.TextChoices):
        TASK_CREATED = "task_created", "Task created"
        TASK_UPDATED = "task_updated", "Task updated"
        ASSIGNEE_CHANGED = "assignee_changed", "Assignee changed"
        STATUS_CHANGED = "status_changed", "Status changed"
        COMMENT_ADDED = "comment_added", "Comment added"

    task = models.ForeignKey(
        "tasks.Task", on_delete=models.CASCADE, related_name="activity"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="activity",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["task", "-created_at"])]

    def __str__(self):
        return f"{self.action} on task {self.task_id}"
