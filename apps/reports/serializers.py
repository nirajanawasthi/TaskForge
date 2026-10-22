from django.utils import timezone
from rest_framework import serializers

from apps.tasks.models import Task


class StatusCountsSerializer(serializers.Serializer):
    todo = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    in_review = serializers.IntegerField()
    done = serializers.IntegerField()


class TaskTotalsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = StatusCountsSerializer()
    overdue = serializers.IntegerField()
    due_soon = serializers.IntegerField()
    unassigned = serializers.IntegerField()
    completion_rate = serializers.FloatField()


class PriorityCountsSerializer(serializers.Serializer):
    low = serializers.IntegerField()
    medium = serializers.IntegerField()
    high = serializers.IntegerField()
    urgent = serializers.IntegerField()


class MyTasksSerializer(serializers.Serializer):
    open = serializers.IntegerField()
    overdue = serializers.IntegerField()


class WorkloadSerializer(serializers.Serializer):
    email = serializers.EmailField()
    open = serializers.IntegerField()
    overdue = serializers.IntegerField()
    done = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    """Documents the dashboard response. The view returns plain dicts."""

    projects = serializers.IntegerField()
    tasks = TaskTotalsSerializer()
    open_by_priority = PriorityCountsSerializer()
    my_tasks = MyTasksSerializer()
    workload = WorkloadSerializer(many=True, required=False)


class OverdueTaskSerializer(serializers.ModelSerializer):
    project = serializers.CharField(source="project.name", read_only=True)
    project_id = serializers.IntegerField(read_only=True)
    assignee = serializers.EmailField(
        source="assignee.email", read_only=True, allow_null=True
    )
    days_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = (
            "id",
            "title",
            "project_id",
            "project",
            "priority",
            "status",
            "assignee",
            "due_date",
            "days_overdue",
        )
        read_only_fields = fields

    def get_days_overdue(self, obj) -> int:
        return (timezone.localdate() - obj.due_date).days
