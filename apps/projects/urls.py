from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import ProjectMemberViewSet, ProjectViewSet

app_name = "projects"

member_list = ProjectMemberViewSet.as_view({"get": "list", "post": "create"})
member_detail = ProjectMemberViewSet.as_view({"delete": "destroy"})

router = SimpleRouter()
router.register("", ProjectViewSet, basename="project")

urlpatterns = [
    path("<int:project_pk>/members/", member_list, name="project-member-list"),
    path(
        "<int:project_pk>/members/<int:pk>/",
        member_detail,
        name="project-member-detail",
    ),
] + router.urls
