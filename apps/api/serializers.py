from rest_framework import serializers

from apps.billing.models import PurchaseOrder, PurchaseItem, AmountDenomination, DenominationDetail


class PurchaseItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseItem
        fields = ['product', 'quantity', 'unit_price', 'tax_percentage']


class PurchaseOrderCreateSerializer(serializers.ModelSerializer):
    items = PurchaseItemCreateSerializer(many=True, write_only=True)

    class Meta:
        model = PurchaseOrder
        fields = ['customer_email', 'is_draft', 'items']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = PurchaseOrder.objects.create(**validated_data)
        self._save_items(order, items_data)
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items')
        instance.purchase_items.all().delete()
        self._save_items(instance, items_data)
        return instance

    def _save_items(self, order, items_data):
        """Create purchase items and recalculate totals."""
        for item_data in items_data:
            PurchaseItem.objects.create(purchase=order, **item_data)
        order.calculate_totals()
        order.save()


class GenerateBillSerializer(serializers.Serializer):
    paid_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    paid = serializers.ListField(child=serializers.DictField())
    change = serializers.ListField(child=serializers.DictField())

    def update(self, instance, validated_data):
        paid_data = validated_data['paid']
        change_data = validated_data['change']

        for item in instance.purchase_items.select_related('product').all():
            item.product.stock_quantity -= item.quantity
            item.product.save(update_fields=['stock_quantity'])

        denom_map = {d.value: d for d in AmountDenomination.objects.all()}

        for detail in paid_data:
            denom = denom_map.get(detail['value'])
            if denom:
                denom.available_count += detail['count']
                denom.save(update_fields=['available_count'])
            else:
                denom = AmountDenomination.objects.create(
                    value=detail['value'],
                    available_count=detail['count'],
                )
            DenominationDetail.objects.create(
                purchase=instance,
                denomination=denom,
                count=detail['count'],
                type=DenominationDetail.PAID,
            )

        for detail in change_data:
            denom = denom_map.get(detail['value'])
            denom.available_count -= detail['count']
            denom.save(update_fields=['available_count'])
            DenominationDetail.objects.create(
                purchase=instance,
                denomination=denom,
                count=detail['count'],
                type=DenominationDetail.BALANCE,
            )

        instance.amount_paid = validated_data['paid_amount']
        instance.change_given = validated_data['balance']
        instance.is_draft = False
        instance.save(update_fields=['amount_paid', 'change_given', 'is_draft'])

        return instance
