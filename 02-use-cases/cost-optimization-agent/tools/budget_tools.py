"""
AWS Budgets Integration Tools
Provides budget tracking, forecasting, and alerting capabilities
"""

import boto3
from datetime import datetime, timedelta
import json


def get_budget_status(budget_name: str) -> str:
    """
    Get current status and utilization of a specific budget.

    Args:
        budget_name: Name of the budget to check

    Returns:
        JSON string with budget status including utilization percentage

    Example:
        get_budget_status("MonthlyAWSBudget")
    """
    try:
        budgets_client = boto3.client("budgets")
        sts_client = boto3.client("sts")
        account_id = sts_client.get_caller_identity()["Account"]

        # Get budget details
        response = budgets_client.describe_budget(
            AccountId=account_id,
            BudgetName=budget_name,
        )

        budget = response["Budget"]

        # Extract key information
        budget_limit = float(budget["BudgetLimit"]["Amount"])
        actual_spend = float(
            budget.get("CalculatedSpend", {}).get("ActualSpend", {}).get("Amount", 0)
        )
        forecasted_spend = float(
            budget.get("CalculatedSpend", {}).get("ForecastedSpend", {}).get("Amount", 0)
        )

        utilization = (actual_spend / budget_limit * 100) if budget_limit > 0 else 0
        forecast_utilization = (forecasted_spend / budget_limit * 100) if budget_limit > 0 else 0

        results = {
            "budget_name": budget_name,
            "budget_limit": round(budget_limit, 2),
            "actual_spend": round(actual_spend, 2),
            "forecasted_spend": round(forecasted_spend, 2),
            "utilization_percent": round(utilization, 2),
            "forecast_utilization_percent": round(forecast_utilization, 2),
            "remaining_budget": round(budget_limit - actual_spend, 2),
            "time_period": budget["TimePeriod"],
            "unit": budget["BudgetLimit"]["Unit"],
            "status": "OK" if utilization < 80 else "WARNING" if utilization < 100 else "EXCEEDED",
        }

        return json.dumps(results, indent=2)

    except budgets_client.exceptions.NotFoundException:
        return json.dumps({"error": f"Budget '{budget_name}' not found"})
    except Exception as e:
        return json.dumps({"error": str(e), "message": "Failed to get budget status"})


def forecast_budget_overrun(budget_name: str) -> str:
    """
    Forecast if a budget will be exceeded based on current spending trends.

    Args:
        budget_name: Name of the budget to analyze

    Returns:
        JSON string with overrun forecast and recommendations

    Example:
        forecast_budget_overrun("MonthlyAWSBudget")
    """
    try:
        budgets_client = boto3.client("budgets")
        sts_client = boto3.client("sts")
        account_id = sts_client.get_caller_identity()["Account"]

        # Get budget details
        response = budgets_client.describe_budget(
            AccountId=account_id,
            BudgetName=budget_name,
        )

        budget = response["Budget"]
        budget_limit = float(budget["BudgetLimit"]["Amount"])
        forecasted_spend = float(
            budget.get("CalculatedSpend", {}).get("ForecastedSpend", {}).get("Amount", 0)
        )
        actual_spend = float(
            budget.get("CalculatedSpend", {}).get("ActualSpend", {}).get("Amount", 0)
        )

        # Calculate overrun risk
        overrun_amount = forecasted_spend - budget_limit
        overrun_percent = (overrun_amount / budget_limit * 100) if budget_limit > 0 else 0

        # Determine risk level
        if overrun_amount <= 0:
            risk_level = "LOW"
            message = "Budget is on track. No overrun expected."
        elif overrun_percent < 10:
            risk_level = "MEDIUM"
            message = f"Minor overrun expected: ${round(overrun_amount, 2)}"
        else:
            risk_level = "HIGH"
            message = f"Significant overrun expected: ${round(overrun_amount, 2)}"

        results = {
            "budget_name": budget_name,
            "budget_limit": round(budget_limit, 2),
            "forecasted_spend": round(forecasted_spend, 2),
            "actual_spend": round(actual_spend, 2),
            "overrun_amount": round(overrun_amount, 2),
            "overrun_percent": round(overrun_percent, 2),
            "risk_level": risk_level,
            "message": message,
            "recommendations": [],
        }

        # Add recommendations based on risk
        if risk_level in ["MEDIUM", "HIGH"]:
            results["recommendations"].append("Review and optimize high-cost services")
            results["recommendations"].append("Consider implementing cost controls")
            if risk_level == "HIGH":
                results["recommendations"].append(
                    "Immediate action required to prevent significant overrun"
                )

        return json.dumps(results, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "message": "Failed to forecast budget overrun"})


