from django.contrib import admin
from .models import *
@admin.action(description='Publish on website')
def publish(m, r, qs): qs.update(is_public=True)
@admin.action(description='Hide from website')
def unpublish(m, r, qs): qs.update(is_public=False)
@admin.action(description='Mark data as VERIFIED (only after checking price and details)')
def verify(m, r, qs): qs.update(status='verified')
@admin.register(Product)
class PA(admin.ModelAdmin):
    list_display = ('sku', 'name', 'dept', 'category', 'sell_price', 'suggested_price', 'status', 'is_public', 'active')
    list_filter = ('dept', 'category', 'status', 'is_public', 'restricted', 'active'); search_fields = ('sku', 'name')
    list_editable = ('sell_price', 'category', 'is_public'); actions = [publish, unpublish, verify]; list_per_page = 100
admin.site.register([Profile, Enquiry])
@admin.register(AuditLog, StockMovement, Sale)
class RO(admin.ModelAdmin):
    def has_add_permission(self, r): return False
    def has_change_permission(self, r, o=None): return False
    def has_delete_permission(self, r, o=None): return False
admin.site.register(Supplier)
