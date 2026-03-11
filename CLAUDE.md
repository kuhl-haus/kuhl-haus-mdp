# CLAUDE.md — kuhl-haus-mdp

## Overview

Core library for the Kuhl Haus Market Data Platform (MDP). Provides shared data processing logic consumed by `kuhl-haus-mdp-servers`.

**Documentation:** https://kuhl-haus-mdp.readthedocs.io  
**PyPI:** https://pypi.org/project/kuhl-haus-mdp/

## Platform Context

MDP is a distributed system for collecting, processing, and serving real-time market data. This library is the core dependency — all data plane server containers depend on it.

**Platform repositories:**
- **kuhl-haus-mdp** *(this repo)* — Core library
- **kuhl-haus-mdp-servers** — Server entry points and Docker images
- **kuhl-haus-mdp-app** — Service Control Plane (SCP) web application
- **kuhl-haus-mdp-deployment** — Kubernetes/Ansible deployment automation

## Architecture

The platform data plane components:

| Component | Acronym | Role |
|---|---|---|
| Market Data Listener | MDL | WebSocket client → Massive.com; routes events to RabbitMQ queues |
| Market Data Queues | MDQ | RabbitMQ FIFO queues; 5s TTL; non-persistent (speed over durability) |
| Market Data Processor | MDP | Horizontally-scalable event processor; delegates to pluggable analyzers; writes to Redis |
| Market Data Cache | MDC | Redis-backed cache with TTL policies (5s–24h), atomic ops, pub/sub |
| Widget Data Service | WDS | WebSocket-to-Redis bridge; fan-out streaming to client applications |
| Service Control Plane | SCP | OAuth auth, SPA serving, runtime management (kuhl-haus-mdp-app) |

All components emit OpenTelemetry traces/metrics and structured JSON logs.

## Code Organization

```
src/kuhl_haus/mdp/
├── analyzers/                    # Pluggable analyzer framework
│   ├── analyzer.py               # Base Analyzer ABC
│   ├── leaderboard_analyzer.py
│   ├── massive_data_analyzer.py
│   ├── top_stocks.py
│   └── top_trades_analyzer.py
├── components/                   # Platform component implementations
│   ├── market_data_cache.py      # Redis MDC client
│   ├── market_data_scanner.py
│   ├── massive_data_listener.py  # WebSocket MDL client
│   └── massive_data_queues.py    # RabbitMQ MDQ publisher
├── data/                         # Data models / schemas
├── enum/                         # Enumerations (queue names, event types)
├── exceptions/                   # Custom exceptions
└── helpers/                      # Utilities (serde, queue routing)
docs/                             # Sphinx documentation source
```

## Development

**Language:** Python 3.14+  
**Package manager:** PDM  
**Build backend:** pdm-backend (version from git tags via setuptools-scm)

```bash
pdm install
pdm run pytest
```

> ⚠️ **Build order matters:** In CI, always run `pdm build` before `pdm install`. Running `pdm install` first regenerates `pdm.lock`, making the working tree dirty — pdm-backend appends `+d<date>` to dirty builds, which PyPI rejects (PEP 440 local version identifiers).

### Key dependencies

- `aiohttp`, `websockets` — async HTTP and WebSocket clients
- `aio-pika` — async RabbitMQ client (AMQP)
- `redis` — Redis client with async support
- `fastapi`, `uvicorn` — async HTTP server
- `opentelemetry-*` — distributed tracing and metrics
- `pydantic-settings`, `python-dotenv` — configuration management
- `tenacity` — retry logic
- `massive` — Massive.com market data client

## Testing

```bash
pdm run pytest --cov=kuhl_haus.mdp --cov-branch
```

Test files live in `tests/`. Uses `pytest-asyncio` for async test support.

## CI/CD (GitHub Actions)

| Workflow | Trigger | Purpose |
|---|---|---|
| `codeql.yml` | push/PR | CodeQL security analysis |
| `publish-to-pypi.yml` | version tag push | Build and publish to PyPI |
| `release.yml` | version tag push | Release automation |

## Branch and Merge Conventions

- **Default branch:** `mainline`
- **Squash merge only** — org-level enforcement; merge commits and rebase are disabled
- All PRs target `mainline`; use feature branches for all changes
- Version tags drive PyPI releases — tag format: `vX.Y.Z`

## Documentation

Built with Sphinx + Furo theme. Hosted on Read the Docs.

```bash
./build-docs.sh          # Linux/macOS
./Build-Docs.ps1         # Windows
```

API reference is auto-generated from docstrings. See `docs/` for RST source.
