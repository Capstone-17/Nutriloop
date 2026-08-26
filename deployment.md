# Deployment, DevOps & Automated Testing Architecture

This document specifies the deployment infrastructure, containerization, automated testing, and CI/CD pipelines for the Deep Learning and Generative AI-Driven Diet Recommendation System.

---

## 1. Automated Testing Suite

### A. Dedicated Pytest Architecture
Restructure automated testing from standalone scripts into a standard `tests/` directory:

```
tests/
├── conftest.py               # Shared test client fixtures and DB mock configurations
├── test_api.py               # Full coverage for all 21 REST endpoints
├── test_models.py            # Model artifact validation, inference correctness, and shape checks
├── test_rules.py             # Risk classification and macronutrient constraint calculations
├── test_safety.py            # Multi-tier safety engine, critical limits, and medication interactions
├── test_adaptation.py        # Meal deviation detection, adaptation triggers, and pattern learning
├── test_raw_input.py         # Conversational questionnaire mapping and edge-case validation
└── test_chatbot.py           # Evaluation harness integration and escalation regex verification
```

### B. Automated Performance & Regression Benchmarks
- Include automated threshold and metrics regression checks in test runs to guarantee that model Macro-F1, PR-AUC, and calibration scores do not degrade across commits.

---

## 2. Containerization (Docker)

### A. Backend Dockerfile
Multi-stage, slim Python 3.11 container for the FastAPI application:

```dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### B. Docker Compose Multi-Service Stack (`docker-compose.yml`)
Orchestrates the entire platform including the local LLM service:

```yaml
version: '3.8'

services:
  backend:
    build: .
    container_name: diet_recommendation_api
    ports:
      - "8000:8000"
    volumes:
      - ./app_data.db:/app/app_data.db
      - ./artifacts:/app/artifacts
      - ./datasets:/app/datasets
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - OLLAMA_MODEL=llama3.2:3b
    depends_on:
      - ollama
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    container_name: local_llm_service
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    restart: unless-stopped

volumes:
  ollama_models:
```

---

## 3. Continuous Integration & Delivery (CI/CD)

### GitHub Actions Workflow (`.github/workflows/ci.yml`)
Automated pipeline triggered on every push and pull request:

```yaml
name: CI Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov ruff

      - name: Lint with Ruff
        run: ruff check backend/ scripts/

      - name: Run Smoke Tests (21 Endpoints)
        run: python scripts/smoke_test.py

      - name: Run Pytest Suite with Coverage
        run: pytest tests/ --cov=backend --cov-report=term-missing
```

---

## 4. Production Hosting & Process Management

- **ASGI Server**: Uvicorn managed by Gunicorn (`gunicorn backend.app:app -w 4 -k uvicorn.workers.UvicornWorker`).
- **Reverse Proxy**: Nginx with SSL termination, rate limiting, and gzip compression for static assets.
- **Monitoring & Logging**: Structured JSON logging with endpoint latency tracking and audit trail synchronization to SQLite / PostgreSQL.
