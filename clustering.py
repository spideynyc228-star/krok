import numpy as np
from typing import List, Dict, Tuple
import hdbscan
from umap import UMAP
from sklearn.metrics import silhouette_score
from schemas import ClusterInfo, UseCase
from prompts import NAME_CLUSTER_PROMPT
from config import config


class DialogClusterer:
    def __init__(self, llm_analyzer=None):
        self.min_cluster_size = config.clustering.min_cluster_size
        self.min_samples = config.clustering.min_samples
        self.top_n = config.clustering.top_n_for_naming
        self.n_neighbors = config.clustering.n_neighbors
        self.n_components = config.clustering.n_components
        self.llm = llm_analyzer

    def cluster(self, embeddings: np.ndarray) -> Dict[int, List[int]]:
        # UMAP для уменьшения размерности перед HDBSCAN
        reducer = UMAP(
            n_components=self.n_components,
            n_neighbors=self.n_neighbors,
            min_dist=0.1,
            metric='cosine',
            random_state=42
        )
        reduced_embeddings = reducer.fit_transform(embeddings)
        
        # HDBSCAN с меньшим min_cluster_size для большего количества кластеров
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            metric='euclidean',
            cluster_selection_method='eom',
            prediction_data=True,
            allow_single_cluster=False
        )
        
        labels = clusterer.fit_predict(reduced_embeddings)
        
        clusters: Dict[int, List[int]] = {}
        noise_indices = []
        
        for idx, label in enumerate(labels):
            if label == -1:
                noise_indices.append(idx)
            else:
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(idx)
        
        # Оставляем выбросы с cluster_id = -1 (не объединяем в один кластер)
        for idx in noise_indices:
            if -1 not in clusters:
                clusters[-1] = []
            clusters[-1].append(idx)
        
        return clusters

    def get_representative_messages(
        self, 
        cluster_indices: List[int], 
        embeddings: np.ndarray, 
        messages: List[str],
        top_n: int = None
    ) -> List[str]:
        if top_n is None:
            top_n = self.top_n
        
        if len(cluster_indices) == 0:
            return []
        
        cluster_embeddings = embeddings[cluster_indices]
        centroid = np.mean(cluster_embeddings, axis=0)
        
        distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
        top_indices = np.argsort(distances)[:min(top_n, len(cluster_indices))]
        
        return [messages[cluster_indices[i]] for i in top_indices]

    def name_cluster(self, messages: List[str], is_noise: bool = False) -> str:
        if is_noise:
            return "Нераспределённые сценарии"
        
        if self.llm is None or len(messages) == 0:
            return self._heuristic_name(messages)
        
        messages_text = "\n".join(f"- {m}" for m in messages[:20])
        prompt = NAME_CLUSTER_PROMPT.format(messages=messages_text)
        
        try:
            import json
            import torch
            
            inputs = self.llm.tokenizer(prompt, return_tensors="pt").to(self.llm.device)
            
            with torch.no_grad():
                outputs = self.llm.model.generate(
                    **inputs,
                    max_new_tokens=60,
                    temperature=0.1,
                    do_sample=True,
                    pad_token_id=self.llm.tokenizer.eos_token_id
                )
            
            generated = self.llm.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
            
            # Пробуем распарсить JSON
            for line in generated.split("\n"):
                line = line.strip()
                if line.startswith("{") or line.startswith("```"):
                    if line.startswith("```"):
                        line = line.split("```")[1].strip()
                        if line.startswith("json"):
                            line = line[3:].strip()
                    try:
                        data = json.loads(line.rstrip("}"))
                        if "use_case" in data:
                            return data["use_case"]
                    except:
                        continue
            
            return self._heuristic_name(messages)
        except Exception as e:
            print(f"Error naming cluster with LLM: {e}")
            return self._heuristic_name(messages)

    def _heuristic_name(self, messages: List[str]) -> str:
        if not messages:
            return "Нераспределённые"
        
        # Анализируем все сообщения кластера, а не только первое
        all_text = " ".join(messages[:10]).lower()
        
        keywords = {
            "Сводка по почте": ["почт", "письм", "email", "сводк", "ответит"],
            "Задачи и Jira": ["задач", "jira", "тикет", "data-", "bug-", "task-"],
            "Встречи и календарь": ["встреч", "календар", "напомин", "планиров", "слот"],
            "CRM и клиенты": ["crm", "клиент", "компан", "сделк", "тендер", "директор"],
            "Отчёты и аналитика": ["отчет", "анализ", "данные", "статистик", "метри"],
            "Документы и Confluence": ["документ", "confluence", "страниц", "wiki", "файл"],
            "Поиск информации": ["найти", "поиск", "информаци", "узнать", "провер"],
            "Код и разработка": ["код", "python", "ошибк", "разработк", "test", "api"],
            "Автоматизация": ["автоматиз", "мониторинг", "уведомлен", "триггер"],
            "Команда и проекты": ["команд", "проект", "участник", "роль", "вендор"],
        }
        
        scores = {}
        for name, kws in keywords.items():
            scores[name] = sum(1 for kw in kws if kw in all_text)
        
        if max(scores.values()) > 0:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        return "Другое"

    def process_clusters(
        self, 
        embeddings: np.ndarray, 
        messages: List[str],
        request_ids: List[int]
    ) -> Tuple[Dict[int, List[int]], List[UseCase]]:
        clusters = self.cluster(embeddings)
        use_cases = []
        
        for cluster_id, indices in clusters.items():
            is_noise = cluster_id == -1
            rep_messages = self.get_representative_messages(indices, embeddings, messages)
            use_case_name = self.name_cluster(rep_messages, is_noise=is_noise)
            
            for idx in indices:
                use_cases.append(UseCase(
                    request_id=request_ids[idx],
                    cluster_id=cluster_id,
                    use_case=use_case_name,
                    member_count=len(indices)
                ))
        
        return clusters, use_cases
