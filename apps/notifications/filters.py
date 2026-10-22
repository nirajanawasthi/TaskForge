from django_filters import rest_framework as filters

from .models import Notification


class NotificationFilter(filters.FilterSet):
    is_read = filters.BooleanFilter(field_name="is_read")
    kind = filters.MultipleChoiceFilter(choices=Notification.Kind.choices)

    class Meta:
        model = Notification
        fields = []
