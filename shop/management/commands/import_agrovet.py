import re, shutil
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from shop.models import Product, StockMovement

def money(v):
    v = re.sub(r"[^0-9.]", "", v or "")
    try:
        return float(v) if v else None
    except ValueError:
        return None

def category(name):
    n = name.lower()
    if any(k in n for k in ("feeder", "syringe", "needle", "gloves", "kill/trap")):
        return "Farm equipment"
    if any(k in n for k in ("tingatinga", "kolopa", "weedal", "kaushia", "dmax", "escort", "sevin",
                            "parastar", "mr bean", "b-safi", "force", "acenex", "passcode",
                            "komix", "bietra", "velman", "kantap", "durocap")):
        return "Crop protection"
    if any(k in n for k in ("fastgrow", "epsom", "booster", "tolakay")) and "udder" not in n and "egg" not in n:
        return "Crop nutrition"
    if any(k in n for k in ("lick", "mix", "dcp", "milk replacer", "block", "salt", "vitamin", "vital",
                            "vitax", "udaminx", "pig", "beemix", "chapp", "kupa", "truvet",
                            "bromix", "kaolin", "maxilick", "natrox", "nobreen", "twelve")):
        return "Animal feeds"
    return "Veterinary and hygiene"

class Command(BaseCommand):
    help = "Replace all agrovet products with agrovet_list.txt"

    def add_arguments(self, p):
        p.add_argument("file", nargs="?", default="agrovet_list.txt")

    def handle(self, *a, **o):
        fields = {f.name: f for f in Product._meta.fields}
        lines = Path(o["file"]).read_text(encoding="utf-8-sig").splitlines()
        rows, used, n = [], set(), 0
        for line in lines:
            c = line.split("|")
            c += [""] * (5 - len(c))
            if not c[1].strip():
                continue
            sku = c[0].strip()
            if not sku:
                n += 1
                sku = f"Agr-X{n:03d}"
            while sku in used:
                sku += "b"
            used.add(sku)
            price = money(c[3])
            d = {"sku": sku, "name": c[1].strip(), "pack": c[2].strip(),
                 "sell_price": price, "review_note": c[4].strip(),
                 "dept": "agrovet", "category": category(c[1]),
                 "is_public": True, "active": True}
            rows.append({k: v for k, v in d.items() if k in fields})

        db = Path(settings.DATABASES["default"]["NAME"])
        shutil.copy(db, db.with_name("db.backup.sqlite3"))
        self.stdout.write("Backup saved: db.backup.sqlite3")

        with transaction.atomic():
            old = Product.objects.filter(dept="agrovet")
            moves = StockMovement.objects.filter(product__in=old).delete()[0]
            deleted = old.delete()[0]
            Product.objects.bulk_create([Product(**r) for r in rows])
        self.stdout.write(self.style.SUCCESS(
            f"Removed {deleted} old rows (and {moves} stock movements), added {len(rows)} products."))
