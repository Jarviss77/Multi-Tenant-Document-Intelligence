from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.auth import get_tenant_from_api_key
from app.core.rate_limiter import rate_limit_dependency
from app.core.config import settings
from app.services.search_service import SearchService
from app.utils.logger import get_logger, log_request
from pydantic import BaseModel, Field

logger = get_logger(__name__)
router = APIRouter()

# Initialize search service
search_service = SearchService()


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query text", min_length=1, max_length=1000)
    top_k: int = Field(default=10, description="Number of results to return", ge=1, le=100)
    min_score: float = Field(default=0.0, description="Minimum similarity score", ge=0.0, le=1.0)
    include_content: bool = Field(default=True, description="Include document content in results")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Additional filters")


class SearchResult(BaseModel):
    document_id: str = Field(..., description="Document ID")
    title: str = Field(..., description="Document title")
    content: Optional[str] = Field(None, description="Document content (if requested)")
    similarity_score: float = Field(..., description="Similarity score (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(..., description="Document creation date")


class SearchResponse(BaseModel):
    query: str = Field(..., description="Original search query")
    total_results: int = Field(..., description="Total number of results found")
    results: List[SearchResult] = Field(..., description="Search results")
    search_time_ms: float = Field(..., description="Search execution time in milliseconds")
    embedding_time_ms: float = Field(..., description="Embedding generation time in milliseconds")
    vector_search_time_ms: float = Field(..., description="Vector search time in milliseconds")


class SearchStats(BaseModel):
    """Search statistics"""
    total_documents: int = Field(..., description="Total documents in tenant's index")
    search_time_ms: float = Field(..., description="Total search time")
    embedding_time_ms: float = Field(..., description="Embedding generation time")
    vector_search_time_ms: float = Field(..., description="Vector search time")
    db_query_time_ms: float = Field(..., description="Database query time")


@router.post("/semantic", response_model=SearchResponse, dependencies=[Depends(rate_limit_dependency(action="searches", max_requests=settings.SEARCHES_PER_MINUTE, window_seconds=60))])
async def semantic_search(
    request: SearchRequest,
    tenant=Depends(get_tenant_from_api_key)
):
    """
    Perform semantic search on documents using vector similarity.
    
    This endpoint uses embeddings to find documents that are semantically
    similar to the search query, rather than just keyword matching.
    """
    try:
        logger.info(f"Semantic search request from tenant {tenant.id}: '{request.query}'")
        
        # Perform the search
        search_results, timing_stats = await search_service.search_documents(
            query=request.query,
            tenant_id=tenant.id,
            top_k=request.top_k,
            min_score=request.min_score,
            include_content=request.include_content,
            filters=request.filters
        )
        
        # Convert results to response format
        results = [
            SearchResult(
                document_id=result["document_id"],
                title=result["title"],
                content=result["content"],
                similarity_score=result["similarity_score"],
                metadata=result["metadata"],
                created_at=result["created_at"]
            )
            for result in search_results
        ]
        
        response = SearchResponse(
            query=request.query,
            total_results=len(results),
            results=results,
            search_time_ms=timing_stats["search_time_ms"],
            embedding_time_ms=timing_stats["embedding_time_ms"],
            vector_search_time_ms=timing_stats["vector_search_time_ms"]
        )
        
        logger.info(f"Search completed: {len(results)} results in {timing_stats['search_time_ms']:.2f}ms")
        return response
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.get("/stats", response_model=SearchStats)
async def get_search_stats(
    tenant=Depends(get_tenant_from_api_key)
):
    """
    Get search statistics for the tenant.
    """
    try:
        logger.info(f"Getting search stats for tenant {tenant.id}")
        
        stats = await search_service.get_search_stats(tenant.id)
        
        return SearchStats(
            total_documents=stats["total_documents"],
            search_time_ms=0.0,  # No search performed
            embedding_time_ms=0.0,
            vector_search_time_ms=0.0,
            db_query_time_ms=0.0
        )
        
    except Exception as e:
        logger.error(f"Failed to get search stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/health")
async def search_health_check():
    """
    Health check endpoint for search service.
    """
    try:
        # Test if services are available
        # This is a simple check - in production you might want more thorough checks
        return {
            "status": "healthy",
            "service": "search",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Search health check failed: {e}")
        raise HTTPException(status_code=503, detail="Search service unhealthy")
