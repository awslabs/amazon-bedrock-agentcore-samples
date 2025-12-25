"""
AWS Cost Explorer Integration Tools
Provides real-time cost data, forecasting, and anomaly detection
"""

import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json


def get_cost_and_usage(
    start_date: str,
    end_date: str,
    granularity: str = "DAILY",
    group_by: Optional[List[Dict]] = None,
    filter_expression: Optional[Dict] = None,
) -> str:
    """
    Retrieve AWS cost and usage data for a specified time period.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        granularity: Time granularity - DAILY, MONTHLY, or HOURLY
        group_by: List of grouping dimensions (e.g., [{"Type": "DIMENSION", "Key": "SERVICE"}])
        filter_expression: Cost Explorer filter expression

    Returns:
        JSON string with cost and usage data

    Example:
        get_cost_and_usage("2024-01-01", "2024-01-31", "DAILY", [{"Type": "DIMENSION", "Key": "SERVICE"}])
    """
    try:
        ce_client = boto3.client("ce")

        # Build request parameters
        params = {
            "TimePeriod": {"Start": start_date, "End": end_date},
            "Granularity": granularity,
            "Metrics": ["UnblendedCost", "UsageQuantity"],
        }

        if group_by:
            params["GroupBy"] = group_by

        if filter_expression:
            params["Filter"] = filter_expression

        # Get cost and usage
        response = ce_client.get_cost_and_usage(**params)

        # Format response
        results = {
            "time_period": {"start": start_date, "end": end_date},
            "granularity": granularity,
            "results": [],
            "total_cost": 0.0,
        }

        for result in response.get("ResultsByTime", []):
            period_data = {
                "start": result["TimePeriod"]["Start"],
                "end": result["TimePeriod"]["End"],
                "groups": [],
            }

            if "Groups" in result:
                for group in result["Groups"]:
                    cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                    period_data["groups"].append(
                        {
                            "keys": group["Keys"],
                            "cost": round(cost, 2),
                            "unit": group["Metrics"]["UnblendedCost"]["Unit"],
                        }
                    )
                    results["total_cost"] += cost
            else:
                cost = float(result["Total"]["UnblendedCost"]["Amount"])
                period_data["total_cost"] = round(cost, 2)
                period_data["unit"] = result["Total"]["UnblendedCost"]["Unit"]
                results["total_cost"] += cost

            results["results"].append(period_data)

        results["total_cost"] = round(results["total_cost"], 2)

        return json.dumps(results, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "message": "Failed to retrieve cost data"})


def get_cost_forecast(
    start_date: str,
    end_date: str,
    metric: str = "UNBLENDED_COST",
    granularity: str = "MONTHLY",
) -> str:
    """
    Get cost forecast for a future time period based on historical data.

    Args:
        start_date: Forecast start date in YYYY-MM-DD format
        end_date: Forecast end date in YYYY-MM-DD format
        metric: Metric to forecast (UNBLENDED_COST, BLENDED_COST, etc.)
        granularity: DAILY or MONTHLY

    Returns:
        JSON string with forecast data including prediction intervals

    Example:
        get_cost_forecast("2024-02-01", "2024-02-29", "UNBLENDED_COST", "MONTHLY")
    """
    try:
        ce_client = boto3.client("ce")

        response = ce_client.get_cost_forecast(
            TimePeriod={"Start": start_date, "End": end_date},
            Metric=metric,
            Granularity=granularity,
            PredictionIntervalLevel=80,  # 80% confidence interval
        )

        results = {
            "time_period": {"start": start_date, "end": end_date},
            "metric": metric,
            "granularity": granularity,
            "total_forecast": round(float(response["Total"]["Amount"]), 2),
            "unit": response["Total"]["Unit"],
            "forecasts": [],
        }

        for forecast in response.get("ForecastResultsByTime", []):
            results["forecasts"].append(
                {
                    "start": forecast["TimePeriod"]["Start"],
                    "end": forecast["TimePeriod"]["End"],
                    "mean_value": round(float(forecast["MeanValue"]), 2),
                    "prediction_interval_lower": round(
                        float(forecast["PredictionIntervalLowerBound"]), 2
                    ),
                    "prediction_interval_upper": round(
                        float(forecast["PredictionIntervalUpperBound"]), 2
                    ),
                }
            )

        return json.dumps(results, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "message": "Failed to generate forecast"})


