"""Tests for shared mock data — ensures consistency across framework samples."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.mock_data import (
    ASSERTIONS,
    BENEFITS,
    EVAL_TURNS,
    EXPECTED_RESPONSES,
    EXPECTED_TRAJECTORY,
    HR_POLICIES,
    PAY_STUBS,
    PTO_BALANCES,
    SYSTEM_PROMPT,
)


class TestMockDataCompleteness:
    def test_pto_balances_have_required_employees(self):
        assert "EMP-001" in PTO_BALANCES
        assert "EMP-002" in PTO_BALANCES
        assert "EMP-042" in PTO_BALANCES

    def test_pto_balance_fields(self):
        for emp_id, balance in PTO_BALANCES.items():
            assert "total_days" in balance
            assert "used_days" in balance
            assert "remaining_days" in balance
            assert balance["remaining_days"] == balance["total_days"] - balance["used_days"]

    def test_hr_policies_have_all_topics(self):
        expected_topics = {"pto", "remote_work", "parental_leave", "code_of_conduct"}
        assert set(HR_POLICIES.keys()) == expected_topics

    def test_benefits_have_all_types(self):
        expected = {"health", "dental", "vision", "401k", "life_insurance"}
        assert set(BENEFITS.keys()) == expected

    def test_pay_stubs_exist(self):
        assert len(PAY_STUBS) >= 2
        for key, stub in PAY_STUBS.items():
            assert "gross_pay" in stub
            assert "net_pay" in stub
            assert stub["net_pay"] < stub["gross_pay"]

    def test_system_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100
        assert "HR" in SYSTEM_PROMPT or "hr" in SYSTEM_PROMPT.lower()


class TestEvalScenarios:
    def test_eval_turns_count(self):
        assert len(EVAL_TURNS) == 3

    def test_expected_responses_match_turns(self):
        assert len(EXPECTED_RESPONSES) == len(EVAL_TURNS)

    def test_expected_trajectory_matches_turns(self):
        assert len(EXPECTED_TRAJECTORY) == len(EVAL_TURNS)

    def test_assertions_not_empty(self):
        assert len(ASSERTIONS) >= 3

    def test_trajectory_tools_are_valid(self):
        valid_tools = {"get_pto_balance", "submit_pto_request", "lookup_hr_policy",
                       "get_benefits_summary", "get_pay_stub"}
        for tool in EXPECTED_TRAJECTORY:
            assert tool in valid_tools, f"Unknown tool in trajectory: {tool}"


class TestNoRealPII:
    def test_employee_ids_are_synthetic(self):
        for emp_id in PTO_BALANCES:
            assert emp_id.startswith("EMP-")
            assert len(emp_id) <= 10

    def test_no_real_names_in_policies(self):
        all_text = " ".join(HR_POLICIES.values())
        assert "@" not in all_text
        assert "555-" not in all_text

    def test_no_real_ssn_or_account_numbers(self):
        all_text = " ".join(str(v) for v in PAY_STUBS.values())
        assert "SSN" not in all_text
        assert "account" not in all_text.lower() or "401k" in all_text.lower()
