from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.organizations.models import Membership

from .models import Project, ProjectMember


@transaction.atomic
def create_project(*, organization, user, **fields):
    """Create a project and make its creator a project member, atomically."""
    project = Project.objects.create(
        organization=organization, created_by=user, **fields
    )
    ProjectMember.objects.create(project=project, user=user)
    return project


@transaction.atomic
def add_project_member(*, project, email):
    """Add an organization member to a project by email."""
    org_membership = (
        Membership.objects.select_related("user")
        .filter(organization_id=project.organization_id, user__email__iexact=email.strip())
        .first()
    )
    if org_membership is None:
        raise ValidationError(
            {"email": "This user is not a member of the organization."}
        )
    if ProjectMember.objects.filter(project=project, user=org_membership.user).exists():
        raise ValidationError({"email": "This user is already on the project."})
    try:
        return ProjectMember.objects.create(project=project, user=org_membership.user)
    except IntegrityError:
        raise ValidationError({"email": "This user is already on the project."})
