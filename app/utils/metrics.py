"""Prometheus metrics for workers and application monitoring"""
from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client import start_http_server
import asyncio

# Kafka consumer metrics
kafka_messages_consumed = Counter(
    'kafka_messages_consumed_total',
    'Total number of Kafka messages consumed',
    ['consumer_group', 'topic']
)

kafka_messages_processed = Counter(
    'kafka_messages_processed_total',
    'Total number of Kafka messages processed successfully',
    ['consumer_group', 'topic']
)

kafka_messages_failed = Counter(
    'kafka_messages_failed_total',
    'Total number of Kafka messages failed',
    ['consumer_group', 'topic', 'error_type']
)

kafka_message_processing_duration = Histogram(
    'kafka_message_processing_duration_seconds',
    'Time spent processing Kafka messages',
    ['consumer_group', 'topic'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

kafka_messages_in_flight = Gauge(
    'kafka_messages_in_flight',
    'Number of Kafka messages currently being processed',
    ['consumer_group', 'topic']
)

# Task processing metrics
tasks_processed_total = Counter(
    'embedding_tasks_processed_total',
    'Total number of embedding tasks processed',
    ['status']  # completed, failed
)

tasks_processing_duration = Histogram(
    'embedding_task_processing_duration_seconds',
    'Time spent processing embedding tasks',
    ['operation'],  # embedding_generation, vector_storage, total
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

tasks_in_progress = Gauge(
    'embedding_tasks_in_progress',
    'Number of embedding tasks currently being processed'
)

# Kafka producer metrics
kafka_messages_produced = Counter(
    'kafka_messages_produced_total',
    'Total number of Kafka messages produced',
    ['producer', 'topic']
)

kafka_produce_errors = Counter(
    'kafka_produce_errors_total',
    'Total number of Kafka produce errors',
    ['producer', 'topic', 'error_type']
)

# Database metrics
database_operations = Counter(
    'database_operations_total',
    'Total number of database operations',
    ['operation', 'table', 'status']
)

database_operation_duration = Histogram(
    'database_operation_duration_seconds',
    'Time spent on database operations',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

# Vector store metrics
vector_store_operations = Counter(
    'vector_store_operations_total',
    'Total number of vector store operations',
    ['operation', 'status']
)

vector_store_operation_duration = Histogram(
    'vector_store_operation_duration_seconds',
    'Time spent on vector store operations',
    ['operation'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Embedding service metrics
embedding_generation_total = Counter(
    'embedding_generation_total',
    'Total number of embeddings generated',
    ['status']  # success, failed
)

embedding_generation_duration = Histogram(
    'embedding_generation_duration_seconds',
    'Time spent generating embeddings',
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0]
)

# Worker health metrics
worker_up = Gauge(
    'worker_up',
    'Worker status (1 if up, 0 if down)',
    ['worker_id', 'worker_type']
)

def start_metrics_server(port=8001):
    """Start Prometheus metrics server"""
    start_http_server(port)
    print(f"Prometheus metrics server started on port {port}")

