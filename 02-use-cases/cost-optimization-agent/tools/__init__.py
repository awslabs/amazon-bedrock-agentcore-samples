"""
Cost Optimization Agent Tools
"""

from .cost_explorer_tools import (
    get_cost_and_usage,
    get_cost_forecast,
    detect_cost_anomalies,
    get_service_costs,
)

from .budget_tools import (
    get_budget_status,
    forecast_budget_overrun,
    get_all_budgets,
    calculate_burn_rate,
)

from .optimization_tools import (
    analyze_savings_plans_coverage,
    identify_idle_resources,
    recommend_model_selection,
    calculate_caching_roi,
    analyze_rightsizing_opportunities,
)

from .memory_tools import (
    store_cost_baseline,
    get_cost_baseline,
    update_optimization_history,
    get_team_preferences,
)

__all__ = [
    # Cost Explorer
    "get_cost_and_usage",
    "get_cost_forecast",
    "detect_cost_anomalies",
    "get_service_costs",
    # Budget
    "get_budget_status",
    "forecast_budget_overrun",
    "get_all_budgets",
    "calculate_burn_rate",
    # Optimization
    "analyze_savings_plans_coverage",
    "identify_idle_resources",
    "recommend_model_selection",
    "calculate_caching_roi",
    "analyze_rightsizing_opportunities",
    # Memory
    "store_cost_baseline",
    "get_cost_baseline",
    "update_optimization_history",
    "get_team_preferences",
]
