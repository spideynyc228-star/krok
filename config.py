from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass
class ModelConfig:
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct"
    zero_shot_model: str = "cointegrated/rubert-tiny-bilingual-nli"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    device: str = "auto"
    max_tokens: int = 2048
    temperature: float = 0.1


@dataclass
class ClassificationConfig:
    confidence_threshold: float = 0.5
    default_class: str = "other"


@dataclass
class ClusteringConfig:
    min_cluster_size: int = 3  # Минимум 3 диалога в кластере
    min_samples: int = 2       # Минимум 2 соседа для точки
    top_n_for_naming: int = 30
    n_neighbors: int = 15      # Для UMAP (локальная структура)
    n_components: int = 5      # Размерность после UMAP


@dataclass
class PathsConfig:
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent)
    data_dir: Path = field(default=None)
    dialogs_dir: Path = field(default=None)
    outputs_dir: Path = field(default=None)
    models_dir: Path = field(default=None)
    classes_file: Path = field(default=None)
    
    def __post_init__(self):
        if self.data_dir is None:
            self.data_dir = self.base_dir / "data"
        if self.dialogs_dir is None:
            self.dialogs_dir = self.data_dir / "dialogs"
        if self.outputs_dir is None:
            self.outputs_dir = self.base_dir / "outputs"
        if self.models_dir is None:
            self.models_dir = self.base_dir / "models"
        if self.classes_file is None:
            self.classes_file = self.data_dir / "classes.csv"


@dataclass
class IntegrationsConfig:
    FIXED_INTEGRATIONS: tuple = field(default_factory=lambda: (
        "Outlook", "Exchange", "Mail", "Calendar", "CRM", "Jira", "Confluence",
        "ISUP", "Excel", "Word", "PowerPoint", "Teams", "Slack", "Telegram",
        "SharePoint", "OneDrive", "Project", "Contacts", "SQL", "REST API",
        "Browser", "Internet", "Filesystem"
    ))


@dataclass
class ToolsConfig:
    FIXED_TOOLS: tuple = field(default_factory=lambda: (
        "web_search", "browser", "mail", "calendar", "contacts", "crm", "jira",
        "confluence", "python", "sql", "excel", "filesystem", "presentation",
        "word", "powerpoint", "ocr", "speech_to_text", "text_to_speech",
        "translator", "summarizer", "image_generation"
    ))


@dataclass
class Config:
    models: ModelConfig = field(default_factory=ModelConfig)
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    clustering: ClusteringConfig = field(default_factory=ClusteringConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)


config = Config()
