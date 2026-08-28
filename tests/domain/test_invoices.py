from decimal import Decimal

from invoice_manager.domain.invoices import calculate_invoice_totals, calculate_line_total
from invoice_manager.domain.money import Money


def test_line_total_no_tax():
    subtotal, gst, total = calculate_line_total(
        quantity=2,
        unit_price_cents=5000,
        discount_cents=1000,
        taxable=False,
        gst_rate=Decimal("0.10"),
    )
    assert subtotal == 9000
    assert gst == 0
    assert total == 9000


def test_line_total_with_tax():
    subtotal, gst, total = calculate_line_total(
        quantity=1,
        unit_price_cents=10000,
        discount_cents=0,
        taxable=True,
        gst_rate=Decimal("0.10"),
    )
    assert subtotal == 10000
    assert gst == 1000
    assert total == 11000


def test_invoice_totals():
    from invoice_manager.domain.invoices import LineItemInput

    subtotal, gst, total = calculate_invoice_totals(
        [
            LineItemInput(quantity=1, unit_price_cents=10000, taxable=True),
            LineItemInput(quantity=2, unit_price_cents=5000, taxable=False),
        ],
        Decimal("0.10"),
    )
    assert subtotal == 20000
    assert gst == 1000
    assert total == 21000


def test_money_str():
    assert str(Money(cents=12345)) == "$123.45"
