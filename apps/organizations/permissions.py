from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Membership


class IsOrganizationAdminOrReadOnly(BasePermission):
    """Any member may read; only organization admins may change members.

    view.requesting_membership raises Http404 for non-members, so people
    outside the organization cannot tell whether it exists.
    """

    def has_permission(self, request, view):
        membership = view.requesting_membership
        if request.method in SAFE_METHODS:
            return True
        return membership.role == Membership.Role.ADMIN
