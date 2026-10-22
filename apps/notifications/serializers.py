from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    task_id = serializers.IntegerField(read_only=True)
    project_id = serializers.IntegerField(source="task.project_id", read_only=True)
    organization_id = serializers.IntegerField(
        source="task.project.organization_id", read_only=True
    )

    class Meta:
        model = Notification
        fields = (
            "id",
            "kind",
            "message",
            "is_read",
            "task_id",
            "project_id",
            "organization_id",
            "created_at",
            "read_at",
        )
        read_only_fields = fields


class UnreadCountSerializer(serializers.Serializer):
    unread = serializers.IntegerField()


class MarkedSerializer(serializers.Serializer):
    marked = serializers.IntegerField()
