import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .models import Expense, Product, Profile, Sale
from .services import StockError, change_stock, pnl, record_sale, return_items, void_sale

class Finance(TestCase):
    def setUp(self):
        U = get_user_model()
        self.owner = U.objects.create_superuser('own', password='x' * 12)
        self.emp = U.objects.create_user('emp', password='x' * 12); Profile.objects.create(user=self.emp, department='chemist')
        self.p = Product.objects.create(sku='A', name='A', dept='chemist', sell_price=Decimal('100'), buy_price=Decimal('50'), status='verified')
        change_stock(self.p, 10, 'receipt', self.owner, '', batch_no='B1', cost=Decimal('60'))
        self.today = timezone.localdate()
    def sell(self, q=2, disc='0', key=None):
        return record_sale(self.emp, 'chemist', [(self.p.pk, q)], 'cash', key or str(uuid.uuid4()), discount=Decimal(disc))
    def test_1_2_sale_saved_and_stock_exact(self):
        s = self.sell(); self.assertTrue(s.receipt_no); self.assertEqual(s.lines.count(), 1); self.assertEqual(s.lines.first().qty, 2); self.assertEqual(self.p.on_hand(), 8)
    def test_3_reprint_creates_no_sale(self):
        s = self.sell(); self.client.force_login(self.emp)
        for _ in range(2): self.assertEqual(self.client.get(f'/staff/receipt/{s.receipt_no}/').status_code, 200)
        self.assertEqual(Sale.objects.count(), 1); self.assertEqual(self.p.on_hand(), 8)
    def test_4_insufficient_blocks_and_rolls_back(self):
        with self.assertRaises(StockError): self.sell(11)
        self.assertEqual(Sale.objects.count(), 0); self.assertEqual(self.p.on_hand(), 10)
    def test_5_duplicate_and_last_unit(self):
        k = str(uuid.uuid4()); a, b = self.sell(2, key=k), self.sell(2, key=k); self.assertEqual(a.pk, b.pk); self.assertEqual(self.p.on_hand(), 8)
        self.sell(8)
        with self.assertRaises(StockError): self.sell(1)
        self.assertEqual(self.p.on_hand(), 0)
    def test_6_7_reconcile_discount_return_expense(self):
        s = self.sell(2, '20'); self.assertEqual(s.total, Decimal('180')); self.assertEqual(s.lines.first().cost_total, Decimal('120'))
        return_items(s, self.owner, {s.lines.first().pk: 1}, 'faulty')
        Expense.objects.create(date=self.today, category='Rent', description='x', amount=Decimal('10'), dept='chemist', method='cash', created_by=self.owner)
        r = pnl(['chemist'], self.today, self.today, False)
        self.assertEqual(r['gross_sales'], Decimal('200')); self.assertEqual(r['discounts'], Decimal('20')); self.assertEqual(r['refunds'], Decimal('90'))
        self.assertEqual(r['net_revenue'], Decimal('90')); self.assertEqual(r['cogs'], Decimal('60')); self.assertEqual(r['gross_profit'], Decimal('30'))
        self.assertEqual(r['margin'], Decimal('33.33')); self.assertEqual(r['net_profit'], Decimal('20')); self.assertEqual(self.p.on_hand(), 9)
    def test_void_restores_stock_and_excludes_revenue(self):
        s = self.sell(); void_sale(s, self.owner, 'mistake')
        self.assertEqual(self.p.on_hand(), 10); self.assertEqual(pnl(['chemist'], self.today, self.today, False)['net_revenue'], 0)
    def test_8_permissions(self):
        s = self.sell(); self.client.force_login(self.emp)
        for url in ('/staff/finance/', '/staff/expenses/', '/staff/agrovet/pos/', '/staff/agrovet/sales/', '/staff/chemist/reports/'):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(self.client.post(f'/staff/receipt/{s.receipt_no}/void/', {'reason': 'x'}).status_code, 403)
        r = self.client.post('/staff/chemist/pos/sale/', data='{"key":"k1","method":"cash","discount":5,"items":[{"id":%d,"qty":1}]}' % self.p.pk, content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.client.force_login(self.owner); self.assertEqual(self.client.get('/staff/finance/').status_code, 200)