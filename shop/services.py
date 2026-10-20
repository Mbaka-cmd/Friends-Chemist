from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone
import uuid
from .models import AuditLog, Batch, Product, Sale, SaleLine, StockMovement

class StockError(Exception): pass

def audit(user, action, detail=''):
    AuditLog.objects.create(user=user if getattr(user, 'is_authenticated', False) else None, action=action, detail=detail[:300])

def _take(p, qty, sale, user):
    left, today = qty, timezone.localdate()
    bs = (p.batches.select_for_update().filter(qty_remaining__gt=0).filter(Q(expiry__isnull=True) | Q(expiry__gte=today))
          .order_by(F('expiry').asc(nulls_last=True), 'id'))
    demo = p.status == 'demo'
    for b in bs:  # FEFO: earliest expiry first, never an expired batch
        if left == 0: break
        n = min(b.qty_remaining, left); b.qty_remaining -= n; b.save(update_fields=['qty_remaining'])
        StockMovement.objects.create(product=p, batch=b, qty=-n, kind='sale', ref=sale.receipt_no, user=user, is_demo=demo)
        left -= n
    if left:
        StockMovement.objects.create(product=p, qty=-left, kind='sale', ref=sale.receipt_no, user=user, is_demo=demo)

def _record(user, dept, items, method, key, pay_ref):
    existing = Sale.objects.filter(idem_key=key).first()
    if existing: return existing
    merged = {}
    for pid, q in items:
        if q <= 0: raise StockError('Quantity must be positive.')
        merged[pid] = merged.get(pid, 0) + q
    if not merged: raise StockError('Cart is empty.')
    prods = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=merged, dept=dept, active=True)}
    sale = Sale.objects.create(receipt_no=f'{dept[:1].upper()}{timezone.localtime():%y%m%d}-{uuid.uuid4().hex[:6].upper()}',
                               dept=dept, cashier=user, method=method, pay_ref=pay_ref, idem_key=key)
    total, demo = Decimal('0'), False
    for pid, q in merged.items():
        p = prods.get(pid)
        if not p: raise StockError('Product not available in this department.')
        if p.sell_price is None: raise StockError(f'{p.name}: no approved selling price set.')
        if p.sellable() < q: raise StockError(f'{p.name}: only {p.sellable()} sellable (expired/quarantined stock excluded).')
        _take(p, q, sale, user)
        lt = p.sell_price * q; total += lt; demo = demo or p.status == 'demo'
        SaleLine.objects.create(sale=sale, product=p, name=p.name, qty=q, unit_price=p.sell_price,
                                unit_cost=p.buy_price if p.status == 'verified' else None, line_total=lt)
    sale.total, sale.is_demo = total, demo
    sale.save(update_fields=['total', 'is_demo'])
    audit(user, 'sale', f'{sale.receipt_no} {total}')
    return sale

def record_sale(user, dept, items, method, key, pay_ref=''):
    try:
        with transaction.atomic():
            return _record(user, dept, items, method, key, pay_ref)
    except IntegrityError:
        s = Sale.objects.filter(idem_key=key).first()
        if s: return s
        raise

@transaction.atomic
def change_stock(product, qty, kind, user, reason='', batch_no='', expiry=None, cost=None, supplier=''):
    if qty == 0: raise StockError('Quantity cannot be zero.')
    if kind != 'receipt' and not reason.strip(): raise StockError('A reason is required.')
    p = Product.objects.select_for_update().get(pk=product.pk)
    batch = None
    if batch_no:
        batch, _ = Batch.objects.get_or_create(product=p, batch_no=batch_no,
                    defaults={'expiry': expiry, 'supplier': supplier, 'cost': cost})
        if batch.qty_remaining + qty < 0: raise StockError('Batch does not hold that quantity.')
        batch.qty_remaining += qty; batch.save(update_fields=['qty_remaining'])
    elif qty < 0 and (p.movements.filter(batch__isnull=True).aggregate(s=Sum('qty'))['s'] or 0) + qty < 0:
        raise StockError('Would make unbatched stock negative.')
    m = StockMovement.objects.create(product=p, batch=batch, qty=qty, kind=kind, reason=reason, user=user,
                                     is_demo=p.status == 'demo', ref=supplier)
    audit(user, f'stock_{kind}', f'{p.sku} {qty:+d} {reason}')
    return m
