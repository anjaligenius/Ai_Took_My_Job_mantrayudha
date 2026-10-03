import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.orchestrator import run_orchestrator

DATASET_PATH = Path(__file__).resolve().parent / "novamart_eval_dataset.json"


def reset_test_fixtures():
    """Reset any order records mutated during evaluation runs to ensure repeatable 100% accuracy."""
    try:
        from src.backend.db import get_engine, get_session_factory, Order
        s = get_session_factory(get_engine())()
        ord_obj = s.query(Order).filter_by(order_id="ORD-007943").first()
        if ord_obj:
            ord_obj.order_status = "processing"
            ord_obj.cancellation_status = "none"
            ord_obj.refund_status = "none"
            s.commit()
        s.close()
    except Exception:
        pass


def run_evaluation():
    reset_test_fixtures()
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"\n{'#':<3} | {'CATEGORY':<28} | {'EXPECTED':<10} | {'ACTUAL':<10} | {'RESULT'}")
    print("-" * 75)

    passed = 0
    failed = 0

    for i, case in enumerate(cases, 1):
        msg = case["message"]
        cust_id = case.get("customer_id")
        expected_dec = case["expected_decision"]
        category = case["category"]

        result = run_orchestrator(user_message=msg, customer_id=cust_id)
        actual_dec = result.get("decision", "UNKNOWN")

        ok = (actual_dec == expected_dec)
        if ok:
            passed += 1
            status = "PASS [OK]"
        else:
            failed += 1
            status = f"FAIL [MISMATCH: got {actual_dec}]"

        print(f"{i:<3} | {category[:28]:<28} | {expected_dec:<10} | {actual_dec:<10} | {status}")

    total = len(cases)
    accuracy = (passed / total) * 100
    print("-" * 75)
    print(f"Total Test Cases: {total} | Passed: {passed} | Failed: {failed} | Accuracy: {accuracy:.1f}%\n")
    return failed == 0


if __name__ == "__main__":
    success = run_evaluation()
    sys.exit(0 if success else 1)
