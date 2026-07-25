"""Self-contained HTML dashboard; no CDN or browser-side dependencies."""

from __future__ import annotations

import html
from collections import Counter
from pathlib import Path
from typing import Any


def rub(value: float) -> str:
    return f"{value:,.0f} ₽".replace(",", " ")


def number(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def rows_html(rows: list[dict[str, Any]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def generate_dashboard(rows: list[dict[str, Any]], use_cases: list[dict[str, Any]], summary: dict[str, Any], output_html: Path) -> Path:
    output_html.parent.mkdir(parents=True, exist_ok=True)
    category_counts = Counter(row["category"] for row in rows)
    tool_counts = Counter(tool for row in rows for tool in row["tools"].split("; ") if tool)
    agent_rows = sorted(summary["agents"], key=lambda item: item["roi_percent"], reverse=True)
    category_rows = [{"Категория": name, "Диалогов": count} for name, count in category_counts.most_common()]
    tools_rows = [{"Инструмент": name, "Вызовов в диалогах": count} for name, count in tool_counts.most_common(12)]
    use_case_rows = [{
        "Сценарий": item["use_case"], "Категория": item["category"], "Диалогов": item["dialogs"],
        "Токенов (оценка)": number(item["tokens_est"]), "Провалов": item["agent_failures"], "Исправлено": item["recovered_errors"],
        "Пример": item["example_request"],
    } for item in use_cases[:20]]
    agent_table = [{
        "Агент": item["agent_id"], "Диалогов": item["dialogs"], "Токенов": number(item["total_tokens_est"]),
        "Затраты": rub(item["allocated_cost_rub"]), "Экономия FTE": rub(item["fte_savings_rub"]),
        "ROI": f"{item['roi_percent']:.1f}%", "B > A": "Да" if item["business_case_positive"] else "Нет",
    } for item in agent_rows]
    cards = [
        ("Диалогов", number(summary["dialogs"])),
        ("Токенов, оценка", number(summary["total_tokens_est"])),
        ("TCO за период", rub(summary["period_tco_rub"])),
        ("Стоимость 1 млн токенов", rub(summary["cost_per_million_tokens_rub"])),
        ("Экономия FTE (B)", rub(summary["fte_savings_rub"])),
        ("ROI", f"{summary['roi_percent']:.1f}%"),
        ("Провалы агента", number(summary["agent_failures"])),
        ("Ошибки, исправленные агентом", number(summary["recovered_errors"])),
        ("B > A", "Да" if summary["business_case_positive"] else "Нет"),
    ]
    card_html = "".join(f"<article class='card'><small>{label}</small><strong>{value}</strong></article>" for label, value in cards)
    html_document = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prompt Radar — ROI AI-агентов</title><style>
:root{{--ink:#132238;--muted:#617087;--bg:#f4f7fb;--accent:#276ef1;--good:#087c5b;--line:#dbe3ef}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 Inter,system-ui,sans-serif}}main{{max-width:1280px;margin:auto;padding:32px 20px 56px}}h1{{font-size:32px;margin:0 0 6px}}h2{{margin:32px 0 12px;font-size:21px}}.lead{{color:var(--muted);max-width:890px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}.card,.section{{background:white;border:1px solid var(--line);border-radius:12px;box-shadow:0 1px 3px #1322380c}}.card{{padding:18px}}.card small{{display:block;color:var(--muted);margin-bottom:8px}}.card strong{{font-size:23px}}.section{{padding:18px;margin-top:14px;overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}th{{color:var(--muted);font-weight:600;white-space:nowrap}}.note{{background:#edf4ff;border-left:4px solid var(--accent);padding:14px 16px;border-radius:6px}}.positive{{color:var(--good);font-weight:700}}code{{background:#eef1f6;padding:2px 5px;border-radius:4px}}@media(max-width:640px){{main{{padding:22px 12px}}h1{{font-size:25px}}}}</style></head>
<body><main><h1>Prompt Radar: эффективность AI‑агентов</h1><p class="lead">Руководительский отчёт по логам запросов, использованным инструментам и экономике. Все денежные оценки задаются в <code>config/economics.json</code>; расчёт воспроизводим.</p>
<div class="grid">{card_html}</div>
<section class="section"><h2>Вывод для решения</h2><p class="{'positive' if summary['business_case_positive'] else ''}">{html.escape(summary['decision'])}</p><p>За период: затраты A = <b>{rub(summary['period_tco_rub'])}</b>; моделируемая экономия B = <b>{rub(summary['fte_savings_rub'])}</b>; чистый эффект = <b>{rub(summary['net_benefit_rub'])}</b>.</p></section>
<section class="section"><h2>Что чаще всего делают с агентом</h2>{rows_html(category_rows, ['Категория','Диалогов'])}</section>
<section class="section"><h2>Топ-сценарии и примеры запросов</h2>{rows_html(use_case_rows, ['Сценарий','Категория','Диалогов','Токенов (оценка)','Провалов','Исправлено','Пример'])}</section>
<section class="section"><h2>ROI по агентам</h2>{rows_html(agent_table, ['Агент','Диалогов','Токенов','Затраты','Экономия FTE','ROI','B > A'])}</section>
<section class="section"><h2>Использованные инструменты</h2>{rows_html(tools_rows, ['Инструмент','Вызовов в диалогах'])}</section>
<section class="section"><h2>Допущения и ограничения</h2><ul><li>Токены в демонстрационном датасете оцениваются как символы / 4. Для финансового расчёта в production замените на usage counters модели.</li><li>Экономия времени — модельная оценка по сценариям и коэффициенту реализации, а не доказанный фактический эффект. Подтверждайте её замерами до/после и выборочной валидацией пользователей.</li><li>Стоимость команды включается в TCO отдельным параметром: её полезно считать для полной окупаемости продукта, но показывать отдельно для unit economics инференса.</li></ul></section>
</main></body></html>"""
    output_html.write_text(html_document, encoding="utf-8")
    return output_html