# ---- v5 ----
from django.db.models import Count
from .models import Expense, SaleReturn
Q2 = Decimal('0.01')

def _take(p, qty, sale, user):
    """FEFO from non-expired batches; returns (cost, cost_known). Cost = specific batch cost, else product buying cost."""
    left, today, cost, known, demo = qty, timezone.localdate(), Decimal('0'), True, p.status == 'demo'
    bs = (p.batches.select_for_update().filter(qty_remaining__gt=0).filter(Q(expiry__isnull=True) | Q(expiry__gte=today))
          .order_by(F('expiry').asc(nulls_last=True), 'id'))
    for b in bs:
        if left == 0: break
        n = min(b.qty_remaining, left); b.qty_remaining -= n; b.save(update_fields=['qty_remaining'])
        u = b.cost if b.cost is not None else p.buy_price
        if u is None: known = False
        else: cost += u * n
        StockMovement.objects.create(product=p, batch=b, qty=-n, kind='sale', ref=sale.receipt_no, user=user, is_demo=demo)
        left -= n
    if left:
        if p.buy_price is None: known = False
        else: cost += p.buy_price * left
        StockMovement.objects.create(product=p, qty=-left, kind='sale', ref=sale.receipt_no, user=user, is_demo=demo)
    return cost, known

def _record(user, dept, items, method, key, pay_ref, discount):
    existing = Sale.objects.filter(idem_key=key).first()
    if existing: return existing
    merged = {}
    for pid, q in items:
        if q <= 0: raise StockError('Quantity must be positive.')
        merged[pid] = merged.get(pid, 0) + q
    if not merged: raise StockError('Cart is empty.')
    prods = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=merged, dept=dept, active=True)}
    sale = Sale.objects.create(receipt_no=f'{dept[:1].upper()}{timezone.localtime():%y%m%d}-{uuid.uuid4().hex[:6].upper()}', dept=dept,
                               cashier=user, method=method, pay_ref=pay_ref, idem_key=key,
                               pay_status='cash_received' if method == 'cash' else 'unverified')
    sub, demo = Decimal('0'), False
    for pid, q in merged.items():
        p = prods.get(pid)
        if not p: raise StockError('Product not available in this department.')
        if p.sell_price is None: raise StockError(f'{p.name}: no approved selling price set.')
        if p.sellable() < q: raise StockError(f'{p.name}: only {p.sellable()} sellable (expired/quarantined stock excluded).')
        cost, known = _take(p, q, sale, user)
        lt = p.sell_price * q; sub += lt; demo = demo or p.status == 'demo'
        SaleLine.objects.create(sale=sale, product=p, name=p.name, qty=q, unit_price=p.sell_price, line_total=lt,
                                unit_cost=(cost / q).quantize(Q2) if known else None, cost_total=cost.quantize(Q2) if known else None)
    if discount < 0 or discount > sub: raise StockError('Invalid discount.')
    sale.discount, sale.total, sale.is_demo = discount, sub - discount, demo
    sale.save(update_fields=['discount', 'total', 'is_demo'])
    audit(user, 'sale', f'{sale.receipt_no} {sale.total}')
    return sale

def record_sale(user, dept, items, method, key, pay_ref='', discount=Decimal('0')):
    try:
        with transaction.atomic():
            return _record(user, dept, items, method, key, pay_ref, discount)
    except IntegrityError:
        s = Sale.objects.filter(idem_key=key).first()
        if s: return s
        raise

