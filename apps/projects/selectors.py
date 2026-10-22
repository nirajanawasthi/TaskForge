from django.db.models import Exists, OuterRef, Q

from apps.organizations.models import Membership

from .models import Project, ProjectMember


def visible_projects(*, user, membership):
    """Projects in the membership's organization that the user may see.

    Organization admins see everything. Everyone else sees public projects
    plus private projects they belong to.
    """
    queryset = Project.objects.filter(organization_id=membership.organization_id)
    if membership.role == Membership.Role.ADMIN:
        return queryset
    is_member = Exists(
        ProjectMember.objects.filter(project=OuterRef("pk"), user=user)
    )
    return queryset.annotate(is_member=is_member).filter(
        Q(is_private=False) | Q(is_member=True)
    )
