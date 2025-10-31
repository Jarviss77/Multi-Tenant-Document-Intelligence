import google.generativeai as genai
from app.core.config import settings
from typing import List
import asyncio
from functools import partial

GEMINI_API_KEY = settings.GEMINI_API_KEY
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in environment")

genai.configure(api_key=GEMINI_API_KEY)

class GeminiEmbeddingService:

    def __init__(self, model: str = "text-embedding-004"):
        self.model = model

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text using thread executor to avoid blocking."""
        if not text.strip():
            return []

        try:
            # Run blocking genai operation in thread executor
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                partial(
                    genai.embed_content,
                    model=self.model,
                    content=text,
                    task_type="retrieval_document"
                )
            )

            return result['embedding']
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return []

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts concurrently for better performance."""
        # Process all embeddings concurrently instead of sequentially
        # Use return_exceptions=True to handle individual failures gracefully
        embedding_tasks = [self.embed_text(text) for text in texts]
        embeddings = await asyncio.gather(*embedding_tasks, return_exceptions=True)
        
        # Filter out exceptions and return successful embeddings
        # Failed embeddings will be empty lists (as returned by embed_text on error)
        return [emb if not isinstance(emb, Exception) else [] for emb in embeddings]