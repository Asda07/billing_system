from django.shortcuts import render, get_object_or_404

from apps.billing.models import PurchaseOrder, PurchaseItem
from core.settings import VALID_DENOMINATIONS


def billing_form(request):
    denominations = sorted(VALID_DENOMINATIONS, reverse=True)
    return render(request, 'billing/billing_form.html', {'denominations': denominations})


def purchase_history(request):
    email = request.GET.get('email', '').strip()
    orders = []
    selected_order = None
    items = []

    if email:
        orders = PurchaseOrder.objects.filter(
            customer_email=email, is_draft=False
        ).order_by('-purchase_date')

        order_code = request.GET.get('order')
        if order_code:
            selected_order = get_object_or_404(
                PurchaseOrder, code=order_code, customer_email=email, is_draft=False
            )
            items = selected_order.purchase_items.select_related('product').all()
            for item in items:
                item.subtotal = item.get_subtotal()
                item.tax_amount = item.get_tax_amount()
                item.total = item.get_total()

    return render(request, 'billing/purchase_history.html', {
        'email': email,
        'orders': orders,
        'selected_order': selected_order,
        'items': items,
    })


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
