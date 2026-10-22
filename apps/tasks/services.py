from rest_framework.exceptions import ValidationError

from apps.projects.models import ProjectMember

from .models import Task

UNSET = object()


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


def create_task(*, project, user, assignee_email=None, **fields):
    assignee = _resolve_assignee(project, assignee_email)
    return Task.objects.create(
        project=project, created_by=user, assignee=assignee, **fields
    )


def update_task(*, task, assignee_email=UNSET, **fields):
    if assignee_email is not UNSET:
        task.assignee = _resolve_assignee(task.project, assignee_email)
    for name, value in fields.items():
        setattr(task, name, value)
    task.save()
    return task
