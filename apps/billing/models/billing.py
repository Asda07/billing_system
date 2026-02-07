import time

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models

from apps.billing.models import BaseModel, Product, AmountDenomination


class PurchaseOrder(BaseModel):
    """Main purchase/order table"""
    code = models.CharField(max_length=25, unique=True, db_index=True, help_text='Unique identification for Order')
    customer_email = models.EmailField(db_index=True, help_text='Customer Email')
    purchase_date = models.DateTimeField(auto_now_add=True, help_text='Date of purchase')

    # Calculated amounts
    total_before_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    change_given = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Status tracking
    invoice_sent = models.BooleanField(default=False, help_text='Invoice sent or not identification')
    invoice_sent_at = models.DateTimeField(null=True, blank=True, help_text='Invoice sent at')

    class Meta:
        ordering = ['-purchase_date']
        verbose_name = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'

    def __str__(self):
        return f"Purchase Order #{self.code} - {self.customer_email} - ₹{self.total_amount}"

    def calculate_totals(self):
        """Calculate all totals from purchase items"""
        items = self.purchase_items.all()

        self.total_before_tax = sum(item.get_subtotal() for item in items)
        self.total_tax = sum(item.get_tax_amount() for item in items)
        self.total_amount = self.total_before_tax + self.total_tax

        if self.amount_paid:
            self.change_given = self.amount_paid - self.total_amount

        return {
            'total_before_tax': self.total_before_tax,
            'total_tax': self.total_tax,
            'total_amount': self.total_amount,
            'change_given': self.change_given
        }

    def save(self, *args, **kwargs):
        if not self.code:
            while True:
                # Generate a code with millisecond precision
                code = str(int(time.time() * 1000))
                if not PurchaseOrder.objects.filter(code=code).exists():
                    self.code = f"PO{code}"
                    break
                # In the unlikely event of a collision, we'll try again
                time.sleep(0.001)  # Wait for 1 millisecond before trying again

        super().save(*args, **kwargs)


class PurchaseItem(models.Model):
    """Individual items in a purchase order"""
    purchase = models.ForeignKey(PurchaseOrder, on_delete=models.RESTRICT, related_name='purchase_items',
                                 help_text='Purchase order')
    product = models.ForeignKey(Product, on_delete=models.RESTRICT, help_text='Product')
    quantity = models.IntegerField(help_text='Quantity')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text='Unit price')
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text='Tax percentage')

    class Meta:
        verbose_name = 'Purchase Item'
        verbose_name_plural = 'Purchase Items'

    def __str__(self):
        return f"{self.product.code} x {self.quantity} in Purchase #{self.purchase.id}"

    def get_subtotal(self):
        """Calculate subtotal (price × quantity) before tax"""
        return Decimal(self.quantity) * self.unit_price

    def get_tax_amount(self):
        """Calculate tax amount for this item"""
        return self.get_subtotal() * (self.tax_percentage / Decimal('100'))

    def get_total(self):
        """Calculate total including tax"""
        return self.get_subtotal() + self.get_tax_amount()

    def clean(self):
        """Validate purchase item"""
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be positive'})


class ChangeDenomination(models.Model):
    """Tracks what denominations were given as change to customer"""
    purchase = models.ForeignKey(PurchaseOrder,on_delete=models.RESTRICT,related_name='change_denominations')
    denomination = models.ForeignKey(AmountDenomination,on_delete=models.RESTRICT)
    count = models.IntegerField()

    class Meta:
        ordering = ['-denomination__value']
        unique_together = ['purchase', 'denomination']
        verbose_name = 'Change Denomination'
        verbose_name_plural = 'Change Denominations'

    def __str__(self):
        return f"₹{self.denomination.value} x {self.count} for Purchase #{self.purchase.id}"

    def get_total_value(self):
        """Calculate the total value of this denomination"""
        return self.denomination.value * self.count

    def clean(self):
        """Validate change denomination"""
        if self.count < 0:
            raise ValidationError({'count': 'Count cannot be negative'})