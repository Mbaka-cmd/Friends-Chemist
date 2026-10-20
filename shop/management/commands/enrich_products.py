import re
from django.core.management.base import BaseCommand
from shop.models import Product
FORMS = [('SYP', 'Syrup'), ('SYRUP', 'Syrup'), ('SUSP', 'Suspension'), ('TABS', 'Tablets'), ('TAB', 'Tablets'), ('CAPS', 'Capsules'),
         ('INJ', 'Injection'), ('INJECTION', 'Injection'), ('VIAL', 'Injection'), ('CREAM', 'Cream'), ('OINT', 'Ointment'), ('GEL', 'Gel'),
         ('BALM', 'Balm'), ('PESS', 'Pessary'), ('PESSARIES', 'Pessary'), ('LOZENGES', 'Lozenges'), ('DPS', 'Drops')]
class Command(BaseCommand):
    help = 'Fill empty strength, dosage form and pack size on Chemist products by reading the product name.'
    def handle(self, *a, **o):
        n = 0
        for p in Product.objects.filter(dept='chemist'):
            u = p.name.upper(); ch = []
            if not p.strength:
                m = re.search(r'(?<![A-Z\d.])(\d+(?:\.\d+)?)\s?(MG|MLS?|GMS?|G|%)(?![A-Z])', u)
                if m: p.strength = (m.group(1) + m.group(2).lower().replace('mls', 'ml').replace('gms', 'g').replace('gm', 'g')); ch.append(1)
            if not p.dosage_form:
                f = next((v for k, v in FORMS if re.search(r'\b' + k + r'\b', u)), '')
                if f: p.dosage_form = f; ch.append(1)
            if not p.pack:
                m = re.search(r"(?<![\d.])(\d+)\s?[`']?S\b", u)
                if m: p.pack = m.group(1) + 's'; ch.append(1)
            if ch: p.save(); n += 1
        self.stdout.write(f'{n} products enriched from their names.')