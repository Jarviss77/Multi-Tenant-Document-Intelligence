from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime

from app.core.auth import get_tenant_from_api_key
from app.core.rate_limiter import rate_limit_dependency
from app.core.config import settings
from app.services.search_service import SearchService
from app.utils.logger import get_logger
from app.utils.dto.search import SearchRequest, ChunkSearchResponse, ChunkSearchResult, SearchStats

logger = get_logger(__name__)
router = APIRouter()

# Initialize search service
search_service = SearchService()



@router.post("/semantic", response_model=ChunkSearchResponse, dependencies=[Depends(rate_limit_dependency(action="searches", max_requests=settings.SEARCHES_PER_MINUTE, window_seconds=60))])
async def chunk_search(
    request: SearchRequest,
    tenant=Depends(get_tenant_from_api_key)
):
    """
    Perform semantic search on document chunks.
    Returns individual chunks that match the query, providing more granular results.
    """
    try:
        # log_request(logger, "chunk_search", tenant.id, {"query": request.query, "top_k": request.top_k}, response_time=request.response_time)
        
        # Perform chunk-based search
        results, timing_stats = await search_service.search_chunks(
            query=request.query,
            tenant_id=tenant.id,
            top_k=request.top_k,
            min_score=request.min_score,
            include_content=request.include_content,
            filters=request.filters
        )
        print(results)
        
        # Convert results to response format
        chunk_results = []
        for result in results:
            chunk_results.append(ChunkSearchResult(
                chunk_id=result["chunk_id"],
                document_id=result["document_id"],
                document_title=result["document_title"],
                content=result["content"],
                chunk_index=result["chunk_index"],
                size=result["size"],
                similarity_score=result["similarity_score"],
                metadata=result["metadata"],
                document_created_at=result["document_created_at"],
                chunk_created_at=result["chunk_created_at"]
            ))
        
        response = ChunkSearchResponse(
            query=request.query,
            total_results=len(chunk_results),
            results=chunk_results,
            search_time_ms=timing_stats.get("search_time_ms", 0.0),
            embedding_time_ms=timing_stats.get("embedding_time_ms", 0.0),
            vector_search_time_ms=timing_stats.get("vector_search_time_ms", 0.0)
        )
        
        logger.info(f"Chunk search completed: {len(results)} results in {timing_stats['search_time_ms']:.2f}ms")
        return response
        
    except Exception as e:
        logger.error(f"Chunk search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chunk search failed: {str(e)}")

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
