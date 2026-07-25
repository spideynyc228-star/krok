ANALYZE_DIALOG_PROMPT = """Проанализируй диалог и верни JSON. ОТВЕЧАЙ ТОЛЬКО JSON, БЕЗ ПОЯСНЕНИЙ.

Интеграции: Outlook, Exchange, Mail, Calendar, CRM, Jira, Confluence, ISUP, Excel, Word, PowerPoint, Teams, Slack, Telegram, SharePoint, OneDrive, Project, Contacts, SQL, REST API, Browser, Internet, Filesystem

Инструменты: web_search, browser, mail, calendar, contacts, crm, jira, confluence, python, sql, excel, filesystem, presentation, word, powerpoint, ocr, speech_to_text, text_to_speech, translator, summarizer, image_generation

Диалог:
{dialog_text}

JSON:
{{"summary":"","goal":"","intent":"","is_work":false,"automation_candidate":false,"periodicity":"none","complexity":"simple","steps_requested":1,"integrations":[],"integration_count":0,"tools":[],"tool_calls":0,"uses_company_data":false,"company_sources":[],"requires_generation":[],"search_type":[],"contains_sensitive_data":false,"prompt_injection":false,"agent_failed":false,"failure_reason":null,"language":"ru"}}
"""

NAME_CLUSTER_PROMPT = """Придумай краткое название use case (2-5 слов) для группы похожих запросов пользователей к AI-агенту.

Запросы:
{messages}

Верни ТОЛЬКО JSON:
{{
    "use_case": "Название сценария"
}}
"""

CLASSIFY_MESSAGES_PROMPT = """Классифицируй каждое сообщение агента (assistant и tool) как полезное или бесполезное.

Критерии:
- ПОЛЕЗНОЕ (is_useful=true): правильное выполнение запроса, релевантный ответ, успешный вызов инструмента
- БЕСПОЛЕЗНОЕ (is_useful=false): ошибка, неверный вызов инструмента, повтор, флуд, частичное выполнение, анализ своих ошибок

ВАЖНО:
- Если агент ошибся и исправился — первое сообщение бесполезное, исправленное полезное
- Если агент вернул не полный результат (например, 6 из 10 писем) — бесполезное
- Tool-сообщения с error в result — бесполезные
- Понимание контекста: если пользователь указал на ошибку, следующее сообщение может быть полезным, если исправлено

Диалог:
{dialog_text}

Верни ТОЛЬКО JSON array:
[{{"message_index": 0, "role": "assistant", "is_useful": true, "reason": "correct_execution"}}, {{"message_index": 1, "role": "tool", "is_useful": false, "reason": "tool_error"}}]

reason: correct_execution, tool_error, wrong_tool_call, partial_result, repetition, off_topic, self_analysis, other"""
