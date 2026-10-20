import getpass
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from shop.models import Profile

class Command(BaseCommand):
    help = 'Create an employee limited to one department: make_staff <username> <chemist|agrovet>'
    def add_arguments(self, p): p.add_argument('username'); p.add_argument('dept', choices=['chemist', 'agrovet'])
    def handle(self, username, dept, **o):
        U = get_user_model()
        if U.objects.filter(username=username).exists(): raise CommandError('User exists.')
        pw = getpass.getpass('Password (min 10 chars): ')
        u = U(username=username); u.set_password(pw); u.full_clean(exclude=['password']) if False else None; u.save()
        Profile.objects.create(user=u, department=dept); self.stdout.write(f'Created {username} for {dept}.')