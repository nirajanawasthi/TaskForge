from rest_framework import mixins, permissions, viewsets

from apps.projects.mixins import ProjectScopedMixin

from .models import Task
from .permissions import CanManageTasks
from .serializers import TaskSerializer
from .services import create_task, update_task


class TaskViewSet(
    ProjectScopedMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageTasks]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Task.objects.none()
        return Task.objects.filter(project=self.project).select_related(
            "assignee", "created_by"
        )

    def perform_create(self, serializer):
        serializer.instance = create_task(
            project=self.project,
            user=self.request.user,
            **serializer.validated_data,
        )

    def perform_update(self, serializer):
        serializer.instance = update_task(
            task=serializer.instance, **serializer.validated_data
        )
