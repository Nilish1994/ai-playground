# AI Playground

Independent FastAPI backend for a personal AI assistant. It uses the OpenAI Responses API, an async SQLAlchemy/Postgres foundation, dependency injection, structured JSON logs, typed settings, and a tool registry designed for future extensions.

## Requirements

- Python 3.12
- Docker and Docker Compose (recommended), or a local Postgres instance
- An OpenAI API key

## Run with Docker

```bash
cp .env.example .env
# Add OPENAI_API_KEY to .env
docker compose up --build
```

The API is available at `http://localhost:8000`; development documentation is at `/docs`.

```bash
curl http://localhost:8000/api/v1/health
curl -X POST http://localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Explain dependency injection in one paragraph."}'
```

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
cp .env.example .env
pip install -e '.[dev]'
pytest
ruff check .
uvicorn app.main:app --reload
```

Use a local database URL in `.env` when running outside Docker, for example `postgresql+asyncpg://ai_playground:ai_playground@localhost:5432/ai_playground`.

## Structure

```text
app/
├── api/          # HTTP routes and dependency wiring
├── core/         # configuration, logging, and errors
├── db/           # async SQLAlchemy engine and sessions
├── schemas/      # Pydantic API contracts
├── services/     # business logic and OpenAI integration
└── tools/        # pluggable assistant-tool contracts and registry
tests/            # isolated API tests; no live OpenAI calls
```

Routes delegate to services, and services receive their dependencies explicitly. To add a tool, implement `AssistantTool`, register it in `get_tool_registry`, then add the tool-call execution loop to the chat service. Database models can inherit from `app.db.base.Base`; add Alembic before introducing persistent tables.

## Configuration

All settings are environment-driven; see `.env.example`. Keep `.env` out of source control. In production, inject secrets through the deployment platform, set `APP_ENV=production`, disable docs with `DOCS_ENABLED=false` if desired, replace database credentials, and terminate TLS at the ingress or load balancer.

The chat request uses `store=False` so response state is not retained by the Responses API through this endpoint. Logs include operational metadata but never prompts or generated response bodies.

## API errors

Application and upstream failures use a stable envelope:

```json
{"error":{"code":"AI_UNAVAILABLE","message":"The AI service is unavailable."}}
```

Validation failures use FastAPI's standard `422` response.

## Production notes

- Pinning makes builds repeatable; update dependencies deliberately and run tests.
- Add authentication, rate limiting, migrations, and a managed secrets provider before exposing the service publicly.
- Scale Uvicorn processes at the container-orchestrator level and tune database pools to match deployment concurrency.
- The health endpoint is a liveness check. Add a separate readiness endpoint when database-backed behavior is introduced.

The SDK usage follows the official [OpenAI API quickstart](https://platform.openai.com/docs/quickstart) pattern: create a response and read its `output_text` convenience property.
