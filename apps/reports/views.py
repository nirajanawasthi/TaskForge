from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.mixins import OrganizationScopedMixin
from apps.tasks.models import Task

from .filters import OverdueFilter
from .selectors import dashboard_stats, overdue_tasks
from .serializers import DashboardSerializer, OverdueTaskSerializer


class DashboardView(OrganizationScopedMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=DashboardSerializer)
    def get(self, request, *args, **kwargs):
        stats = dashboard_stats(
            user=request.user, membership=self.requesting_membership
        )
        return Response(stats)


class OverdueReportView(OrganizationScopedMixin, generics.ListAPIView):
    serializer_class = OverdueTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = OverdueFilter

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Task.objects.none()
        return (
            overdue_tasks(user=self.request.user, membership=self.requesting_membership)
            .select_related("project", "assignee")
            .order_by("due_date", "id")
        )
