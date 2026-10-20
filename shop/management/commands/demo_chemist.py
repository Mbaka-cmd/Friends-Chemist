import re
from django.core.management.base import BaseCommand
from shop.models import Product, StockMovement
SAFE = {'Pain Relief', 'Cough & Cold', 'Vitamins & Supplements', 'Stomach & Digestive', 'Skin Care & Creams', 'Family Planning & Wellness'}
DENY = re.compile(r'TRAMADOL|INJ|VIAL|SALBUTAMOL|LYDIA|MENOZIP|MELOXICAM|ACECLOFENAC|DICLOFENAC|KETOCONAZOLE|PESS|PRAZOLE|CLOTRIM|CLOZOLE|ALLUCID')
class Command(BaseCommand):
    help = 'DEMO only: use suggested prices, add placeholder demo stock, publish only general-sale categories. Owner/pharmacist must review.'
    def handle(self, *a, **o):
        pub = hid = stk = 0
        for p in Product.objects.filter(dept='chemist', status='demo'):
            if p.sell_price is None and p.suggested_price is not None: p.sell_price = p.suggested_price
            safe = p.category in SAFE and not DENY.search(p.name.upper())
            p.is_public, p.restricted = safe, not safe
            p.save(); pub += safe; hid += (not safe)
            if p.quoted_qty and not p.movements.exists():
                StockMovement.objects.create(product=p, qty=p.quoted_qty, kind='opening', is_demo=True,
                                             reason='DEMO placeholder stock from quotation qty (NOT counted stock)'); stk += 1
        self.stdout.write(f'Public on website: {pub} | kept off website (needs pharmacist review): {hid} | demo stock rows: {stk}')