## Workers Overview
The Multi-Tenant Document Intelligence system employs a worker-based architecture to handle document processing efficiently. Workers are responsible for consuming messages from the Kafka message queue, processing documents, generating embeddings, and storing them in the vector database. This modular approach allows for scalability and fault tolerance.

### v1 Workers
In the initial version (v1) of the system, a single type of worker is implemented to handle all document processing tasks. The v1 worker performs the following steps:
1. **Message Consumption**: Listens to the Kafka topic for new document messages.
2. **Document Retrieval**: Fetches the document from PostgreSQL based on the message.
3. **Generation of Embeddings**: Sends the document to the Gemini API to generate embeddings.
4. **Storage**: Stores the generated embeddings in the Pinecone vector database, tagged with the tenant ID.
5. **Status Update**: Updates the document status in PostgreSQL to indicate completion.

#### Retry Mechanism
The v1 worker includes a basic retry mechanism to handle transient errors when communicating with external services like the Gemini API or Pinecone. If a request fails, the worker will retry a configurable number of times before logging an error.

### v2 Workers
The v2 version of the workers introduces several enhancements to improve performance, scalability, and reliability. The key features of the v2 workers include:
1. **Parallel Processing**: The v2 workers are designed to process multiple documents concurrently, leveraging asynchronous programming techniques to maximize throughput.
2. **Advanced Error Handling**: The v2 workers implement more sophisticated error handling strategies, including exponential backoff for retries and detailed logging for easier debugging.
3. **Retry Queue**: Failed messages are placed in a retry queue, allowing for delayed reprocessing without blocking the main processing flow.
4. **Dead Letter Queue**: Failed messages that exceed the retry limit are sent to a dead letter queue for further analysis and manual intervention.
5. **Idempotency**: The v2 workers ensure that processing is idempotent, preventing duplicate embeddings from being created for the same document.

## Job Workflow
![Worker Workflow Diagram](docs/images/worker.png)
The worker workflow consists of the following steps:
1. **Consume Message**: The worker consumes a message from the Kafka topic indicating a new document to process.
2. **Fetch Document**: The worker retrieves the document from PostgreSQL using the document ID provided in the message.
3. **Generate Embeddings**: The document is sent to the Gemini API to generate embeddings.
4. **Store Embeddings**: The generated embeddings are stored in the Pinecone vector database
5. **Update Status**: The worker updates the document status in PostgreSQL to reflect the processing outcome.
6. **Handle Failures**: If any step fails, the worker implements the retry mechanism or routes the message to the appropriate queue (retry or dead letter).

