from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

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


class ChunkSearchResult(BaseModel):
    chunk_id: str = Field(..., description="Chunk ID")
    document_id: str = Field(..., description="Document ID")
    document_title: str = Field(..., description="Document title")
    content: Optional[str] = Field(None, description="Chunk content (if requested)")
    chunk_index: int = Field(..., description="Index of chunk within document")
    size: int = Field(..., description="Total number of chunks in document")
    similarity_score: float = Field(..., description="Similarity score (0-1)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    document_created_at: datetime = Field(..., description="Document creation date")
    chunk_created_at: datetime = Field(..., description="Chunk creation date")


class ChunkSearchResponse(BaseModel):
    query: str = Field(..., description="Original search query")
    total_results: int = Field(..., description="Total number of results found")
    results: List[ChunkSearchResult] = Field(..., description="Search results")
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