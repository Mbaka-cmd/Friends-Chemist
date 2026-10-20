import uuid
from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .models import Product, Profile, Sale
from .services import StockError, change_stock, record_sale

class Core(TestCase):
    def setUp(self):
        self.u = get_user_model().objects.create_user('c', password='x' * 12)
        Profile.objects.create(user=self.u, department='chemist')
        self.p = Product.objects.create(sku='A', name='A', dept='chemist', sell_price=Decimal('10'), status='verified')
        change_stock(self.p, 5, 'opening', self.u, 'count')
    def test_insufficient_rejected_and_rolled_back(self):
        with self.assertRaises(StockError): record_sale(self.u, 'chemist', [(self.p.pk, 6)], 'cash', str(uuid.uuid4()))
        self.assertEqual(self.p.on_hand(), 5); self.assertEqual(Sale.objects.count(), 0)
    def test_duplicate_submission_deducts_once(self):
        k = str(uuid.uuid4())
        a = record_sale(self.u, 'chemist', [(self.p.pk, 2)], 'cash', k); b = record_sale(self.u, 'chemist', [(self.p.pk, 2)], 'cash', k)
        self.assertEqual(a.pk, b.pk); self.assertEqual(self.p.on_hand(), 3); self.assertEqual(a.total, Decimal('20'))
    def test_expired_batch_not_sellable(self):
        change_stock(self.p, 4, 'receipt', self.u, '', 'B1', timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.p.sellable(), 5)
        with self.assertRaises(StockError): record_sale(self.u, 'chemist', [(self.p.pk, 6)], 'cash', str(uuid.uuid4()))
    def test_negative_adjustment_blocked(self):
        with self.assertRaises(StockError): change_stock(self.p, -9, 'adjust', self.u, 'oops')
    def test_department_isolation(self):
        self.client.force_login(self.u)
        self.assertEqual(self.client.get('/staff/chemist/inventory/').status_code, 200)
        self.assertEqual(self.client.get('/staff/agrovet/inventory/').status_code, 403)