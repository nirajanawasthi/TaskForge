from rest_framework import serializers

from .models import Membership, Organization
from .services import create_organization


class OrganizationSerializer(serializers.ModelSerializer):
    my_role = serializers.CharField(read_only=True)

    class Meta:
        model = Organization
        fields = ("id", "name", "slug", "my_role", "created_at")
        read_only_fields = ("id", "slug", "created_at")

    def create(self, validated_data):
        organization = create_organization(
            user=self.context["request"].user, name=validated_data["name"]
        )
        organization.my_role = Membership.Role.ADMIN
        return organization


class MembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Membership
        fields = ("id", "email", "role", "joined_at")
        read_only_fields = fields


class AddMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=Membership.Role.choices, default=Membership.Role.MEMBER
    )


class ChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices)
