# Validation Guide for Performance Optimizations

This guide explains how to validate the performance improvements made to the system.

## Prerequisites

- Docker and Docker Compose installed
- API keys for Gemini and Pinecone configured
- System running with the optimizations applied

## Manual Validation Steps

### 1. Verify Database Indexes

After running migrations, check that indexes were created:

```bash
# Connect to the database
docker-compose exec db psql -U postgres -d document_intelligence

# Check indexes on chunks table
\d chunks

# Check indexes on documents table
\d documents

# Check indexes on embedding_jobs table
\d embedding_jobs
```

Expected output should show indexes on:
- `chunks`: document_id, tenant_id, and composite index idx_chunks_tenant_document
- `documents`: tenant_id, created_at
- `embedding_jobs`: document_id, tenant_id, chunk_id, status, and composite index idx_embedding_jobs_tenant_status

### 2. Verify Concurrent Embedding Processing

Monitor the application logs during document upload:

```bash
# Watch application logs
docker-compose logs -f app

# Upload a large document via API
curl -X POST "http://localhost:8000/api/v1/uploads" \
  -H "X-API-Key: your-api-key" \
  -F "file=@large_document.pdf"
```

Expected behavior:
- Multiple embedding generation operations should run concurrently
- Total processing time should be significantly reduced for documents with many chunks

### 3. Verify Bulk Insert Operations

Check the logs for bulk insert operations:

```bash
# Look for BULK_INSERT log entries
docker-compose logs app | grep "BULK_INSERT"
```

Expected output:
- Should see `BULK_INSERT` for `document_chunks` instead of multiple individual `INSERT` operations
- Should see `BULK_INSERT` for `embedding_jobs` instead of multiple individual `INSERT` operations

### 4. Verify Database Echo Disabled

```bash
# Check application logs - should NOT see verbose SQL queries
docker-compose logs app | grep "SELECT" | head -5
```

Expected output:
- Should NOT see raw SQL queries being logged (unless explicitly logged by application code)
- Only application-level log messages should appear

### 5. Verify Non-Blocking I/O

Monitor event loop performance:

```bash
# Check metrics endpoint
curl http://localhost:8000/metrics | grep -E "http_request_duration|embedding_generation"
```

Expected behavior:
- Request duration should not be blocked during external API calls
- Multiple concurrent requests should be processed efficiently

### 6. Performance Benchmarking

#### Before vs After Comparison

Use Apache Bench or similar tool to test:

```bash
# Test search endpoint
ab -n 100 -c 10 \
  -H "X-API-Key: your-api-key" \
  -T "application/json" \
  -p search_payload.json \
  http://localhost:8000/api/v1/search/semantic
```

Create `search_payload.json`:
```json
{
  "query": "test query",
  "top_k": 10,
  "min_score": 0.0,
  "include_content": true
}
```

Expected improvements:
- Mean response time should be 30-50% faster
- Throughput (requests/second) should increase by 2-3x

#### Upload Performance Test

```bash
# Time a document upload
time curl -X POST "http://localhost:8000/api/v1/uploads" \
  -H "X-API-Key: your-api-key" \
  -F "file=@test_document.pdf"
```

Expected improvements:
- For documents with 100+ chunks: 5-10x faster chunk creation
- For documents with many chunks: Embedding job creation should be nearly instant

## Automated Validation

### Python Validation Script

Create and run a validation script:

```python
import asyncio
import time
from app.services.embedding_service import GeminiEmbeddingService

async def test_concurrent_embeddings():
    """Test that embeddings are processed concurrently."""
    service = GeminiEmbeddingService()
    texts = ["test text " + str(i) for i in range(10)]
    
    # Test sequential (for comparison)
    start = time.time()
    sequential_results = []
    for text in texts:
        result = await service.embed_text(text)
        sequential_results.append(result)
    sequential_time = time.time() - start
    
    # Test concurrent (new implementation)
    start = time.time()
    concurrent_results = await service.embed_batch(texts)
    concurrent_time = time.time() - start
    
    print(f"Sequential time: {sequential_time:.2f}s")
    print(f"Concurrent time: {concurrent_time:.2f}s")
    print(f"Speedup: {sequential_time/concurrent_time:.2f}x")
    
    assert len(concurrent_results) == len(texts)
    assert concurrent_time < sequential_time

if __name__ == "__main__":
    asyncio.run(test_concurrent_embeddings())
```

### Database Query Performance Test

```sql
-- Test query performance with indexes
EXPLAIN ANALYZE
SELECT * FROM chunks
WHERE tenant_id = 'test-tenant' 
  AND document_id = 'test-doc';

-- Compare with query without indexes (if you have before/after data)
-- Should see "Index Scan" instead of "Seq Scan"
```

## Key Performance Indicators (KPIs)

Monitor these metrics in Grafana:

1. **API Response Times**
   - p50, p95, p99 latencies should decrease by 30-50%
   
2. **Database Query Times**
   - Average query execution time should decrease by 50-90%
   
3. **Throughput**
   - Requests/second should increase by 2-3x
   
4. **Resource Usage**
   - CPU usage should be more evenly distributed (due to non-blocking I/O)
   - Memory usage may slightly increase (Spacy model caching) but should stabilize

## Troubleshooting

### If Performance Hasn't Improved

1. **Check that migrations ran successfully**
   ```bash
   docker-compose exec app alembic current
   ```

2. **Verify indexes exist**
   ```sql
   SELECT tablename, indexname FROM pg_indexes 
   WHERE schemaname = 'public';
   ```

3. **Check for blocking operations**
   - Monitor event loop lag
   - Check for synchronous operations in async code

4. **Verify thread pool configuration**
   - Ensure sufficient threads for executor operations
   
### If Seeing Errors

1. **Database migration errors**: Run `alembic upgrade head` again
2. **Import errors**: Ensure all dependencies are installed
3. **Runtime errors**: Check application logs for stack traces

## Success Criteria

✅ All indexes created successfully  
✅ Bulk inserts appearing in logs  
✅ Concurrent embedding processing working  
✅ Non-blocking I/O verified  
✅ Response times improved by 30%+  
✅ Throughput increased by 2x+  
✅ No regression in functionality  

## Next Steps

After validation:

1. Monitor production metrics for 24-48 hours
2. Compare before/after performance data
3. Document any additional optimization opportunities
4. Consider implementing caching layer if needed
5. Review and tune connection pool settings if necessary
