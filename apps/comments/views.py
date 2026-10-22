from rest_framework import mixins, permissions, viewsets

from apps.tasks.mixins import TaskScopedMixin

from .models import Comment
from .permissions import IsAuthorOrReadOnly
from .serializers import CommentSerializer
from .services import add_comment


class CommentViewSet(
    TaskScopedMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Comment.objects.none()
        return Comment.objects.filter(task=self.task).select_related("author")

    def perform_create(self, serializer):
        serializer.instance = add_comment(
            task=self.task,
            author=self.request.user,
            **serializer.validated_data,
        )
