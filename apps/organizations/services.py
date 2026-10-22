from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User

from .models import Membership, Organization


@transaction.atomic
def create_organization(*, user, name):
    """Create an organization and make the creator its admin, atomically."""
    organization = Organization.objects.create(name=name, created_by=user)
    Membership.objects.create(
        user=user, organization=organization, role=Membership.Role.ADMIN
    )
    return organization


def _locked_admin_count(organization_id):
    """Lock the organization's admin rows so concurrent changes cannot both pass."""
    return len(
        list(
            Membership.objects.select_for_update()
            .filter(organization_id=organization_id, role=Membership.Role.ADMIN)
            .values_list("pk", flat=True)
        )
    )


@transaction.atomic
def add_member(*, organization, email, role):
    try:
        user = User.objects.get(email__iexact=email.strip())
    except User.DoesNotExist:
        raise ValidationError({"email": "No registered user with this email."})
    if Membership.objects.filter(organization=organization, user=user).exists():
        raise ValidationError({"email": "This user is already a member."})
    try:
        return Membership.objects.create(user=user, organization=organization, role=role)
    except IntegrityError:
        raise ValidationError({"email": "This user is already a member."})


@transaction.atomic
def change_role(*, membership, role):
    admin_count = _locked_admin_count(membership.organization_id)
    membership.refresh_from_db()
    if (
        membership.role == Membership.Role.ADMIN
        and role != Membership.Role.ADMIN
        and admin_count <= 1
    ):
        raise ValidationError({"role": "An organization must keep at least one admin."})
    membership.role = role
    membership.save(update_fields=["role"])
    return membership


@transaction.atomic
def remove_member(*, membership):
    admin_count = _locked_admin_count(membership.organization_id)
    membership.refresh_from_db()
    if membership.role == Membership.Role.ADMIN and admin_count <= 1:
        raise ValidationError({"detail": "An organization must keep at least one admin."})
    membership.delete()
