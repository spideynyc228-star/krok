import numpy as np
import torch
from typing import List
from sentence_transformers import SentenceTransformer
from config import config


class TextEmbedder:
    def __init__(self):
        self.model_name = config.models.embedding_model
        self.device = self._get_device()
        
        print(f"Loading embedding model: {self.model_name} on {self.device}...")
        self.model = SentenceTransformer(
            self.model_name,
            cache_folder=str(config.paths.models_dir),
            device=self.device
        )
        print("Embedding model loaded successfully")

    def _get_device(self) -> str:
        if config.models.device == "cuda" and torch.cuda.is_available():
            return "cuda"
        elif config.models.device == "cpu":
            return "cpu"
        else:
            return "cuda" if torch.cuda.is_available() else "cpu"

    def embed(self, text: str) -> np.ndarray:
        return self.model.encode(text, convert_to_numpy=True)

    def embed_batch(self, texts: List[str], batch_size: int = 32, show_progress: bool = True) -> np.ndarray:
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=show_progress
        )
        return embeddings
