from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from structure.models import Category, Entity, Sector, Subsector

from .models import Membership


class MembershipCleanTests(TestCase):
    def _build_entity(self) -> Entity:
        sector = Sector.objects.create(name="Sector Test")
        subsector = Subsector.objects.create(sector=sector, name="Subsector Test")
        category = Category.objects.create(subsector=subsector, name="Categoria Test")
        return Entity.objects.create(category=category, code="ENT", name="Entidad Test")

    def test_loader_requires_entity(self):
        user = get_user_model().objects.create_user(username="tester", password="pass1234")
        membership = Membership(
            user=user,
            entity=None,
            role="LOADER",
        )

        with self.assertRaises(ValidationError):
            membership.full_clean()

    def test_loader_with_entity_is_valid(self):
        user = get_user_model().objects.create_user(username="tester2", password="pass1234")
        entity = self._build_entity()
        membership = Membership(
            user=user,
            entity=entity,
            role="LOADER",
        )

        membership.full_clean()
