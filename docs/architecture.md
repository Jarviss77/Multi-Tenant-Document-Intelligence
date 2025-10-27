## Architecture
The architecture of the Multi-Tenant Document Intelligence system is designed to efficiently handle document ingestion, processing, storage, and querying across multiple tenants. The key components of the architecture are as follows:

## Basic Overview
![Architecture Diagram](docs/images/architecture.png)

## Workflow
![Workflow Diagram](docs/images/workflow.png)
### **Document Ingestion**:
- Users upload documents through the FastAPI application. Each document is associated with a specific tenant.
- The application stores the raw documents in PostgreSQL and sends a message to Kafka for processing.

### **Document Processing**:
- A Kafka worker listens for new document messages. Upon receiving a message, it retrieves the document from PostgreSQL.

### **Chunking**
- Supports 2 types of chunking:
  - **Simple Chunking**: Splits text into fixed-size chunks (e.g., 500 tokens) with optional overlap.
  - **Semantic Chunking**: Uses a language model (scapy(en_core_web_sm)) to create semantically meaningful chunks based on content.
- The document is chunked into smaller pieces for embedding.
- Each chunk is sent to the Gemini API to generate embeddings.

### **Embedding Generation**:
- The Gemini API generates high-dimensional vector embeddings for each document chunk.

### **Vector Storage**:
- The generated embeddings are stored in the Pinecone vector database, tagged with the tenant ID for isolation.
- Once processing is complete, the worker updates the document status in PostgreSQL.

### **Querying**:
- Users can send search queries through the FastAPI application.
- The application generates an embedding for the query using the Gemini API.
- It then queries the Pinecone vector database for similar document chunks, filtered by tenant ID.
- The application retrieves the relevant documents from PostgreSQL and returns them to the user.

More detailed Overview of workers v1 and v2 can be found in [docs/workers.md](docs/workers.md).