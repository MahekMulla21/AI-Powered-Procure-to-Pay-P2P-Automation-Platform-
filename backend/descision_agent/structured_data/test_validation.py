import unittest
from datetime import date
import sys
import os
import re

# Add the backend directory to sys.path to resolve structured_data and Invoice_processing
# Also mock the decision_agent module to prevent the broken __init__.py from firing
from unittest.mock import MagicMock
sys.modules["decision_agent"] = MagicMock()
sys.modules["decision_agent.agent_main"] = MagicMock()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Import directly from modules to avoid package-level side effects
import descision_agent.structured_data.rules_engine as rules_engine
from Invoice_processing.Invoice_rule_based_extractor import _extract_total_amount

class TestSOWandTotalExtraction(unittest.TestCase):

    # ─────────────────────────────────────────────────────────────
    # SOW VALIDATION TESTS
    # ─────────────────────────────────────────────────────────────
    def test_sow_validation(self):
        # Base data
        invoice = {
            "invoice_number": "INV-001",
            "invoice_date": "2024-04-05",
            "total_amount": "138000.00",
            "sow_id": "SOW-2024"
        }
        
        # SOW row in DB
        sow_row = {
            "sow_id": "SOW-2024",
            "status": "active",
            "start_date": date(2024, 1, 1),
            "end_date": date(2025, 1, 31),
            "total_value": 200000.00
        }
        
        db = {"sow_row": sow_row, "invoice_row": None}
        
        # 1. Valid case (Invoice date within SOW)
        reasons = rules_engine.run(invoice, db)
        self.assertEqual(len(reasons), 0, f"Valid invoice should pass. Reasons found: {reasons}")

        # 2. Expired case (Invoice date after SOW end)
        invoice["invoice_date"] = "2025-02-15"
        reasons = rules_engine.run(invoice, db)
        codes = [r["code"] for r in reasons]
        self.assertIn("SOW_DATE_INVALID", codes, "Expired SOW should fail")

        # 3. Future case (Invoice date before SOW start)
        invoice["invoice_date"] = "2023-12-15"
        reasons = rules_engine.run(invoice, db)
        codes = [r["code"] for r in reasons]
        self.assertIn("SOW_DATE_INVALID", codes, "Future SOW should fail")

        # 4. Historical case (Invoice from 2024 processed today)
        invoice["invoice_date"] = "2024-05-01"
        reasons = rules_engine.run(invoice, db)
        self.assertEqual(len(reasons), 0, "Historical invoice should pass if valid then")

    # ─────────────────────────────────────────────────────────────
    # TOTAL AMOUNT EXTRACTION TESTS
    # ─────────────────────────────────────────────────────────────
    def test_total_amount_extraction(self):
        test_cases = [
            ("$138,000.00", "138000.00"),
            ("USD 120,000.00", "120000.00"),
            ("18,000.00", "18000.00"),
            ("1,250,999.50", "1250999.50"),
            ("Total Amount (USD) | $138,000.00", "138000.00"),
            ("TOTAL INVOICE AMOUNT: $138,000.00", "138000.00"),
            ("Invoice Total | 138,000.00", "138000.00"),
        ]

        for input_text, expected in test_cases:
            result = _extract_total_amount(input_text)
            self.assertEqual(result, expected, f"Failed for input: {input_text}")

        # Test false positive prevention
        self.assertIsNone(_extract_total_amount("Year: 2024"), "Should not pick up years")
        
        # Test validation > 0
        self.assertIsNone(_extract_total_amount("Total: 0.00"), "Should not pick up zero")
        self.assertIsNone(_extract_total_amount("Total: -100.00"), "Should not pick up negative")

if __name__ == "__main__":
    unittest.main()
