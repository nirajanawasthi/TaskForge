from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters

from config.filters import StableOrderingFilter

from .models import Task


class TaskFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=Task.Status.choices)
    priority = filters.MultipleChoiceFilter(choices=Task.Priority.choices)
    assignee_email = filters.CharFilter(field_name="assignee__email", lookup_expr="iexact")
    assigned_to_me = filters.BooleanFilter(method="filter_assigned_to_me")
    unassigned = filters.BooleanFilter(field_name="assignee", lookup_expr="isnull")
    overdue = filters.BooleanFilter(method="filter_overdue")
    due_before = filters.DateFilter(field_name="due_date", lookup_expr="lte")
    due_after = filters.DateFilter(field_name="due_date", lookup_expr="gte")
    ordering = StableOrderingFilter(
        fields=(
            ("due_date", "due_date"),
            ("created_at", "created_at"),
            ("updated_at", "updated_at"),
            ("title", "title"),
            ("priority_rank", "priority"),
        )
    )

    class Meta:
        model = Task
        fields = []

    def filter_assigned_to_me(self, queryset, name, value):
        user = self.request.user
        if value:
            return queryset.filter(assignee=user)
        return queryset.exclude(assignee=user)

    def filter_overdue(self, queryset, name, value):
        today = timezone.localdate()
        if value:
            return queryset.filter(due_date__lt=today).exclude(status=Task.Status.DONE)
        return queryset.filter(
            Q(due_date__isnull=True)
            | Q(due_date__gte=today)
            | Q(status=Task.Status.DONE)
        )
