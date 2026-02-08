from django.contrib import admin
from apps.billing.models.masters import Product,AmountDenomination

admin.site.register([Product,AmountDenomination])