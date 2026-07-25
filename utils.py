import csv
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
from schemas import DialogAnalysis, UseCase, DialogMetadata, ClassificationResult, TokenCounts


def save_dialogs_csv(analyses: List[DialogAnalysis], output_path: Path):
    rows = []
    for a in analyses:
        row = {
            "request_id": a.request_id,
            "dialog_id": a.dialog_id,
            "user_id": a.user_id,
            "created_at": a.created_at,
            "first_user_message": a.first_user_message,
            "summary": a.metadata.summary,
            "goal": a.metadata.goal,
            "intent": a.metadata.intent,
            "is_work": a.metadata.is_work,
            "automation_candidate": a.metadata.automation_candidate,
            "periodicity": a.metadata.periodicity,
            "complexity": a.metadata.complexity,
            "steps_requested": a.metadata.steps_requested,
            "integrations": ";".join(a.metadata.integrations),
            "integration_count": a.metadata.integration_count,
            "tools": ";".join(a.metadata.tools),
            "tool_calls": a.metadata.tool_calls,
            "uses_company_data": a.metadata.uses_company_data,
            "company_sources": ";".join(a.metadata.company_sources),
            "requires_generation": ";".join(a.metadata.requires_generation),
            "search_type": ";".join(a.metadata.search_type),
            "contains_sensitive_data": a.metadata.contains_sensitive_data,
            "prompt_injection": a.metadata.prompt_injection,
            "agent_failed": a.metadata.agent_failed,
            "failure_reason": a.metadata.failure_reason or "",
            "language": a.metadata.language,
            "class_ids": ";".join(map(str, a.classification.class_ids)),
            "class_names": ";".join(a.classification.class_names),
            "classification_scores": ";".join(map(str, a.classification.scores)),
            "confidence": a.classification.confidence,
            "user_tokens": a.token_counts.user_tokens,
            "assistant_tokens": a.token_counts.assistant_tokens,
            "tool_tokens": a.token_counts.tool_tokens,
            "total_tokens": a.token_counts.total_tokens,
            "estimated_cost": a.token_counts.estimated_cost,
            "burned_tokens": a.burned_tokens,
            "useful_messages": a.message_classification.useful_count if a.message_classification else 0,
            "useless_messages": a.message_classification.useless_count if a.message_classification else 0,
            "analysis_status": a.analysis_status,
            "metadata_confidence": a.metadata_confidence,
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Saved {len(rows)} rows to {output_path}")


def save_use_cases_csv(use_cases: List[UseCase], output_path: Path):
    rows = []
    for uc in use_cases:
        row = {
            "request_id": uc.request_id,
            "cluster_id": uc.cluster_id,
            "use_case": uc.use_case,
            "member_count": uc.member_count
        }
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Saved {len(rows)} use cases to {output_path}")


def save_analytics_csv(dialogs_path: Path, use_cases_path: Path, output_path: Path):
    dialogs_df = pd.read_csv(dialogs_path)
    use_cases_df = pd.read_csv(use_cases_path)
    
    merged = pd.merge(dialogs_df, use_cases_df, on="request_id", how="left")
    merged.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Saved merged analytics ({len(merged)} rows) to {output_path}")
    
    return merged


def load_classes(classes_path: Path) -> List[tuple]:
    classes = []
    with open(classes_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            classes.append((int(row["id"]), row["название_класса"]))
    return classes


def ensure_dirs(paths):
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
