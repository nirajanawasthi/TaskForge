from django_filters import rest_framework as filters


class StableOrderingFilter(filters.OrderingFilter):
    """Ordering filter that breaks ties by id so pages never overlap."""

    def filter(self, qs, value):
        qs = super().filter(qs, value)
        if value:
            qs = qs.order_by(*qs.query.order_by, "-id")
        return qs
