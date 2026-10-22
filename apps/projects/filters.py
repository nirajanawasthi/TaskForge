from django_filters import rest_framework as filters

from config.filters import StableOrderingFilter

from .models import Project


class ProjectFilter(filters.FilterSet):
    ordering = StableOrderingFilter(
        fields=(
            ("name", "name"),
            ("created_at", "created_at"),
            ("updated_at", "updated_at"),
        )
    )

    class Meta:
        model = Project
        fields = ["is_private"]