def get_all_budgets() -> str:
    """
    List all budgets and their current status.

    Returns:
        JSON string with all budgets and their utilization

    Example:
        get_all_budgets()
    """
    try:
        budgets_client = boto3.client("budgets")
        sts_client = boto3.client("sts")
        account_id = sts_client.get_caller_identity()["Account"]

        # List all budgets
        response = budgets_client.describe_budgets(AccountId=account_id)

        budgets_list = []
        for budget in response.get("Budgets", []):
            budget_limit = float(budget["BudgetLimit"]["Amount"])
            actual_spend = float(
                budget.get("CalculatedSpend", {}).get("ActualSpend", {}).get("Amount", 0)
            )
            utilization = (actual_spend / budget_limit * 100) if budget_limit > 0 else 0

            budgets_list.append(
                {
                    "name": budget["BudgetName"],
                    "limit": round(budget_limit, 2),
                    "actual_spend": round(actual_spend, 2),
                    "utilization_percent": round(utilization, 2),
                    "unit": budget["BudgetLimit"]["Unit"],
                    "status": "OK"
                    if utilization < 80
                    else "WARNING"
                    if utilization < 100
                    else "EXCEEDED",
                }
            )

        # Sort by utilization (highest first)
        budgets_list.sort(key=lambda x: x["utilization_percent"], reverse=True)

        results = {
            "total_budgets": len(budgets_list),
            "budgets": budgets_list,
            "summary": {
                "ok": sum(1 for b in budgets_list if b["status"] == "OK"),
                "warning": sum(1 for b in budgets_list if b["status"] == "WARNING"),
                "exceeded": sum(1 for b in budgets_list if b["status"] == "EXCEEDED"),
            },
        }

        return json.dumps(results, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "message": "Failed to list budgets"})


def calculate_burn_rate(time_period: str = "LAST_7_DAYS") -> str:
    """
    Calculate the current spending burn rate (daily/weekly average).

    Args:
        time_period: LAST_7_DAYS, LAST_30_DAYS, or LAST_90_DAYS

    Returns:
        JSON string with burn rate analysis

    Example:
        calculate_burn_rate("LAST_7_DAYS")
    """
    try:
        ce_client = boto3.client("ce")

        # Calculate date range
        if time_period == "LAST_7_DAYS":
            days = 7
        elif time_period == "LAST_30_DAYS":
            days = 30
        elif time_period == "LAST_90_DAYS":
            days = 90
        else:
            days = 7

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # Get daily costs
        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )

        daily_costs = []
        total_cost = 0.0

        for result in response.get("ResultsByTime", []):
            cost = float(result["Total"]["UnblendedCost"]["Amount"])
            daily_costs.append(cost)
            total_cost += cost

        # Calculate burn rate metrics
        avg_daily_burn = total_cost / len(daily_costs) if daily_costs else 0
        avg_weekly_burn = avg_daily_burn * 7
        avg_monthly_burn = avg_daily_burn * 30

        # Calculate trend (comparing first half vs second half)
        mid_point = len(daily_costs) // 2
        first_half_avg = sum(daily_costs[:mid_point]) / mid_point if mid_point > 0 else 0
        second_half_avg = (
            sum(daily_costs[mid_point:]) / (len(daily_costs) - mid_point) if mid_point > 0 else 0
        )
        trend_percent = (
            ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
        )

        results = {
            "time_period": {"start": start_date, "end": end_date, "days": days},
            "total_cost": round(total_cost, 2),
            "burn_rate": {
                "daily_average": round(avg_daily_burn, 2),
                "weekly_average": round(avg_weekly_burn, 2),
                "monthly_projection": round(avg_monthly_burn, 2),
            },
            "trend": {
                "percent_change": round(trend_percent, 2),
                "direction": "INCREASING"
                if trend_percent > 5
                else "DECREASING"
                if trend_percent < -5
                else "STABLE",
            },
            "daily_costs": [round(c, 2) for c in daily_costs],
        }

        return json.dumps(results, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "message": "Failed to calculate burn rate"})
