from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import NotificationFilter
from .models import Notification
from .serializers import (
    MarkedSerializer,
    NotificationSerializer,
    UnreadCountSerializer,
)
from .services import mark_all_read, mark_read


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """The caller's own notifications. Other people's ids answer 404."""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = NotificationFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(
            recipient=self.request.user
        ).select_related("task__project")

    @extend_schema(responses=UnreadCountSerializer)
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        unread = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({"unread": unread})

    @extend_schema(request=None, responses=MarkedSerializer)
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        return Response({"marked": mark_all_read(request.user)})

    @extend_schema(request=None, responses=NotificationSerializer)
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = mark_read(self.get_object())
        return Response(self.get_serializer(notification).data)
