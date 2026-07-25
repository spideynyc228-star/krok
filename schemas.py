from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


class Message(BaseModel):
    role: str
    content: str = ""
    timestamp: Optional[str] = None
    tool_name: Optional[str] = None
    arguments: Optional[dict] = None
    result: Optional[dict] = None


class Dialog(BaseModel):
    user_id: str = ""
    session_id: str = ""
    created_at: str
    scenario: str = Field(..., validation_alias="scenario_type")
    messages: List[Message]
    
    @property
    def id(self) -> int:
        # Извлекаем ID из session_id (sess_20260725_000032 -> 32)
        try:
            return int(self.session_id.split("_")[-1])
        except:
            return 0
    
    @property
    def scenario_id(self) -> str:
        return self.scenario.replace(" ", "_").lower()[:50]
    
    @property
    def scenario_title(self) -> str:
        return self.scenario
    
    @property
    def scenario_description(self) -> str:
        return self.scenario
    
    @property
    def total_tokens(self) -> int:
        from token_counter import TokenCounter
        counter = TokenCounter()
        return counter.count_messages(self.messages).total_tokens
    
    @property
    def message_count(self) -> int:
        return len(self.messages)


class DialogMetadata(BaseModel):
    summary: str = Field(..., description="Краткое саммари диалога")
    goal: str = Field(..., description="Цель пользователя")
    intent: str = Field(..., description="Намерение пользователя")
    is_work: bool = Field(..., description="Рабочий ли запрос")
    automation_candidate: bool = Field(..., description="Кандидат на автоматизацию")
    periodicity: Literal["none", "daily", "weekly", "monthly"] = Field(..., description="Периодичность")
    complexity: Literal["simple", "medium", "complex"] = Field(..., description="Сложность")
    steps_requested: int = Field(..., description="Количество запрошенных шагов")
    integrations: List[str] = Field(default_factory=list, description="Используемые интеграции")
    integration_count: int = Field(default=0, description="Количество интеграций")
    tools: List[str] = Field(default_factory=list, description="Используемые инструменты")
    tool_calls: int = Field(default=0, description="Количество вызовов инструментов")
    uses_company_data: bool = Field(..., description="Использует ли внутренние данные")
    company_sources: List[str] = Field(default_factory=list, description="Источники внутренних данных")
    requires_generation: List[Literal["text", "excel", "sql", "presentation"]] = Field(default_factory=list)
    search_type: List[Literal["internet", "internal"]] = Field(default_factory=list)
    contains_sensitive_data: bool = Field(..., description="Есть ли чувствительные данные")
    prompt_injection: bool = Field(..., description="Попытка промпт-инъекции")
    agent_failed: bool = Field(..., description="Неудача агента")
    failure_reason: Optional[str] = Field(default=None, description="Причина неудачи")
    language: str = Field(default="ru", description="Язык диалога")


class ClassificationResult(BaseModel):
    class_ids: List[int] = Field(default_factory=list)
    class_names: List[str] = Field(default_factory=list)
    scores: List[float] = Field(default_factory=list)
    confidence: float = Field(default=0.0)


class TokenCounts(BaseModel):
    user_tokens: int = 0
    assistant_tokens: int = 0
    tool_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0


class DialogAnalysis(BaseModel):
    request_id: int
    dialog_id: int
    user_id: str = ""
    created_at: str = ""
    first_user_message: str
    metadata: DialogMetadata
    classification: ClassificationResult
    token_counts: TokenCounts
    class_labels: List[str] = Field(default_factory=list)
    analysis_status: str = "success"  # "success" | "parse_error"
    metadata_confidence: float = 1.0


class ClusterInfo(BaseModel):
    cluster_id: int
    member_count: int
    representative_messages: List[str]


class UseCase(BaseModel):
    request_id: int
    cluster_id: int
    use_case: str
    member_count: int


class MessageClassification(BaseModel):
    message_index: int
    role: str
    is_useful: bool
    reason: str


class MessageClassificationResult(BaseModel):
    messages: List[MessageClassification] = Field(default_factory=list)
    burned_tokens: int = 0
    total_messages: int = 0
    useful_count: int = 0
    useless_count: int = 0


class DialogAnalysis(BaseModel):
    request_id: int
    dialog_id: int
    user_id: str = ""
    created_at: str = ""
    first_user_message: str
    metadata: DialogMetadata
    classification: ClassificationResult
    token_counts: TokenCounts
    message_classification: Optional[MessageClassificationResult] = None
    burned_tokens: int = 0
    class_labels: List[str] = Field(default_factory=list)
    analysis_status: str = "success"  # "success" | "parse_error" | "skipped"
    metadata_confidence: float = 1.0
