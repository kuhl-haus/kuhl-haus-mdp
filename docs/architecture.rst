============
Architecture
============

Components Summary
==================


.. figure:: https://raw.githubusercontent.com/kuhl-haus/kuhl-haus-mdp/mainline/docs/Market_Data_Processing_C4.png
   :align: center
   :alt: Market Data Platform Context Diagram

   Market Data Platform Context Diagram


Data Plane Components
----------------------

**Finlight Data Listener (FDL)**
  WebSocket client connecting to the Finlight news API, routing articles to the RabbitMQ news queue with minimal processing overhead.

**Finlight Data Processor (FDP)**
  Async RabbitMQ consumer processing Finlight news articles through pluggable analyzers and writing results to Redis.

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


.. uml:: architecture.puml
   :align: center
   :caption: Market Data Platform Component Architecture

See the :doc:`full-page diagram <architecture-diagram>` for a full-page view.


Finlight Data Listener (FDL)
-----------------------------

The FDL connects to the Finlight news WebSocket API and routes incoming articles to the RabbitMQ ``news`` queue via ``FinlightDataQueues``. It performs minimal processing — the listener delegates each article directly to ``FinlightDataQueues.handle_message``, which serializes and publishes it. Auto-reconnect is handled by ``FinlightDataListener``.

FDL runs as a container and scales independently of other components. FDL should not be accessible outside the data plane local network.

Code Libraries
~~~~~~~~~~~~~~

- **FinlightDataListener** (`components/finlight_data_listener.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.finlight_data_listener>`_) - WebSocket client wrapper for the Finlight news API with persistent connection management and auto-reconnect logic
- **FinlightDataQueues** (`components/finlight_data_queues.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.finlight_data_queues>`_) - Single-channel RabbitMQ publisher serializing Finlight article objects to the ``news`` queue
- **FinlightDataQueue** enum (`enum/finlight_data_queue.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.enum.html#module-kuhl_haus.mdp.enum.finlight_data_queue>`_) - Queue name constant for routing (NEWS = ``"news"``)

Finlight Data Processor (FDP)
-------------------------------

The FDP consumes news articles from the RabbitMQ ``news`` queue and delegates processing to a pluggable analyzer. Like the MDP, it uses semaphore-based concurrency control and writes results to Redis. The FDP is designed for a lower-throughput news feed rather than high-velocity tick data, so it runs as a single async processor rather than using ``ProcessManager`` parallelism.

FDP runs as a container and scales independently of other components. FDP should not be accessible outside the data plane local network.

Code Libraries
~~~~~~~~~~~~~~

- **FinlightDataProcessor** (`components/finlight_data_processor.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.finlight_data_processor>`_) - Async RabbitMQ consumer with semaphore-based concurrency. Deserializes JSON article payloads directly (no WebSocketMessageSerde) and delegates to pluggable analyzers.

Market Data Listener (MDL)
---------------------------

The MDL performs minimal processing on the messages. MDL inspects the message type for selecting the appropriate serialization method and destination queue. MDL implementations may vary as new MDS become available (for example, news).

MDL runs as a container and scales independently of other components. The MDL should not be accessible outside the data plane local network.

Code Libraries
~~~~~~~~~~~~~~

- **MassiveDataListener** (`components/massive_data_listener.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.massive_data_listener>`_) - WebSocket client wrapper for Massive.com with persistent connection management and market-aware reconnection logic
- **MassiveDataQueues** (`components/massive_data_queues.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.massive_data_queues>`_) - Multi-channel RabbitMQ publisher routing messages by event type with concurrent batch publishing (100 msg/frame)
- **WebSocketMessageSerde** (`helpers/web_socket_message_serde.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.helpers.html#module-kuhl_haus.mdp.helpers.web_socket_message_serde>`_) - Serialization/deserialization for Massive WebSocket messages to/from JSON
- **QueueNameResolver** (`helpers/queue_name_resolver.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.helpers.html#module-kuhl_haus.mdp.helpers.queue_name_resolver>`_) - Event type to queue name routing logic

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

- **MassiveDataQueues** (`components/massive_data_queues.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.massive_data_queues>`_) - Queue setup, per-queue channel management, and message publishing with NOT_PERSISTENT delivery mode
- **MassiveDataQueue** enum (`enum/massive_data_queue.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.enum.html#module-kuhl_haus.mdp.enum.massive_data_queue>`_) - Queue name constants for routing (AGGREGATE, TRADES, QUOTES, HALTS, UNKNOWN)

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

