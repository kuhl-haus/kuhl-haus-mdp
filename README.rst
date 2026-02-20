.. image:: https://img.shields.io/github/license/kuhl-haus/kuhl-haus-mdp
    :alt: License
    :target: https://github.com/kuhl-haus/kuhl-haus-mdp/blob/mainline/LICENSE.txt
.. image:: https://img.shields.io/pypi/v/kuhl-haus-mdp.svg
    :alt: PyPI
    :target: https://pypi.org/project/kuhl-haus-mdp/
.. image:: https://static.pepy.tech/badge/kuhl-haus-mdp/month
    :alt: Downloads
    :target: https://pepy.tech/project/kuhl-haus-mdp
.. image:: https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/publish-to-pypi.yml/badge.svg
    :alt: Build Status
    :target: https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/publish-to-pypi.yml
.. image:: https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/codeql.yml/badge.svg
    :alt: CodeQL Advanced
    :target: https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/codeql.yml
.. image:: https://codecov.io/gh/kuhl-haus/kuhl-haus-mdp/branch/mainline/graph/badge.svg
    :alt: codecov
    :target: https://codecov.io/gh/kuhl-haus/kuhl-haus-mdp
.. image:: https://img.shields.io/github/issues/kuhl-haus/kuhl-haus-mdp
    :alt: GitHub issues
    :target: https://github.com/kuhl-haus/kuhl-haus-mdp/issues
.. image:: https://img.shields.io/github/issues-pr/kuhl-haus/kuhl-haus-mdp
    :alt: GitHub pull requests
    :target: https://github.com/kuhl-haus/kuhl-haus-mdp/pulls
.. image:: https://readthedocs.org/projects/kuhl-haus-mdp/badge/?version=latest
    :alt: Documentation
    :target: https://kuhl-haus-mdp.readthedocs.io/en/latest/

|

==============
kuhl-haus-mdp
==============

Market data processing library.

Overview
========

The Kuhl Haus Market Data Platform (MDP) is a distributed system for collecting, processing, and serving real-time market data. Built on Kubernetes and leveraging microservices architecture, MDP provides scalable infrastructure for financial data analysis and visualization.

Architecture
------------

The platform consists of four main packages:

- **Market data processing library** (`kuhl-haus-mdp <https://github.com/kuhl-haus/kuhl-haus-mdp>`_) - Core library with shared data processing logic
- **Backend Services** (`kuhl-haus-mdp-servers <https://github.com/kuhl-haus/kuhl-haus-mdp-servers>`_) - Market data listener, processor, and widget service
- **Frontend Application** (`kuhl-haus-mdp-app <https://github.com/kuhl-haus/kuhl-haus-mdp-app>`_) - Web-based user interface and API
- **Deployment Automation** (`kuhl-haus-mdp-deployment <https://github.com/kuhl-haus/kuhl-haus-mdp-deployment>`_) - Docker Compose, Ansible playbooks and Kubernetes manifests for environment provisioning

Key Features
------------

- Real-time market data ingestion and processing
- Scalable microservices architecture
- Automated deployment with Ansible and Kubernetes
- Multi-environment support (development, staging, production)
- OAuth integration for secure authentication
- Redis-based caching layer for performance

Additional Resources
--------------------

📖 **Blog Series:**

- `Part 1: Why I Built It <https://the.oldschool.engineer/what-i-built-after-quitting-amazon-spoiler-its-a-stock-scanner-28fc3b6d9be0>`_
- `Part 2: How to Run It <https://the.oldschool.engineer/what-i-built-after-quitting-amazon-spoiler-its-a-stock-scanner-part-2-94e445914951>`_
- `Part 3: How to Deploy It <https://the.oldschool.engineer/what-i-built-after-quitting-amazon-spoiler-its-a-stock-scanner-part-3-eab7d9bbf5f7>`_
- `Part 4: Evolution from Prototype to Production <https://the.oldschool.engineer/what-i-built-after-quitting-amazon-spoiler-its-a-stock-scanner-part-4-408779a1f3f2>`_

Components Summary
==================


