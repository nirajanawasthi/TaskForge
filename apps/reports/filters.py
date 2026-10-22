from django_filters import rest_framework as filters

from apps.tasks.models import Task


class OverdueFilter(filters.FilterSet):
    project = filters.NumberFilter(field_name="project_id")
    assignee_email = filters.CharFilter(field_name="assignee__email", lookup_expr="iexact")
    priority = filters.MultipleChoiceFilter(choices=Task.Priority.choices)

    class Meta:
        model = Task
        fields = []
