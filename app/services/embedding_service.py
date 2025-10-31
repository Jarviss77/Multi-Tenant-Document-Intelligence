import google.generativeai as genai
from app.core.config import settings
from typing import List

GEMINI_API_KEY = settings.GEMINI_API_KEY
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in environment")

genai.configure(api_key=GEMINI_API_KEY)

class GeminiEmbeddingService:

    def __init__(self, model: str = "text-embedding-004"):
        self.model = model

    async def embed_text(self, text: str) -> List[float]:
        if not text.strip():
            return []

        try:
            result = genai.embed_content(
                model=self.model,
                content=text,
                task_type="retrieval_document"
            )

            return result['embedding']
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return []

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts concurrently for better performance."""
        import asyncio
        
        # Process all embeddings concurrently instead of sequentially
        embedding_tasks = [self.embed_text(text) for text in texts]
        embeddings = await asyncio.gather(*embedding_tasks, return_exceptions=False)
        return embeddings