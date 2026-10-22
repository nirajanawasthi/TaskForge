from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import MembershipViewSet, OrganizationViewSet

app_name = "organizations"

membership_list = MembershipViewSet.as_view({"get": "list", "post": "create"})
membership_detail = MembershipViewSet.as_view(
    {"patch": "partial_update", "delete": "destroy"}
)

router = SimpleRouter()
router.register("", OrganizationViewSet, basename="organization")

urlpatterns = [
    path("<int:organization_pk>/members/", membership_list, name="membership-list"),
    path(
        "<int:organization_pk>/members/<int:pk>/",
        membership_detail,
        name="membership-detail",
    ),
] + router.urls
