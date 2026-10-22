from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response

from .models import Membership, Organization
from .permissions import IsOrganizationAdminOrReadOnly
from .serializers import (
    AddMemberSerializer,
    ChangeRoleSerializer,
    MembershipSerializer,
    OrganizationSerializer,
)
from .services import add_member, change_role, remove_member


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


class MembershipViewSet(
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = MembershipSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrganizationAdminOrReadOnly]

    @cached_property
    def requesting_membership(self):
        """The caller's own membership in the URL's organization, else 404."""
        return get_object_or_404(
            Membership.objects.select_related("organization"),
            organization_id=self.kwargs["organization_pk"],
            user=self.request.user,
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Membership.objects.none()
        return (
            Membership.objects.filter(
                organization=self.requesting_membership.organization
            )
            .select_related("user")
            .order_by("joined_at", "id")
        )

    @extend_schema(request=AddMemberSerializer, responses={201: MembershipSerializer})
    def create(self, request, *args, **kwargs):
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = add_member(
            organization=self.requesting_membership.organization,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
        )
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ChangeRoleSerializer, responses={200: MembershipSerializer})
    def partial_update(self, request, *args, **kwargs):
        membership = self.get_object()
        serializer = ChangeRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = change_role(
            membership=membership, role=serializer.validated_data["role"]
        )
        return Response(MembershipSerializer(membership).data)

    def perform_destroy(self, instance):
        remove_member(membership=instance)
