import tiktoken
from typing import List, Tuple
from schemas import Message, TokenCounts


class TokenCounter:
    def __init__(self, model: str = "cl100k_base"):
        self.encoder = tiktoken.get_encoding(model)

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self.encoder.encode(text))

    def count_messages(self, messages: List[Message]) -> TokenCounts:
        user_tokens = 0
        assistant_tokens = 0
        tool_tokens = 0

        for msg in messages:
            if msg.role == "user":
                user_tokens += self.count_tokens(msg.content)
            elif msg.role == "assistant":
                assistant_tokens += self.count_tokens(msg.content)
            elif msg.role == "tool":
                tool_content = msg.content or ""
                if msg.arguments:
                    tool_content += str(msg.arguments)
                if msg.result:
                    tool_content += str(msg.result)
                tool_tokens += self.count_tokens(tool_content)

        total = user_tokens + assistant_tokens + tool_tokens
        estimated_cost = (total / 1000) * 0.0001

        return TokenCounts(
            user_tokens=user_tokens,
            assistant_tokens=assistant_tokens,
            tool_tokens=tool_tokens,
            total_tokens=total,
            estimated_cost=estimated_cost
        )
