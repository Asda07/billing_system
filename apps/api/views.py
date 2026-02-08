from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.serializers import PurchaseOrderCreateSerializer, GenerateBillSerializer
from apps.api.utils import validate_balance_possible, send_invoice_email
from apps.billing.models import Product, PurchaseOrder
from core.settings import VALID_DENOMINATIONS

# List and Retrieve API's for data preload

class AmountDenominationListView(APIView):
    def get(self, request):
        return Response({'data': sorted(VALID_DENOMINATIONS, reverse=True)}, status=status.HTTP_200_OK)


# Process Flow API's

class CalculateTotalView(APIView):
    """
    Validates stock, creates a draft order with current prices, and returns calculated totals.
    """

    def post(self, request):
        customer_email = request.data.get('customer_email', '').strip()
        items_data = request.data.get('items', [])
        errors = {}

        if not customer_email:
            errors['customer_email'] = 'Customer email is required.'

        if not items_data:
            errors['items'] = 'At least one item is required.'

        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

        # Check for duplicate product codes in request
        product_codes = [item.get('product_code') for item in items_data]
        if len(product_codes) != len(set(product_codes)):
            return Response(
                {'error': 'Duplicate product entries found. Adjust quantity instead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        products = Product.objects.filter(code__in=product_codes)
        product_map = {p.code: p for p in products}
        missing_codes = set(product_codes) - set(product_map.keys())
        if missing_codes:
            return Response(
                {'error': f"Products not found for codes: {', '.join(missing_codes)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Validate each item's quantity and stock ---
        stock_errors = []
        for item in items_data:
            product = product_map[item['product_code']]
            quantity = item.get('quantity', 0)

            if not isinstance(quantity, int) or quantity <= 0:
                stock_errors.append(f"Invalid quantity for '{product.name}' ({product.code}).")
                continue

            if product.stock_quantity < quantity:
                stock_errors.append(
                    f"Insufficient stock for '{product.name}' ({product.code}). "
                    f"Available: {product.stock_quantity}, Requested: {quantity}"
                )

        if stock_errors:
            return Response({'errors': stock_errors}, status=status.HTTP_400_BAD_REQUEST)

        serializer_items = []
        for item_data in items_data:
            product = product_map[item_data['product_code']]
            serializer_items.append({
                'product': product.id,
                'quantity': item_data['quantity'],
                'unit_price': str(product.unit_price),
                'tax_percentage': str(product.tax_percentage),
            })

        # --- Check if updating an existing draft ---
        order_code = request.data.get('order_code')
        order = None

        if order_code:
            try:
                order = PurchaseOrder.objects.get(code=order_code, is_draft=True)
            except PurchaseOrder.DoesNotExist:
                return Response(
                    {'error': f"Draft order '{order_code}' not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer_data = {
            'customer_email': customer_email,
            'is_draft': True,
            'items': serializer_items,
        }

        if order:
            serializer = PurchaseOrderCreateSerializer(order, data=serializer_data)
        else:
            serializer = PurchaseOrderCreateSerializer(data=serializer_data)

        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            order = serializer.save()

        return Response(
            {
                'order_id': order.id,
                'order_code': order.code,
                'customer_email': order.customer_email,
                'total_before_tax': str(order.total_before_tax),
                'total_tax': str(order.total_tax),
                'total_amount': str(order.total_amount),
            },
            status=status.HTTP_201_CREATED if not order_code else status.HTTP_200_OK,
        )


class GenerateBillView(APIView):
    """
    Validates stock + denomination change, finalizes the draft order,
    """

    def post(self, request):
        order_code = request.data.get('order_code')
        paid_denominations = request.data.get('denominations', [])

        if not order_code:
            return Response({'error': 'Order code is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not paid_denominations:
            return Response({'error': 'Denomination details are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = PurchaseOrder.objects.get(code=order_code, is_draft=True)
        except PurchaseOrder.DoesNotExist:
            return Response(
                {'error': f"Draft order '{order_code}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        stock_errors = []
        purchase_items = order.purchase_items.select_related('product').all()

        for item in purchase_items:
            product = item.product
            if product.stock_quantity < item.quantity:
                stock_errors.append(
                    f"Insufficient stock for '{product.name}' ({product.code}). "
                    f"Available: {product.stock_quantity}, Requested: {item.quantity}"
                )

        if stock_errors:
            return Response({'errors': stock_errors}, status=status.HTTP_400_BAD_REQUEST)

        result = validate_balance_possible(order, paid_denominations)

        if not result['success']:
            return Response(
                {'error': result['message']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = GenerateBillSerializer(order, data={
            'paid_amount': str(result['paid_amount']),
            'balance': str(result['balance']),
            'paid': result['paid'],
            'change': result['change'],
        })
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            order = serializer.save()

        # Send invoice email in background — doesn't block the response and for this simple billing system.
        # For production grade we can go with celery
        send_invoice_email(order)

        items_response = []
        for item in purchase_items:
            items_response.append({
                'product_code': item.product.code,
                'product_name': item.product.name,
                'unit_price': str(item.unit_price),
                'quantity': item.quantity,
                'tax_percentage': str(item.tax_percentage),
                'subtotal': str(item.get_subtotal()),
                'tax_amount': str(item.get_tax_amount()),
                'total': str(item.get_total()),
            })

        paid_response = [
            {'value': d['value'], 'count': d['count']}
            for d in result['paid']
        ]
        change_response = [
            {'value': d['value'], 'count': d['count']}
            for d in result['change']
        ]

        return Response(
            {
                'order_code': order.code,
                'customer_email': order.customer_email,
                'items': items_response,
                'total_before_tax': str(order.total_before_tax),
                'total_tax': str(order.total_tax),
                'total_amount': str(order.total_amount),
                'amount_paid': str(order.amount_paid),
                'change_given': str(order.change_given),
                'paid_denominations': paid_response,
                'change_denominations': change_response,
            },
            status=status.HTTP_200_OK,
        )
