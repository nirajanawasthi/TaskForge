from django.db.models import OuterRef, Subquery
from rest_framework import mixins, permissions, viewsets

from .models import Membership, Organization
from .serializers import OrganizationSerializer


class OrganizationViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Organization.objects.none()
        user = self.request.user
        my_role = Membership.objects.filter(
            organization=OuterRef("pk"), user=user
        ).values("role")[:1]
        return Organization.objects.filter(memberships__user=user).annotate(
            my_role=Subquery(my_role)
        )