def detect_cost_anomalies(lookback_days: int = 7) -> str:
    """
    Detect cost anomalies using AWS Cost Anomaly Detection.

    Args:
        lookback_days: Number of days to look back for anomalies (default: 7)

    Returns:
        JSON string with detected anomalies and their details

    Example:
        detect_cost_anomalies(7)
    """
    try:
        ce_client = boto3.client("ce")

        # Calculate date range
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        # Get anomalies
        response = ce_client.get_anomalies(
            DateInterval={"StartDate": start_date, "EndDate": end_date},
            MaxResults=100,
        )

        anomalies = []
        for anomaly in response.get("Anomalies", []):
            anomaly_data = {
                "anomaly_id": anomaly["AnomalyId"],
                "anomaly_score": round(anomaly["AnomalyScore"]["CurrentScore"], 2),
                "impact": {
                    "max_impact": round(float(anomaly["Impact"]["MaxImpact"]), 2),
                    "total_impact": round(float(anomaly["Impact"]["TotalImpact"]), 2),
                },
                "start_date": anomaly["AnomalyStartDate"],
                "end_date": anomaly.get("AnomalyEndDate", "Ongoing"),
                "dimension_value": anomaly.get("DimensionValue", "Unknown"),
                "root_causes": [],
            }

            # Extract root causes
            for root_cause in anomaly.get("RootCauses", []):
                anomaly_data["root_causes"].append(
                    {
                        "service": root_cause.get("Service", "Unknown"),
                        "region": root_cause.get("Region", "Unknown"),
                        "usage_type": root_cause.get("UsageType", "Unknown"),
                    }
                )

            anomalies.append(anomaly_data)

        results = {
            "time_period": {"start": start_date, "end": end_date},
            "anomaly_count": len(anomalies),
            "anomalies": sorted(anomalies, key=lambda x: x["impact"]["total_impact"], reverse=True),
        }

        return json.dumps(results, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "message": "Failed to detect anomalies"})


def get_service_costs(
    service_name: str,
    time_period: str = "LAST_30_DAYS",
    granularity: str = "DAILY",
) -> str:
    """
    Get detailed cost breakdown for a specific AWS service.

    Args:
        service_name: AWS service name (e.g., "Amazon Elastic Compute Cloud - Compute")
        time_period: LAST_7_DAYS, LAST_30_DAYS, LAST_90_DAYS, or custom date range
        granularity: DAILY or MONTHLY

    Returns:
        JSON string with service-specific cost data

    Example:
        get_service_costs("Amazon Bedrock", "LAST_30_DAYS", "DAILY")
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
            days = 30

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # Get costs for specific service
        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity=granularity,
            Metrics=["UnblendedCost", "UsageQuantity"],
            Filter={
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": [service_name],
                }
            },
            GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
        )

        results = {
            "service": service_name,
            "time_period": {"start": start_date, "end": end_date},
            "granularity": granularity,
            "total_cost": 0.0,
            "usage_types": {},
        }

        for result in response.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                usage_type = group["Keys"][0]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])

                if usage_type not in results["usage_types"]:
                    results["usage_types"][usage_type] = 0.0

                results["usage_types"][usage_type] += cost
                results["total_cost"] += cost

        # Round and sort by cost
        results["total_cost"] = round(results["total_cost"], 2)
        results["usage_types"] = {
            k: round(v, 2)
            for k, v in sorted(
                results["usage_types"].items(),
                key=lambda x: x[1],
                reverse=True,
            )
        }

        return json.dumps(results, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "message": f"Failed to get costs for {service_name}"})
