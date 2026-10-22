from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update an employee login (POS access only)"

    def add_arguments(self, p):
        p.add_argument("username")
        p.add_argument("password")

    def handle(self, *a, **o):
        U = get_user_model()
        u, created = U.objects.get_or_create(**{U.USERNAME_FIELD: o["username"]})
        u.set_password(o["password"])
        u.is_staff = True
        u.is_superuser = False
        u.save()
        g, _ = Group.objects.get_or_create(name="Employee")
        u.groups.add(g)
        self.stdout.write(self.style.SUCCESS(
            "%s employee '%s' (POS only)." % ("Created" if created else "Updated", o["username"])))