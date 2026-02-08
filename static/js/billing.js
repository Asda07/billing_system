$(document).ready(function () {

    // CSRF setup for AJAX
    var csrfToken = $('[name=csrfmiddlewaretoken]').val();
    $.ajaxSetup({
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-CSRFToken', csrfToken);
        }
    });

    function showError(msg) {
        if (typeof msg === 'object') {
            msg = Array.isArray(msg) ? msg.join('\n') : JSON.stringify(msg);
        }
        $('#error-box').text(msg).removeClass('hidden');
    }

    function clearError() {
        $('#error-box').addClass('hidden').text('');
    }

    function resetPaymentSection() {
        $('#totals-section').addClass('hidden');
        $('#denomination-section').addClass('hidden');
        $('.denom-input').val(0);
        $('#paid-amount').val('');
    }

    function updatePaidAmount() {
        var total = 0;
        $('.denom-input').each(function () {
            var value = parseInt($(this).data('value')) || 0;
            var count = parseInt($(this).val()) || 0;
            total += value * count;
        });
        $('#paid-amount').val(total);
    }

    function reindexRows() {
        $('#product-table tbody .product-row').each(function (i) {
            $(this).find('td:first').text(i + 1);
        });
    }

    // Add product row
    $('#add-product').click(function () {
        var row = '<tr class="product-row">' +
            '<td class="text-center"></td>' +
            '<td><input type="text" name="product_code" placeholder="e.g. P001" style="width: 100%;"></td>' +
            '<td><input type="number" name="quantity" min="1" value="1" style="width: 100%;"></td>' +
            '<td class="text-center"><button type="button" class="btn btn-danger btn-sm remove-product">Remove</button></td>' +
            '</tr>';
        $('#product-table tbody').append(row);
        reindexRows();
        resetPaymentSection();
    });

    // Remove product row
    $(document).on('click', '.remove-product', function () {
        if ($('.product-row').length <= 1) {
            showError('At least one product is required.');
            return;
        }
        $(this).closest('tr').remove();
        reindexRows();
        resetPaymentSection();
    });

    // Reset payment section on product changes
    $(document).on('input', '[name=product_code], [name=quantity]', function () {
        resetPaymentSection();
    });

    // Calculate Total
    $('#calculate-total').click(function () {
        clearError();
        var email = $('#customer-email').val().trim();
        var items = [];

        $('.product-row').each(function () {
            var code = $(this).find('[name=product_code]').val().trim();
            var qty = parseInt($(this).find('[name=quantity]').val()) || 0;
            if (code) {
                items.push({ product_code: code, quantity: qty });
            }
        });

        if (!email) { showError('Customer email is required.'); return; }
        if (items.length === 0) { showError('Add at least one product.'); return; }

        var data = { customer_email: email, items: items };
        var orderCode = $('#order-code').val();
        if (orderCode) data.order_code = orderCode;

        var $btn = $(this);
        $btn.prop('disabled', true).text('Calculating...');

        $.ajax({
            url: '/api/calculate-total/',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function (res) {
                $('#order-code').val(res.order_code);
                $('#display-order-code').text(res.order_code);
                $('#total-before-tax').text(res.total_before_tax);
                $('#total-tax').text(res.total_tax);
                $('#total-amount').text(res.total_amount);
                $('#totals-section').removeClass('hidden');
                $('#denomination-section').removeClass('hidden');
            },
            error: function (xhr) {
                var data = xhr.responseJSON || {};
                showError(data.error || data.errors || 'Something went wrong.');
            },
            complete: function () {
                $btn.prop('disabled', false).text('Calculate Total');
            }
        });
    });

    // Update paid amount on denomination change
    $(document).on('input', '.denom-input', function () {
        updatePaidAmount();
    });

    // Generate Bill
    $('#generate-bill').click(function () {
        clearError();
        var orderCode = $('#order-code').val();
        if (!orderCode) { showError('Please calculate total first.'); return; }

        var denominations = [];
        $('.denom-input').each(function () {
            var count = parseInt($(this).val()) || 0;
            if (count > 0) {
                denominations.push({
                    value: parseInt($(this).data('value')),
                    count: count
                });
            }
        });

        if (denominations.length === 0) {
            showError('Enter at least one denomination count.');
            return;
        }

        var paidAmount = parseInt($('#paid-amount').val()) || 0;
        var totalAmount = parseFloat($('#total-amount').text()) || 0;
        if (paidAmount < totalAmount) {
            showError('Paid amount (' + paidAmount + ') is less than total amount (' + totalAmount + '). Please add more denominations.');
            return;
        }

        var $btn = $(this);
        $btn.prop('disabled', true).text('Processing...');

        $.ajax({
            url: '/api/generate-bill/',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ order_code: orderCode, denominations: denominations }),
            success: function (res) {
                window.location.href = '/bill/' + res.order_code + '/';
            },
            error: function (xhr) {
                var data = xhr.responseJSON || {};
                showError(data.error || data.errors || 'Something went wrong.');
            },
            complete: function () {
                $btn.prop('disabled', false).text('Generate Bill');
            }
        });
    });

});
