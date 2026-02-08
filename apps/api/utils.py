from decimal import Decimal

from apps.billing.models import AmountDenomination
from core.settings import VALID_DENOMINATIONS


def _find_change(denominations, amount):
    result = []

    def calculate_possibilities(index, remaining):
        if remaining == 0:
            return True

        if index >= len(denominations):
            return False

        value, available, denom_id = denominations[index]
        max_use = min(remaining // value, available)

        for use_count in range(max_use, -1, -1):
            if use_count > 0:
                result.append({
                    'denomination_id': denom_id,
                    'value': value,
                    'count': use_count,
                })

            if calculate_possibilities(index + 1, remaining - (value * use_count)):
                return True

            if use_count > 0:
                result.pop()

        return False

    if calculate_possibilities(0, amount):
        return result
    return None


def validate_balance_possible(order_instance, paid_denomination_data):
    """
    Checks if the shop can return exact change using available denominations.
    """
    # Validate denomination values against allowed list
    invalid_values = [item['value'] for item in paid_denomination_data if item['value'] not in VALID_DENOMINATIONS]
    if invalid_values:
        return {
            'success': False,
            'message': (
                f"Invalid denomination values: {', '.join(map(str, invalid_values))}. "
                f"Valid denominations: {', '.join(map(str, sorted(VALID_DENOMINATIONS, reverse=True)))}"
            ),
        }

    paid_amount = sum(item['value'] * item['count'] for item in paid_denomination_data)
    paid_amount = Decimal(str(paid_amount))
    order_total = order_instance.total_amount

    balance = paid_amount - order_total

    if balance < 0:
        return {
            'success': False,
            'message': (
                f"Paid amount ({paid_amount}) is less than the total ({order_total}). "
                f"Customer needs to pay {order_total - paid_amount} more."
            ),
        }

    available_denoms = AmountDenomination.objects.all()
    denom_map = {d.value: d for d in available_denoms}
    paid_details = []
    for item in paid_denomination_data:
        denom = denom_map.get(item['value'])
        paid_details.append({
            'denomination_id': denom.id if denom else None,
            'value': item['value'],
            'count': item['count'],
        })

    if balance == 0:
        return {
            'success': True,
            'paid_amount': paid_amount,
            'balance': Decimal('0'),
            'paid': paid_details,
            'change': [],
        }

    # Build working stock: shop's current stock + customer's paid cash
    paid_by_value = {item['value']: item['count'] for item in paid_denomination_data}
    working_stock = {}

    for denom in available_denoms:
        working_stock[denom.value] = denom.available_count + paid_by_value.get(denom.value, 0)

    # Customer may pay with denominations not yet in DB
    for value, count in paid_by_value.items():
        if value not in working_stock:
            working_stock[value] = count

    denom_list = [
        (value, stock, denom_map[value].id if value in denom_map else None)
        for value, stock in sorted(working_stock.items(), reverse=True)
        if stock > 0
    ]

    change_breakdown = _find_change(denom_list, int(balance))

    if change_breakdown is None:
        min_value = min(working_stock.keys()) if working_stock else 0
        suggestion = None

        for extra in range(1, min_value + 1):
            new_balance = int(balance) + extra
            if _find_change(denom_list, new_balance) is not None:
                suggestion = extra
                break

        if suggestion:
            return {
                'success': False,
                'message': (
                    f"Cannot give exact change for balance {int(balance)}. "
                    f"If customer pays {suggestion} more, shop can return {int(balance) + suggestion} as change."
                ),
                'suggestion': suggestion,
            }

        return {
            'success': False,
            'message': (
                f"Cannot give exact change for balance {int(balance)}. "
                f"Customer needs to pay exact amount or provide different denominations."
            ),
        }

    return {
        'success': True,
        'paid_amount': paid_amount,
        'balance': balance,
        'paid': paid_details,
        'change': change_breakdown,
    }