.. figure:: Market_Data_Processing_C4.png
   :align: center
   :alt: Market Data Platform Context Diagram

   Market Data Platform Context Diagram


Data Plane Components
----------------------

**Market Data Listener (MDL)**
  WebSocket client connecting to Massive.com, routing events to appropriate queues with minimal processing overhead.

**Market Data Queues (MDQ)**
  RabbitMQ-based FIFO queues with 5-second TTL, buffering high-velocity streams for distributed processing.

**Market Data Processor (MDP)**
  Horizontally-scalable event processors with semaphore-based concurrency (500 concurrent tasks), delegating to pluggable analyzers.

**Market Data Cache (MDC)**
  Redis-backed cache layer with TTL policies (5s-24h), atomic operations, and pub/sub distribution.

**Widget Data Service (WDS)**
  WebSocket-to-Redis bridge providing real-time streaming to client applications with fan-out pattern.

Control Plane
-------------

**Service Control Plane (SCP)**
  OAuth authentication, SPA serving, runtime controls, and management API (external repository: kuhl-haus-mdp-app).

Observability
-------------

All components emit OpenTelemetry traces/metrics and structured JSON logs for Kubernetes/OpenObserve integration.

Deployment Model
================

The platform deploys to Kubernetes with independent scaling per component:

- **Data plane**: Internal network only (MDL, MDQ, MDP, MDC)
- **Client interface**: Exposed to client networks (WDS)
- **Control plane**: External access (SCP)

All components run as Docker containers with automated deployment via Ansible playbooks and Kubernetes manifests (kuhl-haus-mdp-deployment repository).


Component Descriptions
======================


.. figure:: architecture.svg
   :align: center
   :alt: Market Data Platform Component Architecture

   Market Data Platform Component Architecture


Market Data Listener (MDL)
---------------------------

The MDL performs minimal processing on the messages. MDL inspects the message type for selecting the appropriate serialization method and destination queue. MDL implementations may vary as new MDS become available (for example, news).

MDL runs as a container and scales independently of other components. The MDL should not be accessible outside the data plane local network.

Code Libraries
~~~~~~~~~~~~~~

- **MassiveDataListener** (``components/massive_data_listener.py``) - WebSocket client wrapper for Massive.com with persistent connection management and market-aware reconnection logic
- **MassiveDataQueues** (``components/massive_data_queues.py``) - Multi-channel RabbitMQ publisher routing messages by event type with concurrent batch publishing (100 msg/frame)
- **WebSocketMessageSerde** (``helpers/web_socket_message_serde.py``) - Serialization/deserialization for Massive WebSocket messages to/from JSON
- **QueueNameResolver** (``helpers/queue_name_resolver.py``) - Event type to queue name routing logic

Market Data Queues (MDQ)
-------------------------

**Purpose:** Buffer high-velocity market data stream for server-side processing with aggressive freshness controls

- **Queue Type:** FIFO with TTL (5-second max message age)
- **Cleanup Strategy:** Discarded when TTL expires
- **Message Format:** Timestamped JSON preserving original Massive.com structure
- **Durability:** Non-persistent messages (speed over reliability for real-time data)
- **Independence:** Queues operate completely independently - one queue per subscription
- **Technology:** RabbitMQ

The MDQ should not be accessible outside the data plane local network.

Code Libraries
~~~~~~~~~~~~~~

- **MassiveDataQueues** (``components/massive_data_queues.py``) - Queue setup, per-queue channel management, and message publishing with NOT_PERSISTENT delivery mode
- **MassiveDataQueue** enum (``enum/massive_data_queue.py``) - Queue name constants for routing (AGGREGATE, TRADES, QUOTES, HALTS, UNKNOWN)

Market Data Processors (MDP)
-----------------------------

The purpose of the MDP is to process raw real-time market data and delegate processing to data-specific handlers. This separation of concerns allows MDPs to handle any type of data and simplifies horizontal scaling. The MDP stores its processed results in the Market Data Cache (MDC).

The MDP:

- Hydrates the in-memory cache on MDC
- Processes market data
- Publishes messages to pub/sub channels
- Maintains cache entries in MDC

