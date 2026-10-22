from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.organizations.models import Membership

TASK_WRITE_ROLES = {
    Membership.Role.ADMIN,
    Membership.Role.MANAGER,
    Membership.Role.TEAM_LEAD,
}


class CanManageTasks(BasePermission):
    """Anyone who can see the project may read its tasks; leads and above write.

    The view's check_permissions has already answered 404 for projects the
    caller cannot see, so a 403 here never reveals a hidden project.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return view.requesting_membership.role in TASK_WRITE_ROLES
