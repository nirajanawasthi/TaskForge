from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property

from apps.organizations.models import Membership

from .selectors import visible_projects


class OrganizationScopedMixin:
    """Resolve the caller's membership in the URL's organization.

    check_permissions runs ensure_visible() first, so anything the caller may
    not see answers 404 before any role check can answer 403.
    """

    @cached_property
    def requesting_membership(self):
        return get_object_or_404(
            Membership.objects.select_related("organization"),
            organization_id=self.kwargs["organization_pk"],
            user=self.request.user,
        )

    def ensure_visible(self):
        self.requesting_membership

    def check_permissions(self, request):
        if request.user.is_authenticated:
            self.ensure_visible()
        super().check_permissions(request)


class ProjectScopedMixin(OrganizationScopedMixin):
    """Resolve the URL's project, only if the caller is allowed to see it."""

    @cached_property
    def project(self):
        queryset = visible_projects(
            user=self.request.user, membership=self.requesting_membership
        )
        return get_object_or_404(queryset, pk=self.kwargs["project_pk"])

    def ensure_visible(self):
        self.project
