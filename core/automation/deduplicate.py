"""Merge duplicate line items within a billing batch.

Consolidation step for the browser-automation pipeline: rows that share an
``item_name`` inside one billing batch are collapsed into a single row whose
quantity, line total and discount are summed and whose unit price becomes the
quantity-weighted average of the merged rows. The surviving row's
``description`` is tagged with ``[Merged X duplicate entries]``.

A *billing batch* is one invoice's ``items`` list (the ``empty_invoice()``
shape from core/schema.py). This module accepts a single invoice dict, a list
of invoice dicts, or a bare list of item rows, and dedupes each batch on its
own -- items are never merged across batches.

Values are read tolerantly (thousands separators, currency symbols and blanks
are ignored) and written back as compact strings, matching how the verify form
in core/views.py stores every field.

Usage:
    python core/automation/deduplicate.py INPUT.json [-o OUTPUT.json]
"""

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation


# Characters stripped from a numeric field before parsing (currency, grouping).
_STRIP_CHARS = (",", "₦", "$", " ", "\t")


def _num(value) -> Decimal:
    """Parse a quantity/money field into a Decimal; unparseable -> 0.

    Handles ints/floats, and strings carrying thousands separators or a
    currency symbol. Blank or garbage values degrade to Decimal(0) so a single
    dirty row never aborts a merge.
    """
    if value is None:
        return Decimal(0)
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    cleaned = str(value)
    for ch in _STRIP_CHARS:
        cleaned = cleaned.replace(ch, "")
    if not cleaned:
        return Decimal(0)
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal(0)


def _fmt(value: Decimal) -> str:
    """Render a Decimal back to a compact, non-exponent string.

    Whole numbers come out without a decimal point ("5000"); fractional
    results keep only significant decimals ("7333.33").
    """
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


def _merge_group(rows: list) -> dict:
    """Combine rows sharing an item_name into one consolidated row.

    quantity / line_total / discount are summed; unit_price is the
    quantity-weighted average of the group. Non-numeric fields (item_name,
    and the base description) are taken from the first row in the batch.
    """
    total_qty = sum((_num(r.get("quantity")) for r in rows), Decimal(0))
    total_line = sum((_num(r.get("line_total")) for r in rows), Decimal(0))
    total_discount = sum((_num(r.get("discount")) for r in rows), Decimal(0))

    # Weighted average unit price = sum(unit_price * qty) / sum(qty).
    weighted = sum(
        (_num(r.get("unit_price")) * _num(r.get("quantity")) for r in rows),
        Decimal(0),
    )
    if total_qty:
        avg_unit_price = (weighted / total_qty).quantize(Decimal("0.01"))
    else:
        # No quantities to weight by -> fall back to a plain mean of prices.
        prices = [_num(r.get("unit_price")) for r in rows]
        avg_unit_price = (sum(prices, Decimal(0)) / len(prices)).quantize(Decimal("0.01"))

    merged = dict(rows[0])  # preserve first row's item_name / description / order
    merged["quantity"] = _fmt(total_qty)
    merged["unit_price"] = _fmt(avg_unit_price)
    merged["discount"] = _fmt(total_discount)
    merged["line_total"] = _fmt(total_line)

    # X = number of rows folded into this one (group size).
    note = f"[Merged {len(rows)} duplicate entries]"
    base_description = str(merged.get("description", "")).strip()
    merged["description"] = f"{base_description} {note}".strip()
    return merged


def deduplicate_items(items: list) -> list:
    """Return a new items list with same-item_name rows merged.

    Grouping key is the trimmed, case-folded item_name; first-seen order is
    preserved. Rows with a blank item_name are passed through untouched and
    never merged together.
    """
    if not isinstance(items, list):
        return items

    groups = {}      # key -> list of rows
    layout = []      # ordered slots: ("group", key) | ("row", row)

    for row in items:
        name = str(row.get("item_name", "")).strip() if isinstance(row, dict) else ""
        if not name:
            layout.append(("row", row))
            continue
        key = name.casefold()
        if key not in groups:
            groups[key] = []
            layout.append(("group", key))
        groups[key].append(row)

    result = []
    for kind, payload in layout:
        if kind == "row":
            result.append(payload)
        elif len(groups[payload]) > 1:
            result.append(_merge_group(groups[payload]))
        else:
            result.append(dict(groups[payload][0]))  # lone row, unchanged
    return result


def deduplicate_invoice(invoice: dict) -> dict:
    """Dedupe one invoice dict's items, returning a new dict."""
    if not isinstance(invoice, dict):
        return invoice
    result = dict(invoice)
    if isinstance(result.get("items"), list):
        result["items"] = deduplicate_items(result["items"])
    return result


def deduplicate(data):
    """Entry point.

    Accepts a single invoice dict, a list of invoice dicts (each its own
    batch), or a bare list of item rows, and returns the same shape with
    duplicates merged.
    """
    if isinstance(data, list):
        # A list of invoice dicts -> dedupe each; otherwise a bare items list.
        if all(isinstance(x, dict) and "items" in x for x in data):
            return [deduplicate_invoice(inv) for inv in data]
        return deduplicate_items(data)
    if isinstance(data, dict) and "items" in data:
        return deduplicate_invoice(data)
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge duplicate line items within each billing batch.",
    )
    parser.add_argument("input", help="Path to the extracted invoice JSON.")
    parser.add_argument(
        "-o", "--output",
        help="Write result here (defaults to stdout).",
    )
    parser.add_argument(
        "--indent", type=int, default=2, help="JSON indent width (default: 2).",
    )
    args = parser.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    result = deduplicate(data)
    text = json.dumps(result, indent=args.indent, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
