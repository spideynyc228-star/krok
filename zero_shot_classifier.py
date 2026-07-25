import torch
from typing import List, Tuple
from transformers import pipeline
from schemas import ClassificationResult
from config import config


class ZeroShotClassifier:
    def __init__(self, classes: List[Tuple[int, str]]):
        self.model_name = config.models.zero_shot_model
        self.device = self._get_device()
        self.classes = classes
        self.class_names = [name for _, name in classes]
        self.class_map = {name: id for id, name in classes}
        
        print(f"Loading Zero-Shot classifier: {self.model_name} on {self.device}...")
        self.pipeline = pipeline(
            "zero-shot-classification",
            model=self.model_name,
            device=0 if self.device == "cuda" else -1,
            model_kwargs={"cache_dir": str(config.paths.models_dir)}
        )
        print("Zero-Shot classifier loaded successfully")

    def _get_device(self) -> str:
        if config.models.device == "cuda" and torch.cuda.is_available():
            return "cuda"
        elif config.models.device == "cpu":
            return "cpu"
        else:
            return "cuda" if torch.cuda.is_available() else "cpu"

    def classify(self, text: str, threshold: float = None) -> ClassificationResult:
        if threshold is None:
            threshold = config.classification.confidence_threshold

        result = self.pipeline(
            text,
            candidate_labels=self.class_names,
            multi_label=True
        )

        class_ids = []
        class_names_filtered = []
        scores = []

        for label, score in zip(result["labels"], result["scores"]):
            if score >= threshold:
                class_ids.append(self.class_map[label])
                class_names_filtered.append(label)
                scores.append(score)

        if not class_ids:
            class_ids = [0]
            class_names_filtered = [config.classification.default_class]
            scores = [1.0]

        max_score = max(scores) if scores else 0.0

        return ClassificationResult(
            class_ids=class_ids,
            class_names=class_names_filtered,
            scores=scores,
            confidence=max_score
        )

    def classify_batch(self, texts: List[str], threshold: float = None) -> List[ClassificationResult]:
        return [self.classify(text, threshold) for text in texts]
