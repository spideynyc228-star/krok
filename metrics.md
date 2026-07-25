# Метрики для Dashboard

## Основные метрики

### 1. Общая статистика
- **total_dialogs**: Общее количество диалогов
- **total_users**: Количество уникальных пользователей
- **date_range**: Диапазон дат (min/max created_at)

### 2. Токены
- **total_tokens**: Сумма всех токенов
- **avg_tokens_per_dialog**: Среднее токенов на диалог
- **total_burned_tokens**: Сумма burned_tokens
- **burned_ratio**: burned_tokens / total_tokens (%)
- **total_estimated_cost**: Сумма estimated_cost

### 3. Качество работы агента
- **useful_messages_total**: Сумма useful_messages
- **useless_messages_total**: Сумма useless_messages
- **useful_ratio**: useful_messages / (useful + useless) (%)
- **dialogs_with_burned**: Диалоги с burned_tokens > 0
- **avg_burned_per_failed_dialog**: Среднее burned_tokens на диалог с ошибками

### 4. Классификация
- **work_dialogs**: Диалоги с is_work=True
- **work_ratio**: work_dialogs / total_dialogs (%)
- **automation_candidates**: automation_candidate=True
- **automation_ratio**: automation_candidates / total_dialogs (%)

### 5. Сложность и периодичность
- **complexity_distribution**: Распределение по complexity (simple/medium/complex)
- **periodicity_distribution**: Распределение по periodicity (none/daily/weekly/monthly)

### 6. Интеграции и инструменты
- **dialogs_with_integrations**: Диалоги с integration_count > 0
- **unique_integrations**: Уникальные интеграции
- **unique_tools**: Уникальные инструменты
- **avg_tool_calls**: Среднее tool_calls на диалог

### 7. Use Cases (кластеры)
- **total_clusters**: Количество кластеров (cluster_id != -1)
- **outliers**: Диалоги с cluster_id = -1
- **top_5_clusters**: Топ-5 кластеров по member_count
- **avg_cluster_size**: Средний размер кластера

### 8. Проблемы
- **agent_failures**: agent_failed=True
- **failure_reasons**: Распределение failure_reason
- **prompt_injections**: prompt_injection=True
- **sensitive_data**: contains_sensitive_data=True

### 9. Языки
- **language_distribution**: Распределение по language (ru/en)

### 10. Уверенность классификации
- **avg_confidence**: Средняя confidence
- **low_confidence_dialogs**: Диалоги с confidence < 0.5
