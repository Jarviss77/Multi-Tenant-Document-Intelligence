import time
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.future import select
from app.services.embedding_service import GeminiEmbeddingService
from app.services.vector_store import PineconeVectorStore
from app.db.models.document import Document
from app.db.models.chunks import Chunk
from app.db.sessions import AsyncSessionLocal
from app.db.base import load_all_models
from app.utils.logger import get_logger, log_embedding_operation, log_database_operation

load_all_models()

logger = get_logger("services.search")


class SearchService:

    def __init__(self):
        self.embedding_service = GeminiEmbeddingService()
        self.vector_store = PineconeVectorStore()
    
    async def search_documents(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 10,
        min_score: float = 0.0,
        include_content: bool = True,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        """
        Perform semantic search on documents for a specific tenant.
        
        Args:
            query: Search query text
            tenant_id: Tenant ID to search within
            top_k: Number of results to return
            min_score: Minimum similarity score threshold
            include_content: Whether to include document content
            filters: Additional filters for the search
            
        Returns:
            Tuple of (search_results, timing_stats)
        """
        start_time = time.time()
        timing_stats = {}
        
        try:
            # Generate embedding for the query
            embedding_start = time.time()
            log_embedding_operation(logger, "GENERATE", "query", tenant_id)
            query_embedding = await self.embedding_service.embed_text(query)
            embedding_time = (time.time() - embedding_start) * 1000
            timing_stats["embedding_time_ms"] = embedding_time
            logger.info(f"Generated query embedding in {embedding_time:.2f}ms")
            
            # Perform vector search
            vector_search_start = time.time()
            
            # Build filter for tenant isolation
            search_filter = {"tenant_id": tenant_id}
            if filters:
                search_filter.update(filters)
            
            log_embedding_operation(logger, "SEARCH", "query", tenant_id)

            vector_results = await self.vector_store.query_vectors(
                vector=query_embedding,
                top_k=top_k,
                filter=search_filter
            )
            vector_search_time = (time.time() - vector_search_start) * 1000
            timing_stats["vector_search_time_ms"] = vector_search_time
            logger.info(f"Vector search completed in {vector_search_time:.2f}ms, found {len(vector_results)} results")
            
            # Filter by minimum score and extract document IDs
            filtered_results = []
            for result in vector_results:
                if result.score >= min_score:

                    # Extract document ID from the vector ID format "tenant_id:document_id"
                    doc_id = result.id.split(":", 1)[1] if ":" in result.id else result.id
                    filtered_results.append({
                        "document_id": doc_id,
                        "similarity_score": result.score,
                        "metadata": result.metadata or {}
                    })
            
            logger.info(f"Filtered to {len(filtered_results)} results above score {min_score}")
            
            # Fetch document details from database
            if not filtered_results:
                timing_stats["search_time_ms"] = (time.time() - start_time) * 1000
                return [], timing_stats
            
            db_start = time.time()
            doc_ids = [result["document_id"] for result in filtered_results]
            
            async with AsyncSessionLocal() as db:
                log_database_operation(logger, "SELECT", "documents", f"batch_{len(doc_ids)}")
                
                # Build query based on whether content is needed
                if include_content:
                    query_stmt = select(Document).where(Document.id.in_(doc_ids))
                else:
                    query_stmt = select(
                        Document.id, 
                        Document.title, 
                        Document.created_at
                    ).where(Document.id.in_(doc_ids))
                
                result = await db.execute(query_stmt)
                documents = result.scalars().all() if include_content else result.all()
                
                # Convert to dictionary for easier lookup
                doc_dict = {}
                if include_content:
                    for doc in documents:
                        doc_dict[doc.id] = {
                            "id": doc.id,
                            "title": doc.title,
                            "content": doc.content,
                            "created_at": doc.created_at
                        }
                else:
                    for doc in documents:
                        doc_dict[doc.id] = {
                            "id": doc.id,
                            "title": doc.title,
                            "content": None,
                            "created_at": doc.created_at
                        }
            
            db_time = (time.time() - db_start) * 1000
            timing_stats["db_query_time_ms"] = db_time
            logger.info(f"Database query completed in {db_time:.2f}ms")
            
            # Combine vector results with document data
            search_results = []
            for vector_result in filtered_results:
                doc_id = vector_result["document_id"]
                if doc_id in doc_dict:
                    doc_data = doc_dict[doc_id]
                    search_results.append({
                        "document_id": doc_id,
                        "title": doc_data["title"],
                        "content": doc_data["content"] if include_content else None,
                        "similarity_score": vector_result["similarity_score"],
                        "metadata": vector_result["metadata"],
                        "created_at": doc_data["created_at"]
                    })
            
            # Sort by similarity score (highest first)
            search_results.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            total_time = (time.time() - start_time) * 1000
            timing_stats["search_time_ms"] = total_time
            
            logger.info(f"Search completed in {total_time:.2f}ms, returning {len(search_results)} results")
            return search_results, timing_stats
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            timing_stats["search_time_ms"] = (time.time() - start_time) * 1000
            raise
    
    async def get_search_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get search statistics for a tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Dictionary with search statistics
        """
        try:
            async with AsyncSessionLocal() as db:
                # Count total documents for tenant
                log_database_operation(logger, "COUNT", "documents", tenant_id)
                result = await db.execute(
                    select(Document).where(Document.tenant_id == tenant_id)
                )
                documents = result.scalars().all()
                total_documents = len(documents)
                
                logger.info(f"Found {total_documents} documents for tenant {tenant_id}")
                
                return {
                    "total_documents": total_documents,
                    "tenant_id": tenant_id
                }
                
        except Exception as e:
            logger.error(f"Failed to get search stats: {e}")
            raise
    
    async def search_chunks(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 10,
        min_score: float = 0.0,
        include_content: bool = True,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        """
        Perform semantic search on document chunks for a specific tenant.
        
        Args:
            query: Search query text
            tenant_id: Tenant ID to search within
            top_k: Number of results to return
            min_score: Minimum similarity score threshold
            include_content: Whether to include chunk content
            filters: Additional filters for the search
            
        Returns:
            Tuple of (search_results, timing_stats)
        """
        start_time = time.time()
        timing_stats = {}
        
        try:
            # Generate embedding for the query
            embedding_start = time.time()
            log_embedding_operation(logger, "GENERATE", "query", tenant_id)
            query_embedding = await self.embedding_service.embed_text(query)
            embedding_time = (time.time() - embedding_start) * 1000
            timing_stats["embedding_time_ms"] = embedding_time
            logger.info(f"Generated query embedding in {embedding_time:.2f}ms")
            
            # Perform vector search
            vector_search_start = time.time()
            
            # Build filter for tenant isolation
            search_filter = {"tenant_id": tenant_id}
            if filters:
                search_filter.update(filters)
            
            log_embedding_operation(logger, "SEARCH", "query", tenant_id)

            vector_results = await self.vector_store.query_vectors(
                vector=query_embedding,
                top_k=top_k,
                filter=search_filter
            )
            vector_search_time = (time.time() - vector_search_start) * 1000
            timing_stats["vector_search_time_ms"] = vector_search_time
            logger.info(f"Vector search completed in {vector_search_time:.2f}ms, found {len(vector_results)} results")
            
            # Filter by minimum score and extract chunk IDs
            filtered_results = []
            for result in vector_results:
                if result.score >= min_score:
                    # Extract chunk ID from the vector ID format "tenant_id:chunk_id"
                    chunk_id = result.id.split(":", 1)[1] if ":" in result.id else result.id
                    filtered_results.append({
                        "chunk_id": chunk_id,
                        "similarity_score": result.score,
                        "metadata": result.metadata or {}
                    })
            
            logger.info(f"Filtered to {len(filtered_results)} results above score {min_score}")
            
            # Fetch chunk details from database
            if not filtered_results:
                timing_stats["search_time_ms"] = (time.time() - start_time) * 1000
                return [], timing_stats
            
            db_start = time.time()
            chunk_ids = [result["chunk_id"] for result in filtered_results]
            
            async with AsyncSessionLocal() as db:
                log_database_operation(logger, "SELECT", "document_chunks", f"batch_{len(chunk_ids)}")
                
                # Build query to get chunks with document information
                query_stmt = select(
                    Chunk,
                    Document.title.label("document_title"),
                    Document.created_at.label("document_created_at")
                ).join(
                    Document, Chunk.document_id == Document.id
                ).where(Chunk.id.in_(chunk_ids))
                
                result = await db.execute(query_stmt)
                chunk_data = result.all()
                
                # Convert to dictionary for easier lookup
                chunk_dict = {}
                for chunk, doc_title, doc_created_at in chunk_data:
                    chunk_dict[chunk.id] = {
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "document_title": doc_title,
                        "content": chunk.content if include_content else None,
                        "chunk_index": chunk.chunk_index,
                        "size": chunk.size,
                        "document_created_at": doc_created_at,
                        "chunk_created_at": chunk.created_at
                    }
            
            db_time = (time.time() - db_start) * 1000
            timing_stats["db_query_time_ms"] = db_time
            logger.info(f"Database query completed in {db_time:.2f}ms")
            
            # Combine vector results with chunk data
            search_results = []
            for vector_result in filtered_results:
                chunk_id = vector_result["chunk_id"]
                if chunk_id in chunk_dict:
                    chunk_data = chunk_dict[chunk_id]
                    search_results.append({
                        "chunk_id": chunk_id,
                        "document_id": chunk_data["document_id"],
                        "document_title": chunk_data["document_title"],
                        "content": chunk_data["content"],
                        "chunk_index": chunk_data["chunk_index"],
                        "size": chunk_data["size"],
                        "similarity_score": vector_result["similarity_score"],
                        "metadata": vector_result["metadata"],
                        "document_created_at": chunk_data["document_created_at"],
                        "chunk_created_at": chunk_data["chunk_created_at"]
                    })
            
            # Sort by similarity score (highest first)
            search_results.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            total_time = (time.time() - start_time) * 1000
            timing_stats["search_time_ms"] = total_time
            
            logger.info(f"Chunk search completed in {total_time:.2f}ms, returning {len(search_results)} results")
            return search_results, timing_stats
            
        except Exception as e:
            logger.error(f"Chunk search failed: {e}")
            timing_stats["search_time_ms"] = (time.time() - start_time) * 1000
            raise
