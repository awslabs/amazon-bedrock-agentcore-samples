"""
Deterministic dummy HR data generator.

Uses MD5 hashing of tenant_id as a seed so every tenant always gets
the same synthetic employee records — enabling repeatable DLP demos.
"""

import hashlib
import random
from datetime import datetime
from typing import Any, Dict, List, Optional


def get_dummy_employees(tenant_id: str) -> List[Dict[str, Any]]:
    """Generate consistent synthetic employees for the given tenant."""
    seed = int(hashlib.md5(tenant_id.encode(), usedforsecurity=False).hexdigest()[:8], 16)
    random.seed(seed)

    base = [
        ("John Smith",          "Engineering", "Senior Developer",   "john.smith@company.com"),
        ("Sarah Johnson",       "HR",          "HR Manager",         "sarah.johnson@company.com"),
        ("Mike Davis",          "Finance",     "Financial Analyst",  "mike.davis@company.com"),
        ("Lisa Wilson",         "Marketing",   "Marketing Director", "lisa.wilson@company.com"),
        ("David Brown",         "Engineering", "DevOps Engineer",    "david.brown@company.com"),
        ("Emily Chen",          "HR",          "HR Specialist",      "emily.chen@company.com"),
        ("Robert Taylor",       "Finance",     "Controller",         "robert.taylor@company.com"),
        ("Jennifer Lee",        "Marketing",   "Content Manager",    "jennifer.lee@company.com"),
        ("Michael Rodriguez",   "Engineering", "Software Architect", "michael.rodriguez@company.com"),
        ("Amanda White",        "HR",          "Talent Acquisition", "amanda.white@company.com"),
    ]

    employees = []
    for i, (name, dept, role, email) in enumerate(base):
        emp_id = f"{tenant_id}-emp-{i + 1:03d}"
        employees.append(
            {
                "employee_id": emp_id,
                "name": name,
                "department": dept,
                "role": role,
                "email": email,
                # PII — redacted without hr-dlp-gateway/pii scope
                "phone": f"555-{random.randint(100,999)}-{random.randint(1000,9999)}",
                "personal_phone": f"555-{random.randint(100,999)}-{random.randint(1000,9999)}",
                "emergency_contact": f"Emergency: 555-{random.randint(100,999)}-{random.randint(1000,9999)}",
                # Address — redacted without hr-dlp-gateway/address scope
                "address": f"{random.randint(100,9999)} {random.choice(['Main','Oak','Pine','Elm','Cedar'])} St",
                "city": random.choice(["Seattle", "Portland", "San Francisco", "Austin", "Denver", "Boston"]),
                "state": random.choice(["WA", "OR", "CA", "TX", "CO", "MA"]),
                "zip_code": str(random.randint(10000, 99999)),
                # Employment
                "hire_date": f"20{random.randint(18,23)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                "manager": "Jane Manager" if i > 0 else None,
                "status": "Active",
                # Compensation — redacted without hr-dlp-gateway/comp scope
                "salary": random.randint(60000, 150000),
                "bonus": random.randint(5000, 25000),
                "stock_options": random.randint(0, 10000),
                "pay_grade": random.choice(["L3", "L4", "L5", "L6", "L7"]),
                "benefits_value": random.randint(15000, 30000),
                "compensation_history": [
                    {
                        "year": 2023,
                        "salary": random.randint(55000, 140000),
                        "bonus": random.randint(3000, 20000),
                        "promotion": random.choice([True, False]),
                    },
                    {
                        "year": 2022,
                        "salary": random.randint(50000, 130000),
                        "bonus": random.randint(2000, 18000),
                        "promotion": random.choice([True, False]),
                    },
                ],
            }
        )
    return employees


def get_employee_by_id(employee_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    employees = get_dummy_employees(tenant_id)
    return next((e for e in employees if e["employee_id"] == employee_id), None)


def search_employees_by_query(query: str, tenant_id: str, max_results: int = 10) -> List[Dict[str, Any]]:
    employees = get_dummy_employees(tenant_id)
    if not query:
        return employees[:max_results]
    q = query.lower()
    return [
        e for e in employees
        if q in e["name"].lower()
        or q in e["department"].lower()
        or q in e["role"].lower()
        or q in e["email"].lower()
    ][:max_results]


def get_employee_compensation_data(employee_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    emp = get_employee_by_id(employee_id, tenant_id)
    if not emp:
        return None
    total = emp["salary"] + emp["bonus"] + emp["benefits_value"]
    return {
        "employee_id": emp["employee_id"],
        "name": emp["name"],
        "department": emp["department"],
        "role": emp["role"],
        "salary": emp["salary"],
        "bonus": emp["bonus"],
        "stock_options": emp["stock_options"],
        "pay_grade": emp["pay_grade"],
        "benefits_value": emp["benefits_value"],
        "total_compensation": total,
        "compensation_history": emp["compensation_history"],
        "last_review_date": f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        "next_review_date": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
        "performance_rating": random.choice(["Exceeds Expectations", "Meets Expectations", "Outstanding"]),
        "_data_classification": "HIGHLY_SENSITIVE_COMPENSATION_DATA",
        "_requires_scope": "hr-dlp-gateway/comp",
    }


def validate_tenant_access(employee_id: str, tenant_id: str) -> bool:
    if not employee_id.startswith(f"{tenant_id}-emp-"):
        return False
    return any(e["employee_id"] == employee_id for e in get_dummy_employees(tenant_id))