@transaction.atomic
def void_sale(sale, user, reason):
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status != 'completed' or sale.returns.exists(): raise StockError('Only completed sales without returns can be voided.')
    if not reason.strip(): raise StockError('A reason is required.')
    for m in StockMovement.objects.filter(ref=sale.receipt_no, kind='sale'):
        if m.batch_id:
            b = Batch.objects.select_for_update().get(pk=m.batch_id); b.qty_remaining += -m.qty; b.save(update_fields=['qty_remaining'])
        StockMovement.objects.create(product=m.product, batch=m.batch, qty=-m.qty, kind='return', reason=f'VOID: {reason}'[:250], ref=sale.receipt_no + '-V', user=user, is_demo=m.is_demo)
    sale.status, sale.void_reason = 'voided', reason[:250]; sale.save(update_fields=['status', 'void_reason'])
    audit(user, 'sale_void', f'{sale.receipt_no} {reason}')

@transaction.atomic
def return_items(sale, user, qtys, reason, restock=True):
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status != 'completed': raise StockError('Sale is not active.')
    if not reason.strip(): raise StockError('A reason is required.')
    sub = sale.total + sale.discount; factor = (sale.total / sub) if sub else Decimal('1'); did = False
    for line in sale.lines.select_for_update():
        q = qtys.get(line.pk, 0)
        if q <= 0: continue
        left = line.qty - (line.returns.aggregate(s=Sum('qty'))['s'] or 0)
        if q > left: raise StockError(f'{line.name}: only {left} can still be returned.')
        cb = (line.cost_total * q / line.qty).quantize(Q2) if line.cost_total is not None else None
        SaleReturn.objects.create(sale=sale, line=line, qty=q, refund=(line.unit_price * q * factor).quantize(Q2), cost_back=cb, reason=reason[:250], restocked=restock, user=user)
        if restock: StockMovement.objects.create(product=line.product, qty=q, kind='return', reason=f'Return: {reason}'[:250], ref=sale.receipt_no + '-R', user=user, is_demo=line.product.status == 'demo')
        did = True
    if not did: raise StockError('Nothing to return.')
    audit(user, 'sale_return', f'{sale.receipt_no} {reason}')

def pnl(depts, d1, d2, demo=False):
    Z = Decimal('0')
    S = Sale.objects.filter(dept__in=depts, status='completed', is_demo=demo, created__date__range=(d1, d2))
    a = S.aggregate(t=Sum('total'), d=Sum('discount'), n=Count('id')); total, disc = a['t'] or Z, a['d'] or Z
    L = SaleLine.objects.filter(sale__in=S); lines, costed = L.count(), L.filter(cost_total__isnull=False).count()
    cogs_sold = L.aggregate(c=Sum('cost_total'))['c'] or Z
    R = SaleReturn.objects.filter(sale__dept__in=depts, sale__is_demo=demo, created__date__range=(d1, d2))
    ra = R.aggregate(r=Sum('refund'), c=Sum('cost_back')); refunds, back = ra['r'] or Z, ra['c'] or Z
    net, cogs = total - refunds, cogs_sold - back
    complete = lines == costed and not R.filter(cost_back__isnull=True).exists()
    gp = (net - cogs) if complete else None
    margin = (gp / net * 100).quantize(Q2) if gp is not None and net > 0 else None
    E = Expense.objects.filter(deleted=False, date__range=(d1, d2))
    if set(depts) != {'chemist', 'agrovet'}: E = E.filter(dept__in=depts)
    exp = E.aggregate(s=Sum('amount'))['s'] or Z; ec = E.count()
    return dict(sales_n=a['n'], gross_sales=total + disc, discounts=disc, refunds=refunds, net_revenue=net, cogs=cogs if complete else None,
                gross_profit=gp, margin=margin, lines=lines, costed=costed, expenses=exp, expense_count=ec,
                net_profit=(gp - exp) if gp is not None and ec else None)
