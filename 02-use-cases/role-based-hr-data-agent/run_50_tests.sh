#!/usr/bin/env bash
# Run 50 comprehensive end-to-end tests

set -euo pipefail

echo "================================================================================"
echo "  Comprehensive E2E Test Suite - 50 Test Cases"
echo "================================================================================"
echo ""

PASSED=0
FAILED=0
TEST_NUM=0

run_test() {
    local test_num=$1
    local persona=$2
    local prompt=$3
    local expected_substring=$4
    local test_name=$5

    TEST_NUM=$test_num
    printf "[%2d/50] %-50s " "$test_num" "$test_name"

    output=$(python test/test_agent.py --persona "$persona" --prompt "$prompt" 2>&1 || echo "ERROR")

    if [[ "$output" == *"ERROR"* ]] || [[ "$output" == *"error"* ]] || [[ "$output" == *"failed"* ]]; then
        echo "❌ FAIL"
        ((FAILED++))
        return 1
    elif [[ -n "$expected_substring" ]] && [[ "$output" != *"$expected_substring"* ]]; then
        echo "❌ FAIL - expected '$expected_substring' not found"
        ((FAILED++))
        return 1
    else
        echo "✅ PASS"
        ((PASSED++))
        return 0
    fi
}

# === HR Manager Tests (15) ===
run_test 1 "hr-manager" "search for employees in engineering" "Engineering" "HRM-Search-Engineering"
run_test 2 "hr-manager" "find employee named John" "John" "HRM-Search-Name"
run_test 3 "hr-manager" "get profile for employee tenant-alpha-emp-001" "email" "HRM-Profile-Full"
run_test 4 "hr-manager" "show me details for tenant-alpha-emp-002" "department" "HRM-Profile-Department"
run_test 5 "hr-manager" "get salary for employee tenant-alpha-emp-001" "salary" "HRM-Compensation"
run_test 6 "hr-manager" "show compensation for tenant-alpha-emp-003" "compensation" "HRM-Compensation-Full"
run_test 7 "hr-manager" "find all senior engineers" "Senior" "HRM-Search-Role"
run_test 8 "hr-manager" "list all employees" "employee" "HRM-Multiple-Results"
run_test 9 "hr-manager" "get contact info for tenant-alpha-emp-005" "phone" "HRM-Profile-Phone"
run_test 10 "hr-manager" "what is the equity for tenant-alpha-emp-002" "" "HRM-Compensation-Equity"
run_test 11 "hr-manager" "employees in marketing" "Marketing" "HRM-Search-Marketing"
run_test 12 "hr-manager" "when did tenant-alpha-emp-004 start" "" "HRM-Profile-StartDate"
run_test 13 "hr-manager" "total compensation for tenant-alpha-emp-006" "compensation" "HRM-Compensation-Total"
run_test 14 "hr-manager" "search for developers" "Developer" "HRM-Search-Developers"
run_test 15 "hr-manager" "who manages tenant-alpha-emp-007" "" "HRM-Profile-Manager"

# === HR Specialist Tests (15) ===
run_test 16 "hr-specialist" "search for marketing employees" "Marketing" "HRS-Search-Department"
run_test 17 "hr-specialist" "get email for tenant-alpha-emp-010" "email" "HRS-Profile-Email"
run_test 18 "hr-specialist" "show salary for tenant-alpha-emp-011" "REDACTED" "HRS-Compensation-Denied"
run_test 19 "hr-specialist" "contact info for tenant-alpha-emp-001" "phone" "HRS-Profile-Phone"
run_test 20 "hr-specialist" "find Bob Smith" "" "HRS-Search-Name"
run_test 21 "hr-specialist" "what department is tenant-alpha-emp-002 in" "department" "HRS-Profile-Department"
run_test 22 "hr-specialist" "bonus for tenant-alpha-emp-003" "REDACTED" "HRS-Compensation-Bonus-Denied"
run_test 23 "hr-specialist" "find product managers" "" "HRS-Search-Role"
run_test 24 "hr-specialist" "where is tenant-alpha-emp-005 located" "" "HRS-Profile-Location"
run_test 25 "hr-specialist" "stock options for tenant-alpha-emp-006" "REDACTED" "HRS-Compensation-Equity-Denied"
run_test 26 "hr-specialist" "search for engineers" "Engineer" "HRS-Search-Engineers"
run_test 27 "hr-specialist" "start date for tenant-alpha-emp-007" "" "HRS-Profile-StartDate"
run_test 28 "hr-specialist" "who manages tenant-alpha-emp-008" "" "HRS-Profile-Manager"
run_test 29 "hr-specialist" "list all active employees" "Active" "HRS-Search-All"
run_test 30 "hr-specialist" "job title for tenant-alpha-emp-009" "" "HRS-Profile-Title"

# === Employee Tests (10) ===
run_test 31 "employee" "find my employee record" "" "EMP-Search-Self"
run_test 32 "employee" "show my profile" "email" "EMP-Profile-Self"
run_test 33 "employee" "what is my salary" "salary" "EMP-Compensation-Self"
run_test 34 "employee" "what department am I in" "department" "EMP-Profile-Department"
run_test 35 "employee" "my bonus amount" "bonus" "EMP-Compensation-Bonus"
run_test 36 "employee" "find employee tenant-alpha-emp-020" "" "EMP-Search-Others"
run_test 37 "employee" "show profile for tenant-alpha-emp-021" "" "EMP-Profile-Others"
run_test 38 "employee" "salary for tenant-alpha-emp-022" "" "EMP-Compensation-Others"
run_test 39 "employee" "when did I start working here" "" "EMP-Profile-StartDate"
run_test 40 "employee" "who is my manager" "" "EMP-Profile-Manager"

# === Admin Tests (10) ===
run_test 41 "admin" "search all employees" "employee" "ADM-Search-All"
run_test 42 "admin" "get profile for tenant-alpha-emp-001" "email" "ADM-Profile-Any"
run_test 43 "admin" "compensation for tenant-alpha-emp-002" "salary" "ADM-Compensation-Any"
run_test 44 "admin" "engineering team members" "Engineering" "ADM-Search-Department"
run_test 45 "admin" "full details for tenant-alpha-emp-003" "phone" "ADM-Profile-All-Fields"
run_test 46 "admin" "complete compensation for tenant-alpha-emp-004" "compensation" "ADM-Compensation-All-Fields"
run_test 47 "admin" "all directors" "" "ADM-Search-Role"
run_test 48 "admin" "manager for tenant-alpha-emp-005" "" "ADM-Profile-Manager"
run_test 49 "admin" "bonus for tenant-alpha-emp-006" "bonus" "ADM-Compensation-Bonus"
run_test 50 "admin" "search for remote employees" "" "ADM-Search-Location"

# Summary
echo ""
echo "================================================================================"
echo "  Test Summary"
echo "================================================================================"
echo "Total tests  : 50"
echo "Passed       : $PASSED"
echo "Failed       : $FAILED"
echo "Success rate : $(( PASSED * 100 / 50 ))%"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ $FAILED test(s) failed"
    exit 1
fi
