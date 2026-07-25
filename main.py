"""Reproducible analytics and ROI report for corporate AI-agent logs.

The pipeline deliberately has no mandatory ML or GPU dependencies: it can be
run on a secure analytics host where outbound model downloads are prohibited.
When source logs already contain scenario labels (as in the demo data), those
labels are used as ground truth. For unlabelled logs a documented keyword
fallback is applied and marked as ``heuristic`` in the output.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from dashboard_generator import generate_dashboard
from economics import EconomicsConfig, build_economics, load_economics_config

ROOT = Path(__file__).resolve().parent

CATEGORY_KEYWORDS = {
    "Генерация текста и документов": ("письм", "тз", "документ", "презентац", "сформулиру"),
    "Поиск и сбор информации": ("найди", "поиск", "собери информацию", "поставщик"),
    "Анализ данных и отчетность": ("отчёт", "отчет", "excel", "таблиц", "выгруз"),
    "Работа с задачами и проектами": ("задач", "тикет", "проект", "jira", "исуп"),
    "Планирование и календарь": ("календар", "встреч", "переговорн", "слот"),
    "Управление коммуникациями": ("почт", "ответ клиент", "переписк", "уведом"),
    "Помощь с кодом и техническими вопросами": ("код", "api", "лог", "ошибк", "контейнер"),
    "Обучение и объяснение": ("объясни", "как ", "обуч", "помоги понять"),
    "Автоматизация рабочих процессов": ("автоматиз", "периодическ", "монитор", "еженедельн"),
}

# Minutes are an explicit business assumption, not observed telemetry. They can
# be overridden per use case in config/economics.json.
DEFAULT_MINUTES_BY_CATEGORY = {
    "Генерация текста и документов": 20,
    "Поиск и сбор информации": 25,
    "Анализ данных и отчетность": 35,
    "Работа с задачами и проектами": 12,
    "Планирование и календарь": 10,
    "Управление коммуникациями": 15,
    "Помощь с кодом и техническими вопросами": 25,
    "Обучение и объяснение": 12,
    "Автоматизация рабочих процессов": 30,
    "Общие вопросы и нерабочие запросы": 0,
}


def estimate_tokens(value: Any) -> int:
    """Return a conservative token estimate for arbitrary log payloads.

    Production logs should provide model usage counters. Demo logs do not, so
    we use ``ceil(characters / 4)`` and identify the result as an estimate.
    """
    if value is None:
        return 0
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (len(value) + 3) // 4


def flatten_tools(messages: Iterable[dict[str, Any]]) -> tuple[str, int, int, bool]:
    tools: list[str] = []
    tool_tokens = 0
    failed = False
    for message in messages:
        if message.get("role") != "tool":
            continue
        name = str(message.get("tool_name") or "unknown_tool")
        tools.append(name)
        payload = {key: message.get(key) for key in ("content", "arguments", "result") if message.get(key) is not None}
        tool_tokens += estimate_tokens(payload)
        result = message.get("result")
        if isinstance(result, dict) and str(result.get("status", "ok")).lower() not in {"ok", "success", "completed"}:
            failed = True
    return "; ".join(sorted(set(tools))), len(tools), tool_tokens, failed


def first_user_message(messages: Iterable[dict[str, Any]]) -> str:
    return next((str(m.get("content") or "") for m in messages if m.get("role") == "user"), "")


def classify_category(text: str) -> str:
    lowered = text.lower()
    best_name, best_score = "Общие вопросы и нерабочие запросы", 0
    for name, keywords in CATEGORY_KEYWORDS.items():
        score = sum(keyword in lowered for keyword in keywords)
        if score > best_score:
            best_name, best_score = name, score
    return best_name


def normalise_use_case(text: str, category: str) -> str:
    """A stable fallback name for logs without a labelled scenario."""
    lowered = text.lower()
    if "почт" in lowered and ("свод" in lowered or "саммар" in lowered):
        return "Сводка и приоритизация почты"
    if "календар" in lowered or "переговорн" in lowered or "встреч" in lowered:
        return "Планирование встреч и календаря"
    if "тикет" in lowered or "jira" in lowered or "исуп" in lowered:
        return "Создание и сопровождение задач"
    if "excel" in lowered or "отчёт" in lowered or "отчет" in lowered:
        return "Подготовка отчёта и выгрузки"
    return category


def extract_row(path: Path, data: dict[str, Any], minutes_by_category: dict[str, float]) -> dict[str, Any]:
    messages = data.get("messages") or []
    text = first_user_message(messages)
    category = str(data.get("scenario_type") or "").strip() or classify_category(text)
    labelled = bool(str(data.get("scenario_type") or "").strip())
    use_case = str(data.get("scenario") or "").strip() or normalise_use_case(text, category)
    tools, tool_calls, tool_tokens, tool_failed = flatten_tools(messages)
    user_tokens = sum(estimate_tokens(m.get("content")) for m in messages if m.get("role") == "user")
    assistant_tokens = sum(estimate_tokens(m.get("content")) for m in messages if m.get("role") == "assistant")
    total_tokens = user_tokens + assistant_tokens + tool_tokens
    text_failure = any("не удалось" in str(m.get("content", "")).lower() for m in messages if m.get("role") == "assistant")
    scenario_minutes = minutes_by_category.get(category, DEFAULT_MINUTES_BY_CATEGORY.get(category, 10))
    return {
        "request_id": str(data.get("session_id") or path.stem),
        "session_id": str(data.get("session_id") or ""),
        "user_id": str(data.get("user_id") or "unknown"),
        "agent_id": str(data.get("agent_id") or "unknown"),
        "department": str(data.get("department") or "Не указано"),
        "created_at": str(data.get("created_at") or ""),
        "category": category,
        "use_case": use_case,
        "classification_source": "source_label" if labelled else "heuristic",
        "first_user_message": text,
        "tools": tools,
        "tool_calls": tool_calls,
        "agent_failed": tool_failed or text_failure,
        "agent_recovered_error": bool(data.get("error_corrected", False)),
        "user_tokens_est": user_tokens,
        "assistant_tokens_est": assistant_tokens,
        "tool_tokens_est": tool_tokens,
        "total_tokens_est": total_tokens,
        "estimated_minutes_saved": round(float(scenario_minutes), 2),
        "token_count_method": "chars_div_4_estimate",
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("Нет валидных диалогов для записи")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_use_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["category"], row["use_case"])].append(row)
    report = []
    for (category, use_case), members in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0][1])):
        report.append({
            "category": category,
            "use_case": use_case,
            "dialogs": len(members),
            "tokens_est": sum(int(item["total_tokens_est"]) for item in members),
            "agent_failures": sum(bool(item["agent_failed"]) for item in members),
            "recovered_errors": sum(bool(item["agent_recovered_error"]) for item in members),
            "tools": "; ".join(sorted({tool for item in members for tool in item["tools"].split("; ") if tool})),
            "example_request": members[0]["first_user_message"],
        })
    return report


def run_pipeline(dialogs_dir: Path, outputs_dir: Path, economics_path: Path) -> dict[str, Any]:
    config = load_economics_config(economics_path)
    rows: list[dict[str, Any]] = []
    invalid_files: list[str] = []
    for file in sorted(dialogs_dir.glob("*.json")):
        try:
            with file.open(encoding="utf-8") as stream:
                data = json.load(stream)
            if not isinstance(data, dict):
                raise ValueError("JSON должен содержать объект диалога")
            rows.append(extract_row(file, data, config.minutes_by_category))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            invalid_files.append(f"{file.name}: {exc}")
    if not rows:
        raise RuntimeError(f"В {dialogs_dir} не найдено валидных JSON-диалогов")

    economics = build_economics(rows, config)
    for row in rows:
        row.update(economics["by_request"][row["request_id"]])
    use_cases = build_use_cases(rows)
    by_agent = economics["by_agent"]

    write_csv(outputs_dir / "analytics.csv", rows)
    write_csv(outputs_dir / "use_cases.csv", use_cases)
    write_csv(outputs_dir / "agents_roi.csv", by_agent)
    (outputs_dir / "economics.json").write_text(json.dumps(economics["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    (outputs_dir / "data_quality.json").write_text(json.dumps({
        "valid_dialogs": len(rows),
        "invalid_files": invalid_files,
        "classification_source": dict(Counter(row["classification_source"] for row in rows)),
        "token_count_method": "chars_div_4_estimate; replace with model usage counters in production",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    report = generate_dashboard(rows, use_cases, economics["summary"], outputs_dir / "report.html")
    return {"dialogs": len(rows), "use_cases": len(use_cases), "report": str(report), "summary": economics["summary"], "invalid_files": invalid_files}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Аналитика запросов к корпоративным AI-агентам и ROI")
    parser.add_argument("--dialogs-dir", type=Path, default=ROOT / "data" / "dialogs")
    parser.add_argument("--outputs-dir", type=Path, default=ROOT / "outputs")
    parser.add_argument("--economics-config", type=Path, default=ROOT / "config" / "economics.json")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = run_pipeline(arguments.dialogs_dir, arguments.outputs_dir, arguments.economics_config)
    summary = result["summary"]
    print(f"Обработано диалогов: {result['dialogs']}; сценариев: {result['use_cases']}")
    print(f"TCO периода: {summary['period_tco_rub']:,.0f} ₽; экономия FTE: {summary['fte_savings_rub']:,.0f} ₽")
    print(f"ROI: {summary['roi_percent']:.1f}%; отчёт: {result['report']}")
