from pathlib import Path
from decimal import Decimal
from django.core.management.base import BaseCommand
from shop.models import Product, StockMovement

class Command(BaseCommand):
    help = 'Load the 40-item Agrovet DEMO register (status=demo). Safe to re-run; never touches existing products.'
    def handle(self, *a, **o):
        f = Path(__file__).resolve().parents[2] / 'data' / 'agrovet_demo.csv'
        n = 0
        for line in f.read_text(encoding='utf-8').splitlines():
            sku, name, cat, pack, bp, sp, st = line.split('|')
            p, new = Product.objects.get_or_create(sku=sku, defaults=dict(name=name, dept='agrovet', category=cat, pack=pack,
                buy_price=Decimal(bp), sell_price=Decimal(sp), status='demo', is_public=True,
                restricted=cat in ('Crop protection', 'Veterinary and hygiene')))
            if new:
                StockMovement.objects.create(product=p, qty=int(st), kind='opening', reason='DEMO opening stock', is_demo=True); n += 1
        self.stdout.write(f'{n} demo products added (DEMO - VERIFY BEFORE TRADING).')