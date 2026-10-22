from django.utils import timezone
from rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    assignee = serializers.EmailField(
        source="assignee.email", read_only=True, allow_null=True
    )
    created_by = serializers.EmailField(source="created_by.email", read_only=True)
    assignee_email = serializers.EmailField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "description",
            "status",
            "priority",
            "assignee",
            "assignee_email",
            "created_by",
            "due_date",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "status", "created_at", "updated_at")

    def validate_due_date(self, value):
        if value is not None and value < timezone.localdate():
            raise serializers.ValidationError("The due date cannot be in the past.")
        return value
