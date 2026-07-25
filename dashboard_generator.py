"""Standalone executive dashboard, generated from analysed agent logs."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


def rub(value: float) -> str:
    return f"{value:,.0f} ₽".replace(",", " ")


def number(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def compact(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f} млн"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f} тыс."
    return number(value)


def table(rows: list[dict[str, Any]], columns: list[tuple[str, str, str]]) -> str:
    header = "".join(f"<th class='{align}'>{escape(label)}</th>" for label, _, align in columns)
    body = "".join(
        "<tr>" + "".join(f"<td class='{align}'>{escape(str(row.get(key, '—')))}</td>" for _, key, align in columns) + "</tr>"
        for row in rows
    ) or "<tr><td colspan='99'>Нет данных</td></tr>"
    return f"<div class='table-wrap'><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"


def bars(items: list[tuple[str, float, str]], value_format=number) -> str:
    maximum = max((value for _, value, _ in items), default=1) or 1
    return "".join(
        f"<div class='bar-row'><div class='bar-meta'><span>{escape(label)}</span><b>{value_format(value)}</b></div>"
        f"<div class='track'><i class='{css}' style='width:{max(2, value / maximum * 100):.1f}%'></i></div></div>"
        for label, value, css in items
    )


def summary_card(label: str, value: str, note: str = "", tone: str = "") -> str:
    return f"<article class='metric {tone}'><span>{escape(label)}</span><strong>{escape(value)}</strong><small>{escape(note)}</small></article>"


def generate_dashboard(rows: list[dict[str, Any]], use_cases: list[dict[str, Any]], summary: dict[str, Any], output_html: Path) -> Path:
    output_html.parent.mkdir(parents=True, exist_ok=True)
    category: dict[str, dict[str, float]] = defaultdict(lambda: {"dialogs": 0, "tokens": 0, "cost": 0, "benefit": 0, "minutes": 0})
    monthly: dict[str, dict[str, float]] = defaultdict(lambda: {"dialogs": 0, "tokens": 0, "benefit": 0})
    tools = Counter()
    classification = Counter()
    for row in rows:
        key = row["category"]
        item = category[key]
        item["dialogs"] += 1
        item["tokens"] += int(row["total_tokens_est"])
        item["cost"] += float(row["allocated_cost_rub"])
        item["benefit"] += float(row["fte_savings_rub"])
        item["minutes"] += float(row["estimated_minutes_saved"])
        month = str(row.get("created_at") or "")[:7] or "нет даты"
        monthly[month]["dialogs"] += 1
        monthly[month]["tokens"] += int(row["total_tokens_est"])
        monthly[month]["benefit"] += float(row["fte_savings_rub"])
        tools.update(tool for tool in row["tools"].split("; ") if tool)
        classification[row["classification_source"]] += 1

    ordered_categories = sorted(category.items(), key=lambda pair: pair[1]["tokens"], reverse=True)
    category_rows = [{
        "Категория": name, "Диалоги": number(item["dialogs"]), "Токены": compact(item["tokens"]),
        "Экономия FTE": rub(item["benefit"]), "Затраты": rub(item["cost"]),
        "Эффект": "B > A" if item["benefit"] > item["cost"] else "B ≤ A",
    } for name, item in ordered_categories]
    category_bars = [(name, item["tokens"], "blue") for name, item in ordered_categories]
    tco_components = [(name, value, f"series-{index % 4}") for index, (name, value) in enumerate(summary["monthly_tco_components_rub"].items()) if value]
    total_tool_tokens = sum(int(row["tool_tokens_est"]) for row in rows)
    tool_share = total_tool_tokens / max(1, summary["total_tokens_est"])
    top_tools = [{"Инструмент": name, "Диалогов с инструментом": number(count)} for name, count in tools.most_common(10)]
    agent_rows = [{
        "Агент": item["agent_id"], "Диалоги": number(item["dialogs"]), "Токены": compact(item["total_tokens_est"]),
        "Затраты": rub(item["allocated_cost_rub"]), "Экономия FTE": rub(item["fte_savings_rub"]),
        "ROI": f"{item['roi_percent']:.1f}%", "Вердикт": "B > A" if item["business_case_positive"] else "B ≤ A",
    } for item in sorted(summary["agents"], key=lambda item: item["fte_savings_rub"], reverse=True)]
    trend_rows = [{
        "Месяц": month, "Диалоги": number(item["dialogs"]), "Токены": compact(item["tokens"]), "Экономия FTE": rub(item["benefit"]),
    } for month, item in sorted(monthly.items())]
    scenario_rows = [{
        "Сценарий": item["use_case"], "Категория": item["category"], "Диалоги": number(item["dialogs"]),
        "Токены": compact(item["tokens_est"]), "Провалы": number(item["agent_failures"]),
        "Исправлено": number(item["recovered_errors"]),
    } for item in sorted(use_cases, key=lambda item: item["tokens_est"], reverse=True)[:10]]

    positive = summary["business_case_positive"]
    decision_class = "pass" if positive else "hold"
    decision_title = "Можно масштабировать" if positive else "Масштабирование стоит остановить"
    cost_basis = "всего TCO периода" if summary["monthly_token_capacity"] is None else "стоимость обработанной нагрузки"
    capacity_note = (
        f"Загрузка от паспортной мощности: {summary['capacity_utilisation']:.1%}"
        if summary["capacity_utilisation"] is not None else
        "Паспортная производительность не передана"
    )
    next_actions = [
        ("01", "Зафиксировать метрики инференса", "Передавать input, output, cached и tool tokens из биллинга модели — текущий расчёт токенов оценочный."),
        ("02", "Измерить фактическую загрузку GPU", "Укажите monthly_token_capacity: без неё нельзя отделить недостаточную загрузку сервера от стоимости конкретного агента."),
        ("03", "Сократить тяжёлые ответы инструментов", f"Инструментальные результаты занимают {tool_share:.1%} токенов. Нужны лимиты полей, пагинация и краткие извлечения до передачи в LLM."),
        ("04", "Подтвердить экономию времени", "Проведите до/после на приоритетных сценариях; в отчёте минуты — явное бизнес-допущение, а не телеметрия."),
    ]
    cards = "".join([
        summary_card("Диалогов", number(summary["dialogs"]), f"{summary['period_months']} мес. наблюдений"),
        summary_card("Токены", compact(summary["total_tokens_est"]), "оценка chars / 4"),
        summary_card("Полный TCO", rub(summary["period_tco_rub"]), "амортизация + энергия + команда + лицензии"),
        summary_card("Стоимость 1 млн токенов", rub(summary["cost_per_million_tokens_rub"]), summary["capacity_status"]),
        summary_card("Экономия FTE", rub(summary["fte_savings_rub"]), f"коэффициент реализации {summary['value_realisation_rate']:.0%}"),
        summary_card("ROI", f"{summary['roi_percent']:.1f}%", cost_basis, "good" if positive else "bad"),
    ])
    actions_html = "".join(f"<li><span>{number}</span><div><b>{escape(title)}</b><p>{escape(text)}</p></div></li>" for number, title, text in next_actions)
    html_document = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prompt Radar — ROI корпоративных AI‑агентов</title><style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,600&display=swap');
:root{{--ink:#172238;--muted:#6d7a8e;--line:#dae1ec;--canvas:#f3f6fa;--paper:#fff;--navy:#17233a;--blue:#356af5;--cyan:#15a5b6;--orange:#ed8a4b;--violet:#8757d7;--red:#d75a5a;--green:#1b8d70}}*{{box-sizing:border-box}}body{{margin:0;background:var(--canvas);color:var(--ink);font:400 14px/1.5 Manrope,Arial,sans-serif}}main{{max-width:1440px;margin:auto;padding:28px 28px 56px}}.hero{{background:linear-gradient(122deg,#162138,#263a60);padding:38px 42px 36px;border-radius:24px;color:#fff;position:relative;overflow:hidden}}.hero:after{{content:"";position:absolute;width:360px;height:360px;border:1px solid #ffffff22;border-radius:50%;right:-120px;top:-220px;box-shadow:0 0 0 54px #ffffff08,0 0 0 108px #ffffff06}}.eyebrow{{color:#afcaff;text-transform:uppercase;letter-spacing:.13em;font-size:11px;font-weight:700;margin:0 0 15px}}h1{{font:600 clamp(32px,5vw,54px)/1.05 'Source Serif 4',Georgia,serif;margin:0;letter-spacing:-.035em;max-width:750px}}.hero p{{max-width:715px;color:#d9e2f4;font-size:16px;margin:17px 0 0}}.period{{display:inline-flex;margin-top:23px;padding:7px 11px;background:#ffffff14;border:1px solid #ffffff2c;border-radius:999px;font-size:12px}}.decision{{display:grid;grid-template-columns:auto 1fr;gap:20px;align-items:center;background:var(--paper);border:1px solid var(--line);padding:22px 24px;border-radius:16px;margin-top:20px}}.decision .signal{{width:13px;height:64px;border-radius:9px;background:var(--green)}}.decision.hold .signal{{background:var(--red)}}.decision h2{{font-size:20px;margin:0 0 4px;letter-spacing:-.02em}}.decision p{{margin:0;color:var(--muted)}}.decision strong{{display:block;margin-top:7px;font-size:13px}}.section-title{{display:flex;justify-content:space-between;gap:14px;align-items:end;margin:37px 0 14px}}.section-title h2{{margin:0;font-size:22px;letter-spacing:-.025em}}.section-title p{{margin:0;color:var(--muted);font-size:12px}}.metrics{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}}.metric{{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:16px;min-height:128px;display:flex;flex-direction:column;justify-content:space-between}}.metric span{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}}.metric strong{{font-size:23px;line-height:1.15;letter-spacing:-.04em}}.metric small{{color:var(--muted);font-size:10px;line-height:1.35}}.metric.good strong{{color:var(--green)}}.metric.bad strong{{color:var(--red)}}.grid-two{{display:grid;grid-template-columns:1.06fr .94fr;gap:14px}}.panel{{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:22px;min-width:0}}.panel h3{{margin:0 0 5px;font-size:16px;letter-spacing:-.015em}}.panel .sub{{color:var(--muted);font-size:12px;margin:0 0 22px}}.bar-row{{margin:0 0 14px}}.bar-meta{{display:flex;justify-content:space-between;gap:12px;font-size:12px;margin-bottom:6px}}.bar-meta span{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.bar-meta b{{font-weight:600;white-space:nowrap}}.track{{height:8px;background:#edf0f5;border-radius:99px;overflow:hidden}}.track i{{display:block;height:100%;border-radius:99px;background:var(--blue)}}.track i.series-0{{background:var(--blue)}}.track i.series-1{{background:var(--cyan)}}.track i.series-2{{background:var(--orange)}}.track i.series-3{{background:var(--violet)}}.cost-total{{margin-top:16px;padding-top:14px;border-top:1px solid var(--line);display:flex;justify-content:space-between;font-size:12px}}.callout{{background:#f5f8ff;border:1px solid #d9e4ff;border-radius:12px;padding:15px 16px;color:#31446c;font-size:12px;margin-top:16px}}.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;min-width:600px;font-size:12px}}th{{text-align:left;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.06em;padding:0 10px 10px;border-bottom:1px solid var(--line)}}td{{padding:12px 10px;border-bottom:1px solid #edf0f4;vertical-align:top}}tbody tr:last-child td{{border-bottom:0}}.right{{text-align:right;white-space:nowrap}}.verdict{{font-weight:700}}.insights{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.actions{{padding:0;margin:0;list-style:none}}.actions li{{display:grid;grid-template-columns:34px 1fr;gap:12px;padding:13px 0;border-bottom:1px solid #edf0f4}}.actions li:last-child{{border-bottom:0}}.actions span{{font-size:11px;font-weight:700;color:var(--blue);padding-top:2px}}.actions b{{font-size:13px}}.actions p{{font-size:12px;color:var(--muted);margin:3px 0 0}}.quality{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.quality div{{padding:13px 0;border-right:1px solid var(--line)}}.quality div:last-child{{border:0}}.quality span,.quality strong{{display:block}}.quality span{{font-size:11px;color:var(--muted)}}.quality strong{{font-size:17px;margin-top:3px}}.footer{{color:var(--muted);font-size:11px;margin:22px 4px 0}}@media(max-width:1100px){{.metrics{{grid-template-columns:repeat(3,1fr)}}}}@media(max-width:760px){{main{{padding:14px 12px 36px}}.hero{{padding:28px 23px;border-radius:18px}}.decision,.grid-two,.insights{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(2,1fr)}}.quality{{grid-template-columns:1fr 1fr}}.quality div:nth-child(2){{border:0}}.section-title{{display:block}}.section-title p{{margin-top:4px}}}}@media(max-width:420px){{.metrics{{grid-template-columns:1fr}}.quality{{grid-template-columns:1fr}}.quality div{{border:0;border-bottom:1px solid var(--line)}}}}
</style></head><body><main>
<header class="hero"><p class="eyebrow">KROK · Executive intelligence</p><h1>Prompt Radar</h1><p>Экономика и сценарии корпоративных AI‑агентов — в одной управленческой картине.</p><span class="period">Период наблюдения: {summary['period_months']} мес. · {number(summary['dialogs'])} диалогов</span></header>
<section class="decision {decision_class}"><i class="signal"></i><div><h2>{decision_title}</h2><p>{escape(summary['decision'])}</p><strong>Затраты для сравнения: {rub(summary['comparison_cost_rub'])} · Выгода B: {rub(summary['fte_savings_rub'])} · Разрыв: {rub(abs(summary['net_benefit_rub']))}</strong></div></section>
<section><div class="section-title"><h2>Показатели для решения</h2><p>Финансовые допущения — в config/economics.json</p></div><div class="metrics">{cards}</div></section>
<section><div class="section-title"><h2>Почему экономика выглядит именно так</h2><p>Сначала стоимость платформы, затем фактическое использование</p></div><div class="grid-two"><article class="panel"><h3>Структура ежемесячного TCO</h3><p class="sub">{capacity_note}</p>{bars(tco_components, rub)}<div class="cost-total"><span>Полный TCO в месяц</span><b>{rub(summary['monthly_tco_rub'])}</b></div></article><article class="panel"><h3>Загрузка и потенциал окупаемости</h3><p class="sub">Ориентиры для следующего управленческого цикла</p><div class="quality"><div><span>Токенов в месяц</span><strong>{compact(summary['monthly_observed_tokens_est'])}</strong></div><div><span>До breakeven</span><strong>{number(summary['additional_minutes_needed'])} мин</strong></div><div><span>Breakeven</span><strong>{number(summary['break_even_dialogs'])} диалогов</strong></div><div><span>Цена минуты FTE</span><strong>{rub(summary['fte_minute_cost_rub'])}</strong></div></div><p class="callout">{escape(summary['capacity_status'])}. Передайте производительность сервера за месяц, чтобы в отчёте появилась измеренная загрузка и корректная стоимость конкретного агента.</p></article></div></section>
<section><div class="section-title"><h2>Где агенты создают ценность</h2><p>Категории ранжированы по объёму обработанных токенов</p></div><div class="grid-two"><article class="panel"><h3>Распределение нагрузки</h3><p class="sub">Токены по категориям запросов</p>{bars(category_bars, compact)}</article><article class="panel"><h3>Инструменты — главный потребитель контекста</h3><p class="sub">{tool_share:.1%} всех оценочных токенов приходится на результаты tools</p>{table(top_tools, [('Инструмент','Инструмент',''),('Диалогов с инструментом','Диалогов с инструментом','right')])}</article></div></section>
<section><div class="section-title"><h2>Экономика по сценариям</h2><p>Сценарии с максимальной нагрузкой и их управленческий результат</p></div><article class="panel">{table(scenario_rows, [('Сценарий','Сценарий',''),('Категория','Категория',''),('Диалоги','Диалоги','right'),('Токены','Токены','right'),('Провалы','Провалы','right'),('Исправлено','Исправлено','right')])}</article></section>
<section><div class="section-title"><h2>Агенты и направления</h2><p>Сравнение затрат A с модельной экономией B</p></div><article class="panel">{table(agent_rows, [('Агент','Агент',''),('Диалоги','Диалоги','right'),('Токены','Токены','right'),('Затраты','Затраты','right'),('Экономия FTE','Экономия FTE','right'),('ROI','ROI','right'),('Вердикт','Вердикт','right verdict')])}</article></section>
<section><div class="section-title"><h2>Динамика наблюдений</h2><p>Месячные значения из логов</p></div><article class="panel">{table(trend_rows, [('Месяц','Месяц',''),('Диалоги','Диалоги','right'),('Токены','Токены','right'),('Экономия FTE','Экономия FTE','right')])}</article></section>
<section><div class="section-title"><h2>Что сделать дальше</h2><p>Порядок действий, чтобы перейти от модельного ROI к доказанному</p></div><div class="insights"><article class="panel"><h3>Следующий спринт аналитики</h3><ol class="actions">{actions_html}</ol></article><article class="panel"><h3>Качество доказательств</h3><p class="sub">Отчёт отделяет телеметрию от допущений</p><div class="quality"><div><span>Source labels</span><strong>{number(classification.get('source_label', 0))}</strong></div><div><span>Heuristic labels</span><strong>{number(classification.get('heuristic', 0))}</strong></div><div><span>Провалы tools</span><strong>{number(summary['agent_failures'])}</strong></div><div><span>Исправленные ошибки</span><strong>{number(summary['recovered_errors'])}</strong></div></div><p class="callout">Классы и сценарии в демо-логах уже размечены источником. Это не следует выдавать за качество LLM-классификатора: для production нужна ручная валидационная выборка.</p></article></div></section>
<p class="footer">Сформировано {datetime.now().strftime('%d.%m.%Y %H:%M')} · Prompt Radar · Источник: JSON-логи агентов</p></main></body></html>"""
    output_html.write_text(html_document, encoding="utf-8")
    return output_html
