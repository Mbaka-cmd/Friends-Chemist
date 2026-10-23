from django.core.management.base import BaseCommand, CommandError

from shop.models import Product
from shop.naming import tidy


class Command(BaseCommand):
    help = "Fill display_name (the customer-facing name) for public products. Dry run unless --apply."

    def add_arguments(self, p):
        p.add_argument("--apply", action="store_true")
        p.add_argument("--overwrite", action="store_true", help="replace display names that are already set")
        p.add_argument("--set", action="append", default=[], help='force a name: "STOCK NAME=Shown name"')

    def handle(self, *a, **o):
        manual = {}
        for item in o["set"]:
            if "=" not in item:
                raise CommandError('--set needs the form "STOCK NAME=Shown name"')
            k, v = item.rsplit("=", 1)
            manual[k.strip().lower()] = v.strip()
        qs = Product.objects.filter(is_public=True, active=True, restricted=False).order_by("dept", "name", "pack")
        same = changed = kept = 0
        for p in qs:
            key = (p.name or "").strip().lower()
            new = manual.get(key) or tidy(p.name)
            if p.display_name and not o["overwrite"] and key not in manual:
                kept += 1
                continue
            if new == p.name:
                same += 1
                continue
            self.stdout.write("%-8s %-34s -> %s" % (p.dept, p.name[:34], new))
            if o["apply"] and p.display_name != new:
                p.display_name = new
                p.save(update_fields=["display_name"])
                changed += 1
        self.stdout.write("")
        self.stdout.write("unchanged by tidy: %d | already set: %d | %s: %d" % (
            same, kept, "SAVED" if o["apply"] else "would change", changed if o["apply"] else 0))
        if not o["apply"]:
            self.stdout.write(self.style.WARNING("DRY RUN - nothing saved"))