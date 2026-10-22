from rest_framework import mixins, permissions, viewsets

from apps.tasks.mixins import TaskScopedMixin

from .models import ActivityLog
from .serializers import ActivitySerializer


class ActivityViewSet(TaskScopedMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read-only history of a task, newest first."""

    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ActivityLog.objects.none()
        return ActivityLog.objects.filter(task=self.task).select_related("actor")
