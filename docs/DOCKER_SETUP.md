# Docker Setup Guide for Multi-Tenant Document Intelligence

This guide will help you set up and run the entire project using Docker Compose.

## Prerequisites

- Docker Desktop or Docker Engine installed
- Docker Compose v3.8 or higher
- At least 4GB of available RAM
- API keys for Gemini and Pinecone (if using those services)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Multi-Tenant-Document-Intelligence
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root. You can copy from `env.example`:

```bash
cp env.example .env
```

Edit the `.env` file and fill in your API keys:

```env
# Required API Keys
GEMINI_API_KEY=your_actual_gemini_api_key
PINECONE_API_KEY=your_actual_pinecone_api_key
PINECONE_INDEX_NAME=quickstart

# Optional: Customize other settings
SECRET_KEY=your_secure_random_string
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/document_intelligence
```

### 3. Start All Services

Build and start all containers:

```bash
docker-compose up -d --build
```

This will start:
- **PostgreSQL** database (port 5432)
- **Redis** for rate limiting (port 6379)
- **Kafka + Zookeeper** for message queue (ports 9092, 9093)
- **FastAPI application** (port 8000)
- **Kafka worker** for processing documents (port 8001)
- **Prometheus** for metrics (port 9090)
- **Grafana** for visualization (port 3000)

### 4. Check Service Status

```bash
docker-compose ps
```

### 5. View Logs

View logs for all services:
```bash
docker-compose logs -f
```

View logs for a specific service:
```bash
docker-compose logs -f app      # FastAPI app
docker-compose logs -f worker   # Kafka worker
docker-compose logs -f kafka    # Kafka
docker-compose logs -f db       # PostgreSQL
```

## Services Overview

### Application Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| FastAPI App | `app` | 8000 | Main API server |
| Worker | `worker` | 8001 | Kafka consumer worker |
| Database | `db` | 5432 | PostgreSQL |
| Redis | `redis` | 6379 | Rate limiting cache |
| Kafka | `kafka` | 9092 | Message broker |

### Monitoring Services

| Service | Container | Port | Description |
|---------|-----------|------|-------------|
| Prometheus | `prometheus` | 9090 | Metrics collection |
| Grafana | `grafana` | 3000 | Metrics visualization |

## Access Points

Once running, you can access:

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

## Environment Variables

### Database
- `DATABASE_URL`: PostgreSQL connection string (default for Docker: `postgresql+asyncpg://postgres:postgres@db:5432/document_intelligence`)

### Redis
- `REDIS_URL`: Redis connection string
- `REDIS_HOST`: Redis hostname (default: `redis`)
- `REDIS_PORT`: Redis port (default: `6379`)

### Kafka
- `KAFKA_BROKER`: Kafka broker address (default: `kafka:29092`)
- `KAFKA_TOPIC`: Kafka topic name (default: `document_events`)

### API Keys (Required)
- `GEMINI_API_KEY`: Google Gemini API key for embeddings
- `PINECONE_API_KEY`: Pinecone API key for vector store
- `PINECONE_INDEX_NAME`: Pinecone index name (default: `quickstart`)

### Security
- `SECRET_KEY`: Secret key for JWT tokens (change in production!)

### Application Settings
- `CHUNKING_STRATEGY`: Chunking strategy (default: `fixed_size`)
- `UPLOADS_PER_MINUTE`: Rate limit for uploads
- `SEARCHES_PER_MINUTE`: Rate limit for searches

## Common Operations

### Stop All Services

```bash
docker-compose down
```

### Stop and Remove Volumes (Clean State)

```bash
docker-compose down -v
```

### Restart a Specific Service

```bash
docker-compose restart app
docker-compose restart worker
```

### Rebuild After Code Changes

```bash
docker-compose up -d --build
```

### View Logs in Real-Time

```bash
docker-compose logs -f app worker
```

### Execute Commands in a Container

```bash
# Run database migrations
docker-compose exec app alembic upgrade head

# Access database
docker-compose exec db psql -U postgres -d document_intelligence

# Access Redis
docker-compose exec redis redis-cli
```

## Monitoring & Observability

### Prometheus Metrics

Prometheus is configured to scrape metrics from:
- FastAPI app: `app:8000/metrics`
- Worker: `worker:8001/metrics`

Access Prometheus UI: http://localhost:9090

### Grafana Dashboards

Grafana is pre-configured with:
- Prometheus data source
- Pre-built dashboards in `grafana/dashboards/`

Access Grafana: http://localhost:3000
- Username: `admin`
- Password: `admin`

## Database Migrations

Run migrations after starting the services:

```bash
docker-compose exec app alembic upgrade head
```

Or manually:
```bash
docker-compose exec app bash
alembic upgrade head
exit
```

## Development Workflow

### Running in Development Mode

For development, you can override the docker-compose configuration:

Create `docker-compose.override.yml`:
```yaml
version: '3.8'
services:
  app:
    volumes:
      - .:/app
      - /app/venv  # Exclude venv
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Hot Reload

The app supports hot reload when you mount the source code. Update `docker-compose.yml` to add:

```yaml
app:
  volumes:
    - .:/app
```

Then restart:
```bash
docker-compose restart app
```

## Troubleshooting

### Services Won't Start

Check logs:
```bash
docker-compose logs
```

Check if ports are already in use:
```bash
lsof -i :8000  # Check if port is taken
```

### Database Connection Issues

Verify database is healthy:
```bash
docker-compose ps db
docker-compose logs db
```

### Kafka Connection Issues

Verify Kafka is ready:
```bash
docker-compose logs kafka
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Build Failures

Clear Docker cache and rebuild:
```bash
docker-compose build --no-cache
docker-compose up -d
```

### Out of Memory

If you encounter memory issues:
1. Increase Docker Desktop memory allocation (4GB+)
2. Or reduce the number of worker instances
