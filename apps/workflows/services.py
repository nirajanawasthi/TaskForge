from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.activity_logs.models import ActivityLog
from apps.activity_logs.services import log_activity
from apps.tasks.models import Task
from apps.tasks.permissions import TASK_WRITE_ROLES

Status = Task.Status

TRANSITIONS = {
    "start": {"from": Status.TODO, "to": Status.IN_PROGRESS},
    "submit_for_review": {"from": Status.IN_PROGRESS, "to": Status.IN_REVIEW},
    "approve": {"from": Status.IN_REVIEW, "to": Status.DONE},
    "request_changes": {"from": Status.IN_REVIEW, "to": Status.IN_PROGRESS},
    "reopen": {"from": Status.DONE, "to": Status.IN_PROGRESS},
}


def _is_allowed(action, *, user, role, task):
    is_assignee = task.assignee_id == user.id
    is_lead = role in TASK_WRITE_ROLES
    if action in ("start", "submit_for_review"):
        return is_assignee or is_lead
    if action in ("approve", "request_changes"):
        # Nobody reviews their own work, whatever their role.
        return is_lead and not is_assignee
    if action == "reopen":
        return is_lead
    return False


@transaction.atomic
def apply_transition(*, task, user, role, action):
    """Move a task along the workflow. The only way a task's status changes."""
    # Lock the row so two simultaneous transitions cannot both succeed.
    task = Task.objects.select_for_update().get(pk=task.pk)
    rule = TRANSITIONS[action]

    if not _is_allowed(action, user=user, role=role, task=task):
        raise PermissionDenied("You are not allowed to do this on this task.")
    if task.status != rule["from"]:
        raise ValidationError(
            {"action": f"Cannot {action} a task that is {task.get_status_display()}."}
        )
    if action == "start" and task.assignee_id is None:
        raise ValidationError({"action": "Assign the task before starting it."})

    old_status = task.status
    task.status = rule["to"]
    task.save(update_fields=["status", "updated_at"])
    log_activity(
        task=task,
        actor=user,
        action=ActivityLog.Action.STATUS_CHANGED,
        details={"action": action, "from": old_status, "to": rule["to"].value},
    )
    return task
