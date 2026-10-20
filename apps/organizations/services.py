from django.db import transaction

from .models import Membership, Organization


@transaction.atomic
def create_organization(*, user, name):
    """Create an organization and make the creator its admin, atomically."""
    organization = Organization.objects.create(name=name, created_by=user)
    Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.ADMIN
    )
    return organization
