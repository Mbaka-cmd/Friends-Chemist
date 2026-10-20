import csv
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand
from shop.models import Product

def dec(v):
    try: return Decimal(v.strip()) if v and v.strip() else None
    except InvalidOperation: return None

class Command(BaseCommand):
    help = 'Import Chemist supplier register (TSV). Preview by default; add --commit to save. Never touches stock or approved prices.'
    def add_arguments(self, p):
        p.add_argument('path'); p.add_argument('--commit', action='store_true')
    def handle(self, path, commit, **o):
        rows, seen, dups, bad = [], set(), [], []
        with open(path, encoding='utf-8-sig', newline='') as fh:
            for i, r in enumerate(csv.reader(fh, delimiter='\t'), 1):
                if not r or not r[0].strip() or r[0].lower().startswith('supplier sku'): continue
                r += [''] * (17 - len(r)); sku = r[0].strip()
                if sku in seen: dups.append(sku); continue
                seen.add(sku)
                if not r[1].strip(): bad.append(f'line {i}: no name'); continue
                rows.append((sku, r[1].strip(), r[3].strip(), int(dec(r[4]) or 0), dec(r[6]), dec(r[10])))
        new = sum(not Product.objects.filter(sku=s).exists() for s, *_ in rows)
        self.stdout.write(f'Rows: {len(rows)} | new: {new} | updates: {len(rows)-new} | duplicate SKUs skipped: {dups} | problems: {bad}')
        self.stdout.write(f'Quoted line total check (sum BP x qty): {sum((r[4] or 0) * r[3] for r in rows)}')
        if not commit: return self.stdout.write('Preview only. Re-run with --commit to save.')
        for sku, name, pack, qq, bp, sug in rows:
            p, created = Product.objects.get_or_create(sku=sku, defaults=dict(name=name, dept='chemist', pack=pack, supplier_ref=sku,
                status='demo', is_public=False, restricted=True))
            p.quoted_qty, p.suggested_price = qq, sug
            if p.status != 'verified': p.buy_price = bp  # quoted price only; verified costs are never overwritten
            p.save()
        self.stdout.write('Imported. Items stay hidden from the public site until reviewed and approved.')