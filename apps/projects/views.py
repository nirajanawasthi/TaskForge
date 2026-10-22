from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from .mixins import OrganizationScopedMixin, ProjectScopedMixin
from .models import Project, ProjectMember
from .permissions import CanManageProjects
from .selectors import visible_projects
from .serializers import (
    AddProjectMemberSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
)
from .services import add_project_member, create_project


class ProjectViewSet(
    OrganizationScopedMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageProjects]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Project.objects.none()
        return visible_projects(
            user=self.request.user, membership=self.requesting_membership
        ).select_related("created_by")

    def ensure_visible(self):
        super().ensure_visible()
        if "pk" in self.kwargs:
            get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def perform_create(self, serializer):
        serializer.instance = create_project(
            organization=self.requesting_membership.organization,
            user=self.request.user,
            **serializer.validated_data,
        )


class ProjectMemberViewSet(
    ProjectScopedMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ProjectMemberSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageProjects]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ProjectMember.objects.none()
        return (
            ProjectMember.objects.filter(project=self.project)
            .select_related("user")
            .order_by("joined_at", "id")
        )

    @extend_schema(
        request=AddProjectMemberSerializer, responses={201: ProjectMemberSerializer}
    )
    def create(self, request, *args, **kwargs):
        serializer = AddProjectMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project_member = add_project_member(
            project=self.project, email=serializer.validated_data["email"]
        )
        return Response(
            ProjectMemberSerializer(project_member).data,
            status=status.HTTP_201_CREATED,
        )
