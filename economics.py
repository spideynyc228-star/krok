"""Transparent TCO and FTE-value model for AI-agent usage."""

from __future__ import annotations

from dataclasses import dataclass, field
import calendar
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EconomicsConfig:
    server_capex_rub: float = 100_000_000
    amortization_years: int = 5
    server_power_kw: float = 10.0
    electricity_rub_per_kwh: float = 8.0
    utilisation: float = 0.60
    monthly_product_and_inference_team_rub: float = 0.0
    monthly_license_per_active_user_rub: float = 10_000.0
    monthly_token_capacity: int | None = None
    monthly_fte_rub: float = 400_000.0
    working_days_per_month: int = 22
    working_hours_per_day: int = 8
    value_realisation_rate: float = 0.70
    minutes_by_category: dict[str, float] = field(default_factory=dict)


def load_economics_config(path: Path) -> EconomicsConfig:
    with path.open(encoding="utf-8") as stream:
        values = json.load(stream)
    allowed = {item.name for item in __import__("dataclasses").fields(EconomicsConfig)}
    return EconomicsConfig(**{key: value for key, value in values.items() if key in allowed})


def months_in_period(rows: list[dict[str, Any]]) -> int:
    keys = set()
    for row in rows:
        timestamp = str(row.get("created_at") or "")
        if len(timestamp) >= 7 and timestamp[4] == "-":
            keys.add(timestamp[:7])
    return max(1, len(keys))


def active_user_months(rows: list[dict[str, Any]]) -> int:
    return max(1, len({(row["user_id"], str(row.get("created_at") or "")[:7]) for row in rows}))


def build_economics(rows: list[dict[str, Any]], config: EconomicsConfig) -> dict[str, Any]:
    period_months = months_in_period(rows)
    total_tokens = sum(int(row["total_tokens_est"]) for row in rows)
    users_months = active_user_months(rows)
    hours_per_month = 365.25 / 12 * 24
    monthly_amortization = config.server_capex_rub / config.amortization_years / 12
    monthly_electricity = config.server_power_kw * hours_per_month * config.utilisation * config.electricity_rub_per_kwh
    monthly_team = config.monthly_product_and_inference_team_rub
    monthly_licenses = config.monthly_license_per_active_user_rub * (users_months / period_months)
    monthly_tco = monthly_amortization + monthly_electricity + monthly_team + monthly_licenses
    period_tco = monthly_tco * period_months
    denominator = (config.monthly_token_capacity or (total_tokens / period_months)) * period_months
    cost_per_token = period_tco / max(1, denominator)
    minute_cost = config.monthly_fte_rub / (config.working_days_per_month * config.working_hours_per_day * 60)
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_request: dict[str, dict[str, Any]] = {}
    for row in rows:
        token_cost = int(row["total_tokens_est"]) * cost_per_token
        savings = float(row["estimated_minutes_saved"]) * minute_cost * config.value_realisation_rate
        item = {
            "allocated_cost_rub": round(token_cost, 2),
            "fte_savings_rub": round(savings, 2),
            "net_benefit_rub": round(savings - token_cost, 2),
            "business_case_positive": savings > token_cost,
        }
        by_request[row["request_id"]] = item
        by_agent[row["agent_id"]].append({**row, **item})
    agent_rows = []
    for agent_id, items in sorted(by_agent.items()):
        cost = sum(item["allocated_cost_rub"] for item in items)
        benefit = sum(item["fte_savings_rub"] for item in items)
        agent_rows.append({
            "agent_id": agent_id,
            "dialogs": len(items),
            "total_tokens_est": sum(int(item["total_tokens_est"]) for item in items),
            "allocated_cost_rub": round(cost, 2),
            "fte_savings_rub": round(benefit, 2),
            "net_benefit_rub": round(benefit - cost, 2),
            "roi_percent": round(((benefit - cost) / cost * 100) if cost else 0, 2),
            "business_case_positive": benefit > cost,
        })
    total_minutes = sum(float(row["estimated_minutes_saved"]) for row in rows)
    fte_savings = total_minutes * minute_cost * config.value_realisation_rate
    net_benefit = fte_savings - period_tco
    summary = {
        "dialogs": len(rows), "period_months": period_months, "active_user_months": users_months,
        "total_tokens_est": total_tokens, "monthly_amortization_rub": round(monthly_amortization, 2),
        "monthly_electricity_rub": round(monthly_electricity, 2), "monthly_team_rub": round(monthly_team, 2),
        "monthly_licenses_rub": round(monthly_licenses, 2), "monthly_tco_rub": round(monthly_tco, 2),
        "period_tco_rub": round(period_tco, 2), "cost_per_token_rub": cost_per_token,
        "cost_per_million_tokens_rub": round(cost_per_token * 1_000_000, 2),
        "fte_minute_cost_rub": round(minute_cost, 2), "modeled_minutes_saved": round(total_minutes, 2),
        "value_realisation_rate": config.value_realisation_rate, "fte_savings_rub": round(fte_savings, 2),
        "net_benefit_rub": round(net_benefit, 2), "roi_percent": round((net_benefit / period_tco * 100) if period_tco else 0, 2),
        "business_case_positive": fte_savings > period_tco, "agent_failures": sum(bool(row["agent_failed"]) for row in rows),
        "recovered_errors": sum(bool(row.get("agent_recovered_error")) for row in rows),
        "agents": agent_rows,
    }
    summary["decision"] = (
        "Модель подтверждает экономический эффект: B > A. Проверьте допущения о времени и фактические usage counters перед инвестиционным решением."
        if summary["business_case_positive"] else
        "При текущих допущениях B ≤ A: увеличьте загрузку, подтвердите экономию времени или пересмотрите TCO перед масштабированием."
    )
    return {"summary": summary, "by_request": by_request, "by_agent": agent_rows}
