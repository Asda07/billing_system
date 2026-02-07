from django.core.exceptions import ValidationError
from django.db import models
from apps.billing.managers import ActiveManager
from core.settings import VALID_DENOMINATIONS


class BaseModel(models.Model):
    """
    Useful abstract base class that adds the concept of something being active and creation and modification dates.
    """
    is_active = models.BooleanField(default=True, help_text="Whether this item is active, use this instead of deleting")

    created_on = models.DateTimeField(auto_now_add=True, editable=False, blank=True,
                                      help_text="When this item was originally created")
    last_updated_on = models.DateTimeField(auto_now=True, editable=False, blank=True,
                                           help_text="When this item was last modified")
    is_deleted = models.BooleanField(default=False, help_text='use this for soft deleting')

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True


class Product(BaseModel):
    """Product master table"""
    code = models.CharField(max_length=50, unique=True, db_index=True, help_text="The product code")
    name = models.CharField(max_length=200, help_text="The product name")
    stock_quantity = models.IntegerField(default=0, help_text="The product stock quantity")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="The product unit price")
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="The product tax percentage")

    class Meta:
        ordering = ['name']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

    def __str__(self):
        return f"{self.name} - ({self.code})"

    def clean(self):
        """Validate product data"""
        if self.unit_price < 0:
            raise ValidationError({'unit_price': 'Price cannot be negative'})
        if self.tax_percentage < 0 or self.tax_percentage > 100:
            raise ValidationError({'tax_percentage': 'Tax percentage must be between 0 and 100'})
        if self.stock_quantity < 0:
            raise ValidationError({'stock_quantity': 'Stock quantity cannot be negative'})


class AmountDenomination(BaseModel):
    """Currency denomination master table"""
    value = models.IntegerField(unique=True, help_text="The currency denomination value")
    available_count = models.IntegerField(default=0, help_text="The amount available")

    class Meta:
        ordering = ['-value']
        verbose_name = 'Amount Denomination'
        verbose_name_plural = 'Amount Denominations'

    def __str__(self):
        return f"₹{self.value} ({self.available_count} available)"

    def clean(self):
        """Validate that denomination is in an allowed list"""
        if self.value not in VALID_DENOMINATIONS:
            raise ValidationError({
                'value': f'{self.value} is not a valid denomination. '
                         f'Valid denominations: {", ".join(map(str, VALID_DENOMINATIONS))}'
            })
        if self.available_count < 0:
            raise ValidationError({'available_count': 'Count cannot be negative'})

    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)