from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from plants.models import Plant
from projects.models import Project

from .models import Membership


class MembershipCleanTests(TestCase):
    def test_membership_rejects_plant_and_project(self):
        user = get_user_model().objects.create_user(username="tester", password="pass1234")
        plant = Plant.objects.create(code="PLANT", name="Plant")
        project = Project.objects.create(name="Project")

        membership = Membership(
            user=user,
            plant=plant,
            project=project,
            role="LOADER",
        )

        with self.assertRaises(ValidationError):
            membership.full_clean()
