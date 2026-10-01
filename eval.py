import sqlite3

from db import run_query
from llm import generate_sql
from prompt import build_generation_prompt
from sql_guard import UnsafeQueryError, validate_select_only

# Golden set: (question, ground-truth SQL). The ground-truth SQL is written by
# hand once; the model's SQL is allowed to differ in wording as long as the
# RESULT matches (result-match), which is what actually matters to a user.
GOLDEN_SET = [
    ("How many products are in the Snacks category?",
     "SELECT COUNT(*) AS n FROM products WHERE category = 'Snacks'"),
    ("What is the average unit price of Beverages?",
     "SELECT ROUND(AVG(unit_price), 2) AS avg_price FROM products WHERE category = 'Beverages'"),
    ("Which region had the most orders?",
     "SELECT region FROM sales GROUP BY region ORDER BY COUNT(*) DESC LIMIT 1"),
    ("How many orders were returned in Phuket?",
     "SELECT COUNT(*) AS n FROM sales WHERE region = 'Phuket' AND returned = 1"),
    ("What is the total quantity sold for SKU-1001?",
     "SELECT SUM(quantity) AS total FROM sales WHERE sku = 'SKU-1001'"),
    ("List the 3 most expensive products.",
     "SELECT name FROM products ORDER BY unit_price DESC LIMIT 3"),
    ("How many distinct SKUs have ever been sold in Khon Kaen?",
     "SELECT COUNT(DISTINCT sku) AS n FROM sales WHERE region = 'Khon Kaen'"),
    ("What fraction of all orders were returned, as a percentage?",
     "SELECT ROUND(100.0 * SUM(returned) / COUNT(*), 1) AS pct_returned FROM sales"),
]


def _round(v):
    return round(v, 2) if isinstance(v, float) else v


def _row_covers(expected_row: dict, actual_row: dict) -> bool:
    # The model may select extra columns beyond what the analyst asked for
    # (e.g. sku + unit_price alongside name) - that's not wrong, so we only
    # require every EXPECTED value to appear somewhere in the actual row.
    expected_values = {_round(v) for v in expected_row.values()}
    actual_values = {_round(v) for v in actual_row.values()}
    return expected_values.issubset(actual_values)


def _rows_match(expected: list[dict], actual: list[dict]) -> bool:
    if len(expected) != len(actual):
        return False
    remaining = list(actual)
    for erow in expected:
        match_idx = next((i for i, arow in enumerate(remaining) if _row_covers(erow, arow)), None)
        if match_idx is None:
            return False
        remaining.pop(match_idx)
    return True


def run_eval():
    passed = 0
    for question, gt_sql in GOLDEN_SET:
        expected = run_query(gt_sql)
        try:
            raw_sql = generate_sql(build_generation_prompt(question))
            safe_sql = validate_select_only(raw_sql)
            actual = run_query(safe_sql)
        except (UnsafeQueryError, sqlite3.Error) as e:
            print(f"[FAIL] {question!r} -> pipeline error: {e}")
            continue

        ok = _rows_match(expected, actual)
        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {question!r}")
        if not ok:
            print(f"         expected: {expected}")
            print(f"         actual:   {actual}  (sql: {safe_sql})")

    total = len(GOLDEN_SET)
    print(f"\nResult-match rate: {passed}/{total} ({100 * passed / total:.0f}%)")


if __name__ == "__main__":
    run_eval()
