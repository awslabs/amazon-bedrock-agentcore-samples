"""Deterministic cost estimation.

Two principles, both deliberate:

1. All arithmetic happens here, in Python. No language model computes money. When
   this validator is later wired to an LLM front end, the model's job is to pick
   usage inputs; multiplication stays in code where it can be unit-tested.

2. The estimate splits into a baseline and a compliance premium. The premium is
   the cost of the controls the segment and industry rules demand. Showing it
   separately is what lets a partner answer "what is compliance costing me?"
   instead of arguing with one opaque total.
"""

from __future__ import annotations

from . import catalog
from .models import CostEstimate, CostLine, DesignGraph, Node

PREMIUM_FLAT = {
    "customer_managed_key",
    "waf_enabled",
    "guardrails_enabled",
    "rotation_enabled",
}


def _driver_labels(service_id: str) -> dict[str, str]:
    drivers = catalog.service_defs()[service_id].get("cost_drivers", [])
    return {d["id"]: d["label"] for d in drivers}


def _baseline_lines(node: Node, rates: dict[str, float]) -> list[CostLine]:
    labels = _driver_labels(node.service_id)
    lines: list[CostLine] = []
    for driver, quantity in node.usage.items():
        rate = rates.get(driver)
        if rate is None:
            continue
        lines.append(
            CostLine(
                node_id=node.service_id,
                node_name=node.name,
                driver=driver,
                driver_label=labels.get(driver, driver),
                quantity=float(quantity),
                unit_rate=float(rate),
                monthly_cost=round(float(quantity) * float(rate), 2),
            )
        )
    return lines


def _premium_lines(
    node: Node, rates: dict[str, float], control_costs: dict
) -> list[CostLine]:
    lines: list[CostLine] = []
    definition = catalog.service_defs()[node.service_id]

    # Multi-AZ duplicates the drivers the catalogue says it duplicates.
    if node.get("multi_az") is True:
        for driver in definition.get("multi_az_multiplies", []):
            quantity = float(node.usage.get(driver, 0))
            rate = float(rates.get(driver, 0))
            if quantity and rate:
                lines.append(
                    CostLine(
                        node_id=node.service_id,
                        node_name=node.name,
                        driver=driver,
                        driver_label=f"{_driver_labels(node.service_id).get(driver, driver)} (standby)",
                        quantity=quantity,
                        unit_rate=rate,
                        monthly_cost=round(quantity * rate, 2),
                        is_premium=True,
                        note="Multi-AZ standby capacity.",
                    )
                )

    # Flat-rate controls.
    for control in PREMIUM_FLAT:
        if node.get(control) is not True:
            continue
        spec = control_costs.get(control)
        if not spec or spec.get("basis") != "flat_monthly":
            continue
        amount = float(spec["amount"])
        lines.append(
            CostLine(
                node_id=node.service_id,
                node_name=node.name,
                driver=control,
                driver_label=catalog.attribute_defs()[control]["label"],
                quantity=1.0,
                unit_rate=amount,
                monthly_cost=round(amount, 2),
                is_premium=True,
                note=spec.get("note", ""),
            )
        )

    # Retention beyond the free allocation.
    for control in ("backup_retention_days", "log_retention_days"):
        days = node.get(control)
        if days is None:
            continue
        spec = control_costs.get(control, {})
        free_days = float(spec.get("free_days", 0))
        if float(days) <= free_days:
            continue
        storage_gb = float(node.usage.get("storage_gb", 0))
        if not storage_gb:
            continue
        multiple = (float(days) - free_days) / max(free_days, 1.0)
        amount = storage_gb * float(spec["amount_per_gb_month"]) * multiple
        lines.append(
            CostLine(
                node_id=node.service_id,
                node_name=node.name,
                driver=control,
                driver_label=f"{catalog.attribute_defs()[control]['label']} beyond {int(free_days)} days",
                quantity=round(storage_gb * multiple, 1),
                unit_rate=float(spec["amount_per_gb_month"]),
                monthly_cost=round(amount, 2),
                is_premium=True,
                note=spec.get("note", ""),
            )
        )

    return lines


def estimate(graph: DesignGraph) -> CostEstimate:
    snapshot = catalog.pricing()
    all_rates = snapshot["rates"]
    control_costs = snapshot["control_costs"]

    lines: list[CostLine] = []
    for node in graph.nodes.values():
        rates = all_rates.get(node.service_id, {})
        lines.extend(_baseline_lines(node, rates))
        lines.extend(_premium_lines(node, rates, control_costs))

    baseline = round(sum(l.monthly_cost for l in lines if not l.is_premium), 2)
    premium = round(sum(l.monthly_cost for l in lines if l.is_premium), 2)

    return CostEstimate(
        baseline=baseline,
        premium=premium,
        lines=sorted(lines, key=lambda l: (l.node_name, l.is_premium, l.driver)),
        as_of=snapshot["as_of"],
        region=snapshot["region"],
        currency=snapshot["currency"],
        source=snapshot["source"],
    )
