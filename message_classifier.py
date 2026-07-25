import json
import torch
from typing import List, Optional, Tuple
from schemas import Dialog, MessageClassification, MessageClassificationResult
from prompts import CLASSIFY_MESSAGES_PROMPT
from config import config


class MessageClassifier:
    def __init__(self, model=None, tokenizer=None, device=None):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        
        if model is None or tokenizer is None:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            print(f"Loading model for message classification: {config.models.llm_model}...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                config.models.llm_model,
                cache_dir=str(config.paths.models_dir)
            )
            # Оптимизации памяти:
            # 1. torch_dtype=torch.float16 для экономии памяти
            # 2. device_map="auto" для автоматического распределения
            # 3. low_cpu_mem_usage=True для экономии CPU памяти
            self.model = AutoModelForCausalLM.from_pretrained(
                config.models.llm_model,
                torch_dtype=torch.float16,
                device_map="auto",
                low_cpu_mem_usage=True,
                cache_dir=str(config.paths.models_dir)
            )
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print("Message classifier loaded successfully")
        
        # Очищаем кэш CUDA перед началом работы
        if self.device == "cuda":
            torch.cuda.empty_cache()
            print(f"GPU memory after loading: {torch.cuda.memory_allocated() / 1e9:.2f} GB")

    def _format_dialog(self, dialog: Dialog) -> str:
        """Форматируем диалог для промпта."""
        lines = []
        for i, msg in enumerate(dialog.messages):
            if msg.role == "user":
                lines.append(f"[{i}] User: {msg.content}")
            elif msg.role == "assistant":
                lines.append(f"[{i}] Agent: {msg.content}")
            elif msg.role == "tool":
                tool_info = f"{msg.tool_name}({json.dumps(msg.arguments) if msg.arguments else ''})"
                result_info = json.dumps(msg.result) if msg.result else ""
                lines.append(f"[{i}] Tool: {tool_info} → {result_info}")
        return "\n".join(lines)
    
    def _format_dialog_chunk(self, dialog: Dialog, message_indices: List[Tuple[int, any]]) -> str:
        """Форматируем только выбранные сообщения для чанка."""
        lines = []
        indices = set(idx for idx, _ in message_indices)
        
        for i, msg in enumerate(dialog.messages):
            if i in indices or msg.role == "user":
                if msg.role == "user":
                    lines.append(f"[{i}] User: {msg.content}")
                elif msg.role == "assistant":
                    lines.append(f"[{i}] Agent: {msg.content}")
                elif msg.role == "tool":
                    tool_info = f"{msg.tool_name}({json.dumps(msg.arguments) if msg.arguments else ''})"
                    result_info = json.dumps(msg.result) if msg.result else ""
                    lines.append(f"[{i}] Tool: {tool_info} → {result_info}")
        return "\n".join(lines)

    def classify_dialog(self, dialog: Dialog) -> MessageClassificationResult:
        """Классифицирует все сообщения агента в диалоге по чанкам."""
        max_chunk_tokens = 100000
        chunk_size = 20
        
        all_classifications = []
        burned_tokens = 0
        useful_count = 0
        useless_count = 0
        
        assistant_messages = [(i, msg) for i, msg in enumerate(dialog.messages) 
                              if msg.role in ["assistant", "tool"]]
        
        if not assistant_messages:
            return MessageClassificationResult(
                messages=[],
                burned_tokens=0,
                total_messages=0,
                useful_count=0,
                useless_count=0
            )
        
        for i in range(0, len(assistant_messages), chunk_size):
            chunk = assistant_messages[i:i + chunk_size]
            
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            chunk_dialog_text = self._format_dialog_chunk(dialog, chunk)
            prompt = CLASSIFY_MESSAGES_PROMPT.format(dialog_text=chunk_dialog_text)
            
            try:
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
                prompt_length = inputs.input_ids.shape[1]
                
                if prompt_length > max_chunk_tokens:
                    print(f"Warning: Chunk too long ({prompt_length}), skipping...")
                    del inputs
                    continue
                
                with torch.no_grad():
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=300,
                        pad_token_id=self.tokenizer.eos_token_id,
                        use_cache=True
                    )
                
                generated = self.tokenizer.decode(
                    outputs[0][inputs.input_ids.shape[1]:], 
                    skip_special_tokens=True
                ).strip()
                
                del outputs, inputs
                if self.device == "cuda":
                    torch.cuda.empty_cache()
                
                chunk_classifications = self._parse_response(generated, dialog.messages)
                all_classifications.extend(chunk_classifications)
                
                for cls in chunk_classifications:
                    if cls.is_useful:
                        useful_count += 1
                    else:
                        useless_count += 1
                        msg = dialog.messages[cls.message_index]
                        if msg.role == "assistant":
                            burned_tokens += self._count_tokens(msg.content)
                        elif msg.role == "tool":
                            tool_text = json.dumps(msg.arguments or {}) + json.dumps(msg.result or {})
                            burned_tokens += self._count_tokens(tool_text)
                
            except Exception as e:
                print(f"Error classifying chunk {i // chunk_size}: {e}")
                if self.device == "cuda":
                    torch.cuda.empty_cache()
        
        return MessageClassificationResult(
            messages=all_classifications,
            burned_tokens=burned_tokens,
            total_messages=len(all_classifications),
            useful_count=useful_count,
            useless_count=useless_count
        )

    def _parse_response(self, response: str, messages: List) -> List[MessageClassification]:
        """Парсит JSON ответ от модели с валидацией и нормализацией."""
        classifications = []
        
        # Очищаем ответ от markdown
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1].strip()
            if response.startswith("json"):
                response = response[3:].strip()
        
        # Пробуем распарсить JSON
        data = None
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Пробуем найти JSON в тексте
            import re
            json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except:
                    pass
        
        if not data or not isinstance(data, list):
            print(f"Warning: Invalid JSON response from LLM: {response[:200]}...")
            return classifications
        
        # Валидируем и нормализуем каждое сообщение
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            
            # message_index: должен быть int
            msg_idx = item.get("message_index")
            if msg_idx is None or not isinstance(msg_idx, (int, float, str)):
                continue
            try:
                msg_idx = int(msg_idx)
            except (ValueError, TypeError):
                continue
            
            # is_useful: нормализуем (true/false, 1/0, "true"/"false")
            is_useful_raw = item.get("is_useful")
            is_useful = self._normalize_boolean(is_useful_raw)
            
            # role: должен быть "assistant" или "tool"
            role = item.get("role", "assistant")
            if role not in ["assistant", "tool"]:
                role = "assistant"
            
            # reason: валидируем
            reason = item.get("reason", "other")
            valid_reasons = ["correct_execution", "tool_error", "wrong_tool_call", 
                           "partial_result", "repetition", "off_topic", "self_analysis", "other"]
            if reason not in valid_reasons:
                reason = "other"
            
            classifications.append(MessageClassification(
                message_index=msg_idx,
                role=role,
                is_useful=is_useful,
                reason=reason
            ))
        
        return classifications

    def _normalize_boolean(self, value) -> bool:
        """Нормализует значение в boolean."""
        if value is None:
            return True  # По умолчанию полезное
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, (int, float)):
            # 0, 0.0 → False; 1, 1.0 → True
            return bool(value)
        
        if isinstance(value, str):
            value = value.lower().strip()
            if value in ["true", "1", "yes", "да", "полезное", "useful"]:
                return True
            if value in ["false", "0", "no", "нет", "бесполезное", "useless"]:
                return False
            # Пробуем распарсить как число
            try:
                return bool(float(value))
            except:
                return True
        
        return bool(value)

    def _count_tokens(self, text: str) -> int:
        """Считает токены в тексте."""
        if not text:
            return 0
        try:
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            return len(encoder.encode(text))
        except:
            return len(text) // 4  # Грубая оценка

    def classify_batch(self, dialogs: List[Dialog]) -> List[MessageClassificationResult]:
        """Классифицирует сообщения в нескольких диалогах."""
        return [self.classify_dialog(dialog) for dialog in dialogs]
