from rest_framework import serializers

from .models import Project, ProjectMember


class ProjectSerializer(serializers.ModelSerializer):
    created_by = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = Project
        fields = (
            "id",
            "name",
            "description",
            "is_private",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ProjectMemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ProjectMember
        fields = ("id", "email", "joined_at")
        read_only_fields = fields


class AddProjectMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
