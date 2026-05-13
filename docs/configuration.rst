Configuration Reference
=======================

All MDP server containers are configured exclusively via environment variables.
No configuration files are required at runtime.

----

Common Variables
----------------

These variables are supported by all servers.

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Variable
     - Default
     - Description
   * - ``LOG_LEVEL``
     - ``INFO``
     - Logging level: ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``
   * - ``SERVER_IP``
     - ``0.0.0.0``
     - IP address to bind the HTTP server
   * - ``SERVER_PORT``
     - *(server-specific)*
     - TCP port for the HTTP server (see per-server defaults below)
   * - ``CONTAINER_IMAGE``
     - ``Unknown``
     - Image name injected at build time (informational)
   * - ``IMAGE_VERSION``
     - ``Unknown``
     - Image version injected at build time (informational)

----

OpenTelemetry (OTEL-enabled images)
------------------------------------

These variables are only available on image variants built with OpenTelemetry
instrumentation. They are standard
`OpenTelemetry SDK environment variables <https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/>`_
unless noted otherwise.

.. note::

   OTEL-enabled images are published separately from the standard images.
   Check the package page on GHCR for available tags.

.. list-table::
   :header-rows: 1
   :widths: 38 20 42

   * - Variable
     - Default
     - Description
   * - ``OTEL_SERVICE_NAME``
     - *(required)*
     - Logical service name attached to all traces, metrics, and logs emitted
       by this instance (e.g. ``mdl``, ``fdl``, ``mds``). Should be unique
       per server type.
   * - ``OTEL_TRACES_EXPORTER``
     - ``otlp``
     - Exporter for trace data. Options: ``otlp`` — send to an OTLP-compatible
       collector; ``console`` — print to stdout (useful for local debugging);
       ``none`` — disable trace export entirely.
   * - ``OTEL_METRICS_EXPORTER``
     - ``otlp``
     - Exporter for metrics data. Same options as ``OTEL_TRACES_EXPORTER``:
       ``otlp``, ``console``, or ``none``.
   * - ``OTEL_LOGS_EXPORTER``
     - ``otlp``
     - Exporter for log data. Same options as ``OTEL_TRACES_EXPORTER``:
       ``otlp``, ``console``, or ``none``.
   * - ``OTEL_EXPORTER_OTLP_PROTOCOL``
     - ``http/protobuf``
     - Wire protocol used by the OTLP exporter. Options: ``http/protobuf`` —
       HTTP with Protocol Buffers encoding (recommended, most broadly
       supported); ``grpc`` — gRPC; ``http/json`` — HTTP with JSON encoding.
   * - ``OTEL_EXPORTER_OTLP_ENDPOINT``
     - *(required)*
     - Base URL of the OTLP collector endpoint
       (e.g. ``https://openobserve.example.com/api/default``). The SDK appends
       signal-specific paths (``/v1/traces``, ``/v1/metrics``, ``/v1/logs``)
       automatically when using ``http/protobuf`` or ``http/json``.
   * - ``OTEL_EXPORTER_OTLP_HEADERS``
     - *(none)*
     - Comma-separated ``key=value`` pairs sent as HTTP headers with every
       OTLP export request. Used for authentication and routing
       (e.g. ``Authorization=Bearer <token>,stream-name=default``).
   * - ``OTEL_LOG_LEVEL``
     - ``error``
     - Internal log level for the OpenTelemetry SDK itself — controls SDK
       diagnostic output, not application log output (see ``LOG_LEVEL`` for
       that). Options: ``debug``, ``info``, ``warning``, ``error``,
       ``critical``.
   * - ``OTEL_PYTHON_FASTAPI_EXCLUDED_URLS``
     - ``health``
     - Comma-separated URL path patterns excluded from FastAPI auto-
       instrumentation. The ``health`` endpoint is excluded by default to
       prevent probe traffic from polluting trace data.

----

Finlight Data Listener (FDL)
-----------------------------

**Default port:** 4203

The FDL connects to the Finlight news WebSocket API and routes articles to the
RabbitMQ ``news`` queue.

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Variable
     - Default
     - Description
   * - ``FINLIGHT_API_KEY``
     - *(required)*
     - Finlight API key for WebSocket authentication
   * - ``FINLIGHT_QUERY``
     - *(none)*
     - Full-text query filter for incoming articles (e.g. ``"earnings catalyst"``)
   * - ``FINLIGHT_LANGUAGE``
     - *(none)*
     - ISO 639-1 language code to filter (e.g. ``en``)
   * - ``FINLIGHT_RAW``
     - ``false``
     - Subscribe to raw (unprocessed) article feed instead of enriched feed
   * - ``FINLIGHT_INCLUDE_ENTITIES``
     - ``true``
     - Include entity tagging (tickers, people, orgs) in enriched article payloads
   * - ``RABBITMQ_URL``
     - ``amqp://mdq:mdq@localhost:5672/``
     - RabbitMQ connection URL (AMQP)
   * - ``MARKET_DATA_MESSAGE_TTL``
     - ``5000``
     - RabbitMQ message TTL in milliseconds
   * - ``MDQ_PUBLISHER_CONFIRMS``
     - ``true``
     - Enable RabbitMQ publisher confirms (``true`` / ``false``)
   * - ``FDL_AUTO_START_ENABLED``
     - ``false``
     - Automatically connect to Finlight on startup. When ``false``, use the ``/start`` endpoint.

----

Finlight Data Processor (FDP)
-------------------------------

**Default port:** 4204

The FDP consumes articles from the RabbitMQ ``news`` queue and processes them
through a pluggable analyzer, writing results to Redis.

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Variable
     - Default
     - Description
   * - ``RABBITMQ_URL``
     - ``amqp://mdq:mdq@localhost:5672/``
     - RabbitMQ connection URL (AMQP)
   * - ``MDC_REDIS_URL``
     - ``redis://mdc:mdc@localhost:6379/0``
     - Market Data Cache Redis URL. Used by Analyzers via ``AnalyzerOptions``.
   * - ``WDC_REDIS_URL``
     - ``redis://mdc:mdc@localhost:6379/1``
     - Widget Data Cache Redis URL. Used by Processors to store analyzer results.
   * - ``FDP_QUEUE_NAME``
     - ``news``
     - RabbitMQ queue to consume from
   * - ``PREFETCH_COUNT``
     - ``100``
     - RabbitMQ prefetch count (messages delivered before ACK required)
   * - ``MAX_CONCURRENCY``
     - ``500``
     - Maximum concurrent async processing tasks (semaphore limit)
   * - ``FINLIGHT_API_KEY``
     - *(empty)*
     - Finlight API key. Passed to ``AnalyzerOptions`` and forwarded to the
       analyzer. Required for analyzers that call the Finlight REST API directly.
   * - ``NEWS_FEED_LIST_MAX``
     - ``10000``
     - Maximum number of articles retained in the news feed Redis list cache
       (``news:feed:latest``). Overrides the ``FinlightDataCache.NEWS_FEED_LIST_MAX``
       enum default. Increase for deeper history; decrease to bound memory use.
   * - ``NEWS_TICKER_LIST_MAX``
     - ``100``
     - Maximum number of articles retained per ticker Redis list cache
       (``news:ticker:<TICKER>``). Overrides the ``FinlightDataCache.NEWS_TICKER_LIST_MAX``
       enum default.
   * - ``NEWS_FEED_CACHE_TTL``
     - ``172800`` (2 days)
     - Redis TTL in seconds for the news feed list cache (``news:feed:latest``).
       Overrides the ``MarketDataCacheTTL.NEWS_FEED_LATEST`` enum default.
   * - ``NEWS_TICKER_CACHE_TTL``
     - ``604800`` (7 days)
     - Redis TTL in seconds for per-ticker news list caches
       (``news:ticker:<TICKER>``). Overrides the ``MarketDataCacheTTL.NEWS_TICKER``
       enum default.

----

Leaderboard Analyzer (LBA)
---------------------------

**Default port:** 4210

The LBA subscribes to Redis pub/sub channels and runs leaderboard and trade
analyzers sequentially.

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Variable
     - Default
     - Description
   * - ``MASSIVE_API_KEY``
     - *(required)*
     - Massive.com API key. Same resolution chain as MDL.
   * - ``RABBITMQ_URL``
     - ``amqp://mdq:mdq@localhost:5672/``
     - RabbitMQ connection URL (AMQP)
   * - ``MDC_REDIS_URL``
     - ``redis://mdc:mdc@localhost:6379/0``
     - Market Data Cache Redis URL. Used by Analyzers via ``AnalyzerOptions``.
   * - ``WDC_REDIS_URL``
     - ``redis://mdc:mdc@localhost:6379/1``
     - Widget Data Cache Redis URL. Used by Processors to store analyzer results.
   * - ``PARALLELISM``
     - ``1``
     - Number of parallel processor workers
   * - ``PREFETCH_COUNT``
     - ``10``
     - RabbitMQ prefetch count per worker
   * - ``MAX_CONCURRENCY``
     - ``100``
     - Maximum concurrent async tasks per worker (semaphore limit)

----

Massive Data Listener (MDL)
---------------------------

**Default port:** 4200

The MDL connects to the Massive.com WebSocket API and routes tick data events
to per-type RabbitMQ queues.

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Variable
     - Default
     - Description
   * - ``MASSIVE_API_KEY``
     - *(required)*
     - Massive.com API key. Resolved in order: ``MASSIVE_API_KEY`` env var →
       ``POLYGON_API_KEY`` env var (legacy) → ``/app/massive_api_key.txt`` (Docker secret).
   * - ``MASSIVE_FEED``
     - ``RealTime``
     - Massive.com feed type: ``RealTime`` or ``Delayed``
   * - ``MASSIVE_MARKET``
     - ``Stocks``
     - Massive.com market: ``Stocks``, ``Options``, or ``Indices``
   * - ``MASSIVE_SUBSCRIPTIONS``
     - ``["A.*","T.*","Q.*","LULD.*"]``
     - JSON array of WebSocket subscription patterns
   * - ``MASSIVE_RAW``
     - ``false``
     - Subscribe to raw feed instead of typed events
   * - ``MASSIVE_VERBOSE``
     - ``false``
     - Enable verbose Massive SDK logging
   * - ``MASSIVE_SECURE``
     - ``true``
     - Use TLS for Massive.com WebSocket connection
   * - ``MASSIVE_MAX_RECONNECTS``
     - ``5``
     - Maximum WebSocket reconnection attempts before giving up
   * - ``RABBITMQ_URL``
     - ``amqp://mdq:mdq@localhost:5672/``
     - RabbitMQ connection URL (AMQP)
   * - ``MARKET_DATA_MESSAGE_TTL``
     - ``5000``
     - RabbitMQ message TTL in milliseconds
   * - ``MDQ_PUBLISHER_CONFIRMS``
     - ``true``
     - Enable RabbitMQ publisher confirms (``true`` / ``false``)
   * - ``MDL_AUTO_START_ENABLED``
     - ``false``
     - Automatically connect to Massive.com on startup. When ``false``, use the ``/start`` endpoint.

----

Market Data Processor (MDP)
----------------------------

**Default port:** 4201

The MDP runs parallel ``MassiveDataProcessor`` workers consuming from
multiple RabbitMQ queues and writing results to Redis.

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Variable
     - Default
     - Description
   * - ``MASSIVE_API_KEY``
     - *(required)*
     - Massive.com API key. Same resolution chain as MDL.
   * - ``RABBITMQ_URL``
     - ``amqp://mdq:mdq@localhost:5672/``
     - RabbitMQ connection URL (AMQP)
   * - ``MDC_REDIS_URL``
     - ``redis://mdc:mdc@localhost:6379/0``
     - Market Data Cache Redis URL. Used by Analyzers via ``AnalyzerOptions``.
   * - ``WDC_REDIS_URL``
     - ``redis://mdc:mdc@localhost:6379/1``
     - Widget Data Cache Redis URL. Used by Processors to store analyzer results.
   * - ``PARALLELISM``
     - ``10``
     - Number of parallel processor workers per queue type
   * - ``PREFETCH_COUNT``
     - ``10``
     - RabbitMQ prefetch count per worker
   * - ``MAX_CONCURRENCY``
     - ``100``
     - Maximum concurrent async tasks per worker (semaphore limit)

----

Market Data Scanner (MDS)
--------------------------

**Default port:** 4205

The MDS subscribes to Redis pub/sub channels and runs pluggable analyzers on
enriched market data for event correlation, alert generation, and trend
analysis. It operates entirely within Redis and does not consume from RabbitMQ.

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Variable
     - Default
     - Description
   * - ``MASSIVE_API_KEY``
     - *(empty)*
     - Massive.com API key. Passed to ``AnalyzerOptions`` and forwarded to the
       analyzer. Required for analyzers that call the Massive API directly.
   * - ``WDC_REDIS_URL``
     - ``redis://mdc:mdc@localhost:6379/1``
     - Widget Data Cache Redis URL. MDS reads from and writes to WDC only;
       it never connects to MDC.
   * - ``DRA_CACHE_LIST_MAX``
     - ``1000``
     - Maximum number of HOD/LOD alert events retained in the
       ``dra:alerts:<TICKER>`` Redis list cache. Overrides the
       ``WidgetDataCacheLimits.DRA_CACHE_LIST_MAX`` enum default.
       Increase for deeper alert history; decrease to bound memory use.

----

Widget Data Service (WDS)
--------------------------

**Default port:** 4202

The WDS bridges Redis pub/sub to client WebSocket connections with fan-out.

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - Variable
     - Default
     - Description
   * - ``WDC_REDIS_URL``
     - ``redis://mdc:mdc@localhost:6379/1``
     - Widget Data Cache Redis URL. Read by WDS to deliver scanner results and
       quote feeds to connected WebSocket clients.
   * - ``AUTH_ENABLED``
     - ``false``
     - Enable API key authentication for WebSocket connections
   * - ``AUTH_API_KEY``
     - ``secret``
     - API key required when ``AUTH_ENABLED=true``
