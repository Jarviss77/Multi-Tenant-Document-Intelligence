import re
import spacy
from typing import List, Dict, Any
from abc import ABC, abstractmethod
from app.utils.tokenizer import Tokenizer

# Factory pattern for chunking strategies
class ChunkingStrategy(ABC):
    @abstractmethod
    def chunk(self, text: str) -> List[Dict[str, Any]]:
        pass


class FixedSizeChunking(ChunkingStrategy):
    """Simple fixed-size chunking with overlap."""

    def chunk(self, text: str, chunk_size: int = 100, overlap: int = 20) -> List[Dict[str, Any]]:
        chunks = []
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]

            chunks.append({
                "text": chunk_text,
                "start_char": start,
                "end_char": end,
                "chunk_size": len(chunk_text)
            })

            start += chunk_size - overlap

        return chunks


class SentenceAwareChunking(ChunkingStrategy):
    def __init__(self, lightweight: bool = False):
        self.tokenizer = Tokenizer(lightweight=lightweight)

    def chunk(self, text: str, chunk_size: int = 100, overlap: int = 20) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []

        sentences = self.tokenizer.tokenize(text=text)

        chunks = []
        current_chunk = ""
        current_start = 0

        for sentence in sentences:
            sent_len = len(sentence)

            # If adding the sentence exceeds the chunk size, save the current chunk
            if len(current_chunk) + sent_len > chunk_size and current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "start_char": current_start,
                    "end_char": current_start + len(current_chunk),
                    "chunk_size": len(current_chunk)
                })

                # Overlap management
                overlap_text = current_chunk[-overlap:] if overlap > 0 else ""
                current_start = current_start + len(current_chunk) - len(overlap_text)
                current_chunk = overlap_text + " " + sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        # Add final chunk
        if current_chunk:
            chunks.append({
                "text": current_chunk.strip(),
                "start_char": current_start,
                "end_char": current_start + len(current_chunk),
                "chunk_size": len(current_chunk)
            })

        return chunks


class ChunkingStrategyFactory:
    def __init__(self):
        self.strategies = {
            "fixed_size": FixedSizeChunking(),
            "sentence_aware": SentenceAwareChunking(),
        }

    def chunk_document(
            self,
            text: str,
            strategy: str,
            **kwargs
    ) -> List[Dict[str, Any]]:
        if strategy not in self.strategies:
            raise ValueError(f"Unknown chunking strategy: {strategy}")

        return self.strategies[strategy].chunk(text, **kwargs)

    def get_available_strategies(self) -> List[str]:
        return list(self.strategies.keys())

chunking_strategy = ChunkingStrategyFactory()


# Example usage (can be removed in production)
# if __name__ == "__main__":
#     text = (
#         "SpaCy is a great NLP library. It can segment sentences very well! "
#         "You can use it for tokenization, parsing, and more. "
#         "This chunking method respects sentence boundaries."
#     )
#
#     print("=== FixedSizeChunking ===")
#     fixed = FixedSizeChunking().chunk(text, chunk_size=50, overlap=10)
#     for ch in fixed:
#         print(ch, "\n")
#
#     print("=== SentenceAwareChunking ===")
#     sentence_based = SentenceAwareChunking().chunk(text, chunk_size=80, overlap=10)
#     for ch in sentence_based:
#         print(ch, "\n")
