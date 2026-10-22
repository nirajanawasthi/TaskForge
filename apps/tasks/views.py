from django.db.models import Case, IntegerField, When
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, permissions, viewsets
from rest_framework.filters import SearchFilter

from apps.projects.mixins import ProjectScopedMixin

from .filters import TaskFilter
from .models import Task
from .permissions import CanManageTasks
from .serializers import TaskSerializer
from .services import create_task, update_task

# Priority sorts by importance (low < medium < high < urgent), not alphabetically.
PRIORITY_RANK = Case(
    When(priority=Task.Priority.LOW, then=1),
    When(priority=Task.Priority.MEDIUM, then=2),
    When(priority=Task.Priority.HIGH, then=3),
    When(priority=Task.Priority.URGENT, then=4),
    default=0,
    output_field=IntegerField(),
)


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
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = TaskFilter
    search_fields = ["title", "description"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Task.objects.none()
        return (
            Task.objects.filter(project=self.project)
            .select_related("assignee", "created_by")
            .annotate(priority_rank=PRIORITY_RANK)
        )

    def perform_create(self, serializer):
        serializer.instance = create_task(
            project=self.project,
            user=self.request.user,
            **serializer.validated_data,
        )

    def perform_update(self, serializer):
        serializer.instance = update_task(
            task=serializer.instance,
            user=self.request.user,
            **serializer.validated_data,
        )
