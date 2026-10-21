from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

DEPTS = [('chemist', 'Friends Chemist'), ('agrovet', 'Friends Agrovet')]

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    department = models.CharField(max_length=10, choices=DEPTS)
    def __str__(self): return f'{self.user} ({self.department})'

class Supplier(models.Model):
    name = models.CharField(max_length=120, unique=True)
    phone = models.CharField(max_length=40, blank=True)
    notes = models.CharField(max_length=250, blank=True)
    def __str__(self): return self.name

class Product(models.Model):
    STATUS = [('demo', 'DEMO - verify before trading'), ('unverified', 'Unverified'), ('verified', 'Verified')]
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    dept = models.CharField(max_length=10, choices=DEPTS)
    category = models.CharField(max_length=80, blank=True)
    pack = models.CharField(max_length=80, blank=True)
    supplier_ref = models.CharField(max_length=80, blank=True)
    brand = models.CharField(max_length=80, blank=True)
    strength = models.CharField(max_length=40, blank=True)
    dosage_form = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True, help_text='Product page Description tab. Blank line = new paragraph. Start a line with "* " for bullets and "## " for a heading.')
    additional_info = models.TextField(blank=True, help_text='Additional information tab. One per line as  Label: value')
    review_note = models.CharField(max_length=250, blank=True, help_text='Data check note (not shown to customers)')
    supplier = models.ForeignKey('Supplier', null=True, blank=True, on_delete=models.SET_NULL)
    buy_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sell_price = models.DecimalField('approved selling price', max_digits=12, decimal_places=2, null=True, blank=True)
    suggested_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quoted_qty = models.PositiveIntegerField(default=0, help_text='Supplier quotation qty. NOT stock.')
    reorder_level = models.PositiveIntegerField(default=5)
    status = models.CharField(max_length=12, choices=STATUS, default='unverified')
    is_public = models.BooleanField(default=False)
    restricted = models.BooleanField(default=False, help_text='Needs professional/regulatory review')
    active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='products/', blank=True)
    class Meta: ordering = ['name']; indexes = [models.Index(fields=['dept', 'active'])]
    def __str__(self): return f'{self.sku} {self.name}'
    def on_hand(self): return self.movements.aggregate(s=Sum('qty'))['s'] or 0
    def sellable(self):
        unb = self.movements.filter(batch__isnull=True).aggregate(s=Sum('qty'))['s'] or 0
        bat = (self.batches.filter(qty_remaining__gt=0).filter(Q(expiry__isnull=True) | Q(expiry__gte=timezone.localdate()))
               .aggregate(s=Sum('qty_remaining'))['s'] or 0)
        return unb + bat

class Batch(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='batches')
    batch_no = models.CharField(max_length=60)
    expiry = models.DateField(null=True, blank=True)
    qty_remaining = models.IntegerField(default=0)
    supplier = models.CharField(max_length=120, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    received = models.DateField(auto_now_add=True)
    class Meta: unique_together = ('product', 'batch_no')

class StockMovement(models.Model):
    KINDS = [('opening', 'Opening count'), ('receipt', 'Supplier receipt'), ('sale', 'Sale'),
             ('adjust', 'Adjustment'), ('writeoff', 'Write-off'), ('return', 'Return')]
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='movements')
    batch = models.ForeignKey(Batch, null=True, blank=True, on_delete=models.PROTECT)
    qty = models.IntegerField()
    kind = models.CharField(max_length=10, choices=KINDS)
    reason = models.CharField(max_length=250, blank=True)
    ref = models.CharField(max_length=60, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    is_demo = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created', '-id']

class Sale(models.Model):
    METHODS = [('cash', 'Cash'), ('mpesa', 'M-Pesa (manually recorded)'), ('card', 'Card (manually recorded)'), ('other', 'Other')]
    receipt_no = models.CharField(max_length=30, unique=True)
    dept = models.CharField(max_length=10, choices=DEPTS)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    method = models.CharField(max_length=10, choices=METHODS)
    pay_ref = models.CharField(max_length=60, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    idem_key = models.CharField(max_length=64, unique=True)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=10, default='completed', choices=[('completed', 'Completed'), ('voided', 'Voided')])
    pay_status = models.CharField(max_length=14, default='cash_received', choices=[('cash_received', 'Cash received'), ('unverified', 'Manually recorded, NOT verified')])
    void_reason = models.CharField(max_length=250, blank=True)
    is_demo = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created']

class SaleLine(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    qty = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cost_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

class Enquiry(models.Model):
    dept = models.CharField(max_length=10, choices=DEPTS)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)
    message = models.TextField(max_length=1000, blank=True)
    status = models.CharField(max_length=10, default='new', choices=[('new', 'New'), ('contacted', 'Contacted'), ('closed', 'Closed')])
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created']

class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60)
    detail = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created']
from django.core.validators import FileExtensionValidator
class SaleReturn(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='returns')
    line = models.ForeignKey(SaleLine, on_delete=models.PROTECT, related_name='returns')
    qty = models.PositiveIntegerField()
    refund = models.DecimalField(max_digits=12, decimal_places=2)
    cost_back = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reason = models.CharField(max_length=250)
    restocked = models.BooleanField(default=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)

class Expense(models.Model):
    CATS = [(c, c) for c in ('Rent', 'Salaries', 'Utilities', 'Transport', 'Licences and permits', 'Repairs', 'Marketing', 'Bank and M-Pesa charges', 'Other')]
    date = models.DateField(default=timezone.localdate)
    category = models.CharField(max_length=40, choices=CATS)
    description = models.CharField(max_length=250)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    dept = models.CharField('department (blank = shared)', max_length=10, blank=True, choices=DEPTS)
    method = models.CharField(max_length=10, choices=[('cash', 'Cash'), ('mpesa', 'M-Pesa'), ('bank', 'Bank'), ('card', 'Card'), ('other', 'Other')])
    reference = models.CharField(max_length=80, blank=True)
    attachment = models.FileField(upload_to='expenses/', blank=True, validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(default=False)
    delete_reason = models.CharField(max_length=250, blank=True)
    class Meta: ordering = ['-date', '-id']