- **MassiveDataProcessor** (`components/massive_data_processor.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.massive_data_processor>`_) - RabbitMQ consumer with semaphore-based concurrency control for high-throughput scenarios (1,000+ events/sec)
- **MarketDataScanner** (`components/market_data_scanner.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.market_data_scanner>`_) - Redis pub/sub consumer with pluggable analyzer pattern for sequential message processing
- **Analyzers** (`analyzers/ <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.analyzers.html>`_)

  - **MassiveDataAnalyzer** (`massive_data_analyzer.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.analyzers.html#module-kuhl_haus.mdp.analyzers.massive_data_analyzer>`_) - Stateless event router dispatching by event type
  - **LeaderboardAnalyzer** (`leaderboard_analyzer.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.analyzers.html#module-kuhl_haus.mdp.analyzers.leaderboard_analyzer>`_) - Redis sorted set leaderboards (volume, gappers, gainers) with day/market boundary resets and distributed throttling
  - **TopTradesAnalyzer** (`top_trades_analyzer.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.analyzers.html#module-kuhl_haus.mdp.analyzers.top_trades_analyzer>`_) - Redis List-based trade history with sliding window (last 1,000 trades/symbol) and aggregated statistics
  - **TopStocksAnalyzer** (`top_stocks.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.analyzers.html#module-kuhl_haus.mdp.analyzers.top_stocks>`_) - In-memory leaderboard prototype (legacy, single-instance)

- **MarketDataAnalyzerResult** (`data/market_data_analyzer_result.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.data.html#module-kuhl_haus.mdp.data.market_data_analyzer_result>`_) - Result envelope for analyzer output with cache/publish metadata
- **ProcessManager** (`helpers/process_manager.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.helpers.html#module-kuhl_haus.mdp.helpers.process_manager>`_) - Multiprocess orchestration for async workers with OpenTelemetry context propagation

Market Data Cache (MDC)
------------------------

**Purpose:** In-memory data store for serialized processed market data.

- **Cache Type:** In-memory persistent or with TTL
- **Queue Type:** pub/sub
- **Technology:** Redis

The MDC should not be accessible outside the data plane local network.

Code Libraries
~~~~~~~~~~~~~~

- **MarketDataCache** (`components/market_data_cache.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.market_data_cache>`_) - Redis cache-aside layer for Massive.com API with TTL policies, negative caching, and specialized metric methods (snapshot, avg volume, free float)
- **MarketDataCacheKeys** enum (`enum/market_data_cache_keys.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.enum.html#module-kuhl_haus.mdp.enum.market_data_cache_keys>`_) - Internal Redis cache key patterns and templates
- **MarketDataCacheTTL** enum (`enum/market_data_cache_ttl.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.enum.html#module-kuhl_haus.mdp.enum.market_data_cache_ttl>`_) - TTL values balancing freshness vs. API quotas vs. memory pressure (5s for trades, 24h for reference data)
- **MarketDataPubSubKeys** enum (`enum/market_data_pubsub_keys.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.enum.html#module-kuhl_haus.mdp.enum.market_data_pubsub_keys>`_) - Redis pub/sub channel names for external consumption

Widget Data Service (WDS)
--------------------------

**Purpose:**

1. WebSocket interface provides access to processed market data for client-side code
2. Is the network-layer boundary between clients and the data that is available on the data plane

WDS runs as a container and scales independently of other components. WDS is the only data plane component that should be exposed to client networks.

Code Libraries
~~~~~~~~~~~~~~

- **WidgetDataService** (`components/widget_data_service.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.widget_data_service>`_) - WebSocket-to-Redis bridge with fan-out pattern, lazy task initialization, wildcard subscription support, and lock-protected subscription management
- **MarketDataCache** (`components/market_data_cache.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.components.html#module-kuhl_haus.mdp.components.market_data_cache>`_) - Snapshot retrieval for initial state before streaming

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

- **Observability** (`helpers/observability.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.helpers.html#module-kuhl_haus.mdp.helpers.observability>`_) - OpenTelemetry tracer/meter factory for distributed tracing and metrics
- **StructuredLogging** (`helpers/structured_logging.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.helpers.html#module-kuhl_haus.mdp.helpers.structured_logging>`_) - JSON logging for K8s/OpenObserve with dev mode support
- **Utils** (`helpers/utils.py <https://kuhl-haus-mdp.readthedocs.io/en/latest/mdp/kuhl_haus.mdp.helpers.html#module-kuhl_haus.mdp.helpers.utils>`_) - API key resolution (MASSIVE_API_KEY → POLYGON_API_KEY → file) and TickerSnapshot serialization
