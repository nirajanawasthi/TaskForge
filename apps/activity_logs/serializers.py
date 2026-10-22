from rest_framework import serializers

from .models import ActivityLog


class ActivitySerializer(serializers.ModelSerializer):
    actor = serializers.EmailField(source="actor.email", read_only=True, allow_null=True)

    class Meta:
        model = ActivityLog
        fields = ("id", "actor", "action", "details", "created_at")
        read_only_fields = fields
