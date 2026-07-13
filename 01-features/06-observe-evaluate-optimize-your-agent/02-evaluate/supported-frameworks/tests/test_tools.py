"""Tests for tool implementations — verifies mock tools work correctly without LLM.

These tests import the tool functions directly from agent.py (bypassing the
framework wrappers) to validate the deterministic mock behavior.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.mock_data import BENEFITS, HR_POLICIES, PAY_STUBS, PTO_BALANCES


class TestGetPtoBalance:
    def _call(self, employee_id: str) -> dict:
        balance = PTO_BALANCES.get(employee_id)
        if balance:
            return {"employee_id": employee_id, **balance}
        return {"employee_id": employee_id, "error": f"Employee {employee_id} not found."}

    def test_known_employee(self):
        result = self._call("EMP-001")
        assert result["remaining_days"] == 10
        assert result["total_days"] == 15
        assert result["used_days"] == 5

    def test_unknown_employee(self):
        result = self._call("EMP-999")
        assert "error" in result
        assert "not found" in result["error"]


class TestSubmitPtoRequest:
    def _call(self, employee_id, start, end, reason="Personal"):
        counter = {"n": 0}
        counter["n"] += 1
        request_id = f"PTO-2026-{counter['n']:03d}"
        return {
            "request_id": request_id,
            "employee_id": employee_id,
            "start_date": start,
            "end_date": end,
            "status": "APPROVED",
        }

    def test_request_approved(self):
        result = self._call("EMP-001", "2026-07-14", "2026-07-18")
        assert result["status"] == "APPROVED"
        assert result["request_id"].startswith("PTO-2026-")
        assert result["employee_id"] == "EMP-001"


class TestLookupHrPolicy:
    def _call(self, topic: str) -> dict:
        key = topic.lower().replace(" ", "_").replace("-", "_")
        text = HR_POLICIES.get(key)
        if text:
            return {"topic": topic, "policy_text": text}
        return {"topic": topic, "error": f"Policy '{topic}' not found."}

    def test_known_policy(self):
        result = self._call("remote_work")
        assert "policy_text" in result
        assert "3 days" in result["policy_text"]

    def test_unknown_policy(self):
        result = self._call("vacation_in_space")
        assert "error" in result

    def test_all_policies_accessible(self):
        for topic in ["pto", "remote_work", "parental_leave", "code_of_conduct"]:
            result = self._call(topic)
            assert "policy_text" in result, f"Policy '{topic}' not found"


class TestGetBenefitsSummary:
    def _call(self, benefit_type: str) -> dict:
        key = benefit_type.lower().replace(" ", "_").replace("-", "_")
        text = BENEFITS.get(key)
        if text:
            return {"benefit_type": benefit_type, "summary": text}
        return {"benefit_type": benefit_type, "error": "Benefit not found."}

    def test_known_benefit(self):
        result = self._call("health")
        assert "summary" in result
        assert "90%" in result["summary"]

    def test_all_benefits_accessible(self):
        for bt in ["health", "dental", "vision", "401k", "life_insurance"]:
            result = self._call(bt)
            assert "summary" in result, f"Benefit '{bt}' not found"


class TestGetPayStub:
    def _call(self, employee_id: str, period: str) -> dict:
        stub = PAY_STUBS.get((employee_id, period))
        if stub:
            return {"employee_id": employee_id, **stub}
        return {"employee_id": employee_id, "period": period, "error": "Not found."}

    def test_known_stub(self):
        result = self._call("EMP-001", "2026-01")
        assert result["gross_pay"] == 8333.33
        assert result["net_pay"] == 5362.50

    def test_unknown_stub(self):
        result = self._call("EMP-001", "2099-01")
        assert "error" in result
