from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property

from apps.projects.mixins import ProjectScopedMixin

from .models import Task


class TaskScopedMixin(ProjectScopedMixin):
    """Resolve the URL's task, only if its project is visible to the caller."""

    @cached_property
    def task(self):
        return get_object_or_404(
            Task.objects.filter(project=self.project), pk=self.kwargs["task_pk"]
        )

    def ensure_visible(self):
        self.task