MDPs runs as containers and scale independently of other components. The MDPs should not be accessible outside the data plane local network.

Code Libraries
~~~~~~~~~~~~~~

- **MassiveDataProcessor** (``components/massive_data_processor.py``) - RabbitMQ consumer with semaphore-based concurrency control for high-throughput scenarios (1,000+ events/sec)
- **MarketDataScanner** (``components/market_data_scanner.py``) - Redis pub/sub consumer with pluggable analyzer pattern for sequential message processing
- **Analyzers** (``analyzers/``)

  - **MassiveDataAnalyzer** (``massive_data_analyzer.py``) - Stateless event router dispatching by event type
  - **LeaderboardAnalyzer** (``leaderboard_analyzer.py``) - Redis sorted set leaderboards (volume, gappers, gainers) with day/market boundary resets and distributed throttling
  - **TopTradesAnalyzer** (``top_trades_analyzer.py``) - Redis List-based trade history with sliding window (last 1,000 trades/symbol) and aggregated statistics
  - **TopStocksAnalyzer** (``top_stocks.py``) - In-memory leaderboard prototype (legacy, single-instance)

- **MarketDataAnalyzerResult** (``data/market_data_analyzer_result.py``) - Result envelope for analyzer output with cache/publish metadata
- **ProcessManager** (``helpers/process_manager.py``) - Multiprocess orchestration for async workers with OpenTelemetry context propagation

Market Data Cache (MDC)
------------------------

**Purpose:** In-memory data store for serialized processed market data.

- **Cache Type:** In-memory persistent or with TTL
- **Queue Type:** pub/sub
- **Technology:** Redis

The MDC should not be accessible outside the data plane local network.

Code Libraries
~~~~~~~~~~~~~~

- **MarketDataCache** (``components/market_data_cache.py``) - Redis cache-aside layer for Massive.com API with TTL policies, negative caching, and specialized metric methods (snapshot, avg volume, free float)
- **MarketDataCacheKeys** enum (``enum/market_data_cache_keys.py``) - Internal Redis cache key patterns and templates
- **MarketDataCacheTTL** enum (``enum/market_data_cache_ttl.py``) - TTL values balancing freshness vs. API quotas vs. memory pressure (5s for trades, 24h for reference data)
- **MarketDataPubSubKeys** enum (``enum/market_data_pubsub_keys.py``) - Redis pub/sub channel names for external consumption

Widget Data Service (WDS)
--------------------------

**Purpose:**

1. WebSocket interface provides access to processed market data for client-side code
2. Is the network-layer boundary between clients and the data that is available on the data plane

WDS runs as a container and scales independently of other components. WDS is the only data plane component that should be exposed to client networks.

Code Libraries
~~~~~~~~~~~~~~

- **WidgetDataService** (``components/widget_data_service.py``) - WebSocket-to-Redis bridge with fan-out pattern, lazy task initialization, wildcard subscription support, and lock-protected subscription management
- **MarketDataCache** (``components/market_data_cache.py``) - Snapshot retrieval for initial state before streaming

Service Control Plane (SCP)
----------------------------

**Purpose:**

1. Authentication and authorization
2. Serve static and dynamic content via py4web
3. Serve SPA to authenticated clients
4. Injects authentication token and WDS url into SPA environment for authenticated access to WDS
5. Control plane for managing application components at runtime
6. API for programmatic access to service controls and instrumentation.

The SCP requires access to the data plane network for API access to data plane components.

The SCP code is in the `kuhl-haus/kuhl-haus-mdp-app <https://github.com/kuhl-haus/kuhl-haus-mdp-app>`_ repo.



Miscellaneous Code Libraries
-----------------------------

- **Observability** (``helpers/observability.py``) - OpenTelemetry tracer/meter factory for distributed tracing and metrics
- **StructuredLogging** (``helpers/structured_logging.py``) - JSON logging for K8s/OpenObserve with dev mode support
- **Utils** (``helpers/utils.py``) - API key resolution (MASSIVE_API_KEY → POLYGON_API_KEY → file) and TickerSnapshot serialization