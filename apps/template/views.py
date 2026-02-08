from django.shortcuts import render, get_object_or_404

from apps.billing.models import PurchaseOrder
from core.settings import VALID_DENOMINATIONS


def billing_form(request):
    denominations = sorted(VALID_DENOMINATIONS, reverse=True)
    return render(request, 'billing/billing_form.html', {'denominations': denominations})


def billing_result(request, order_code):
    order = get_object_or_404(PurchaseOrder, code=order_code, is_draft=False)
    items = order.purchase_items.select_related('product').all()
    change_details = order.denomination_details.filter(
        type='balance'
    ).select_related('denomination')

    for item in items:
        item.subtotal = item.get_subtotal()
        item.tax_amount = item.get_tax_amount()
        item.total = item.get_total()

    return render(request, 'billing/billing_result.html', {
        'order': order,
        'items': items,
        'change_details': change_details,
    })
