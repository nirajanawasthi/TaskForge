from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.organizations.models import Membership

MANAGE_ROLES = {Membership.Role.ADMIN, Membership.Role.MANAGER}


class CanManageProjects(BasePermission):
    """Any organization member may read; only admins and managers may write.

    view.requesting_membership raises Http404 for non-members, so people
    outside the organization cannot tell whether it exists.
    """

    def has_permission(self, request, view):
        membership = view.requesting_membership
        if request.method in SAFE_METHODS:
            return True
        return membership.role in MANAGE_ROLES
