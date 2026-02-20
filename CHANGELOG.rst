=========
Changelog
=========
Version 0.2.21 (2026-02-20)
===========================

- `e79c3be <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/e79c3be>`_ Move Architecture content to Code Organization

  Rename and relocate the 'Architecture' section to 'Code Organization' in README.md and README.rst. The platform package list was reformatted and moved under the new heading, preserving links and descriptions for the four main packages (mdp, servers, app, deployment).

- `5253b2e <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/5253b2e>`_ Rename Overview to Architecture in docs

  Update docs/index.rst to change the toctree entry label from "Overview" to "Architecture" (points to readme). This adjusts the sidebar/contents heading to better reflect the documentation content.

- `869903c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/869903c>`_ Move context diagram to Components Summary

  Relocate the Market Data Processing context diagram into the Components Summary section in both README.md and README.rst, and remove the duplicate instance later in the file. This places the diagram next to the high-level component list for clearer documentation and eliminates redundant images.

- `2ce1b5c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/2ce1b5c>`_ Add release workflow and changelog generator

  Add a new GitHub Actions 'Release' workflow to compute the next semver tag (manual bump: patch/minor/major), create/force the tag, run a changelog generator, and commit/push the updated CHANGELOG.rst and tag. Add update-changelog.sh: a script that builds CHANGELOG.rst from git tags/commits with commit links to the repository. Also update CHANGELOG.rst content format and add Update-Changelog.ps1 to .gitignore.

- `028b954 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/028b954>`_ Enhance docs with architecture & deployment

  Add detailed Data Plane, Control Plane, Observability, and Deployment Model sections to README.md and README.rst, describing MDL, MDQ, MDP, MDC, WDS, and SCP components, scaling and deployment notes, and OpenTelemetry logging/metrics. Insert architecture.svg reference and move the Context Diagram figure in the RST; remove the old ASCII art diagram. Also update docs/index.rst to remove the separate Architecture entry. Files changed: README.md, README.rst, docs/index.rst.

- `fffa756 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/fffa756>`_ Try adding images to README.rst
- `4ed2d81 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/4ed2d81>`_ Last-ditch effort to get the architecture diagram to render
- `f88e3c0 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/f88e3c0>`_ Inline PlantUML code in architecture.rst for ReadTheDocs rendering

  The sphinxcontrib-plantuml extension expects inline PlantUML code within the .. uml:: directive, not a file reference. This change embeds the complete PlantUML source from architecture.puml directly into the RST file so the diagram renders correctly on ReadTheDocs.

- `30a4338 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/30a4338>`_ Add architecture docs and diagrams

  Add component architecture documentation: new PlantUML source (docs/architecture.puml), rendered SVG (docs/architecture.svg), and Sphinx page (docs/architecture.rst). Update docs/conf.py, docs/index.rst, and docs/requirements.txt to include the new page and required tooling/extensions to render the diagram and integrate it into the site.

- `6fa3b0a <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/6fa3b0a>`_ Linting and style cleanups across MDP

  Add flake8 step to CI and apply styling/lint fixes across the MDP package. Reformat meter.create_counter calls to multi-line for readability in massive_data_analyzer, market_data_cache, and massive_data_processor; split a long debug log, simplify some f-strings and string literals, and adjust spacing in a sleep/log statement. Remove an unused typing import, add a noqa for the pythonjsonlogger import to satisfy linters, and fix missing/newline endings in package data files. These changes are aimed at improving readability and addressing flake8 issues.

- `0c5fc52 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/0c5fc52>`_ Update CHANGELOG.rst
- `44b640b <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/44b640b>`_ Expand README with project overview and features

  Update README.md and README.rst: remove example badge comments and add a concise project Overview and Architecture sections, list the four main packages (library, backend, frontend, deployment), include Key Features (real-time ingestion, microservices, automated deployment, multi-environment, OAuth, Redis caching) and an Additional Resources/blog links. Improves documentation clarity and provides quick entry points for contributors and users.

- `c924417 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/c924417>`_ Add repo link and rename Code Libraries section

  Clarify where the SCP implementation lives by adding a link to the kuhl-haus/kuhl-haus-mdp-app repository and rename the "Code Libraries" heading to "Miscellaneous Code Libraries" in README.md and README.rst. Also apply minor formatting tweaks to the section intro to keep both markdown and rst files consistent.

- `9625c40 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/9625c40>`_ Updated README files

Version 0.2.20 (2026-02-19)
===========================

- `7d725fe <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7d725fe>`_ Add/expand docstrings across mdp package

  Add and expand module/class/function docstrings and developer-facing comments across the kuhl_haus.mdp package. Changes document intent, lifecycle and concurrency behavior, Redis/RabbitMQ semantics, throttling, rehydration and shutdown handling for analyzers (Analyzer, LeaderboardAnalyzer, MassiveDataAnalyzer, TopStocksAnalyzer, TopTradesAnalyzer), components (MarketDataCache, MarketDataScanner, MassiveDataListener, MassiveDataProcessor, MassiveDataQueues, WidgetDataService), and data models. Clarifies cache/publish side effects, TTLs, distributed election/throttle patterns, queue/channel usage, and startup/stop semantics to improve maintainability and operator understanding. No functional logic changes intended — mainly documentation and clearer API/behavior explanations.

- `50acf88 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/50acf88>`_ feat: make observability.py cross-package compatible; rewrite non-conforming tests

  - Add _resolve_version() helper and optional pkg_name parameter to

  get_tracer() and get_meter() so dependent packages (e.g.

  kuhl-haus-mdp-servers) can resolve their own version for

  OpenTelemetry instrumentation. Fully backwards-compatible.

  - Add docstring examples to _resolve_version(), get_tracer(), and

  get_meter() showing default and cross-package usage.

  - Rewrite test_structured_logging.py (36 tests), test_market_data_cache.py

  (29 tests), and test_utils.py (13 tests) to conform to project test

  standards: AAA format, single-line Act, sut naming, test_X_with_Y_expect_Z

  convention, pytest fixtures, parameterized tests, PEP8 compliance.

  - Fix flake8 issues in test_massive_data_analyzer.py (remove unused import).

  - Add .output.txt to .gitignore.


Version 0.2.19 (2026-02-19)
===========================

- `368f31c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/368f31c>`_ Add market status handling to MassiveDataListener

  Introduce MarketStatusValue enum and integrate RESTClient market status checks into MassiveDataListener to drive reconnection logic (track healthy/reconnects, adjust sleep/retry behavior, and improve error logging). Update MassiveDataQueues with minor refactors for formatting. Add comprehensive tests for MassiveDataListener and MassiveDataQueues; added flake8 to requirements-test.txt.


Version 0.2.18 (2026-02-18)
===========================

- `ba8d3a3 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ba8d3a3>`_ Re-enable observability: tracing & metrics

  Restore observability instrumentation in MassiveDataQueues: re-enable get_tracer/get_meter import and initialize tracer and meter; recreate error/message counters and per-queue counters. Reapply tracer.start_as_current_span decorators to connect, handle_messages, _publish_message, shutdown and setup_queues, and re-enable counter increments (message_counter, error_counter, per-queue counters). These changes undo prior temporary comment-outs that disabled tracing/metrics (previously done due to MDL instability) and reintegrate monitoring without altering core message-publishing logic.

  https://github.com/kuhl-haus/kuhl-haus-mdp/issues/3

- `32ead83 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/32ead83>`_ Use instance attributes in connection_status

  Initialize connection_status with self.feed, self.market, and self.subscriptions instead of ctor parameters. This fixes incorrect values returned by the connection_status property after the feed, market, or subscriptions change post-initialization.


Version 0.2.17 (2026-02-18)
===========================

- `caf1ddd <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/caf1ddd>`_ perf(mdq): multi-channel concurrent publishing for higher throughput

  Replace single-channel sequential publishing with a dedicated channel per queue and concurrent publish via asyncio.gather to eliminate I/O latency as the throughput bottleneck.

  https://github.com/kuhl-haus/kuhl-haus-mdp/issues/3

  Changes:

  - Allocate one AMQP channel per queue (6 channels) so publishes to different queues are never serialized at the broker level

  - Batch-publish all messages concurrently with asyncio.gather instead of awaiting each publish sequentially in a loop

  - Pre-build all Message objects and resolve queue names before any network I/O begins

  - Add publisher_confirms constructor parameter (default True) to allow disabling broker ACKs for fire-and-forget throughput

  - Switch delivery mode from PERSISTENT to NOT_PERSISTENT since messages are ephemeral market data with short TTLs

  - Remove unused fanout_to_queues method; handle_messages now delegates to _publish_message directly

  - Update shutdown and setup_queues to manage per-queue channel lifecycle

  Before: sequential publishes on a single channel — each message waits for a full network round-trip (~20ms), limiting throughput to ~300 msg/s in production.

  After: concurrent publishes across 6 channels — overlapped I/O with optional confirm disable targets 5,000+ msg/s.


Version 0.2.16 (2026-02-18)
===========================

- `f96e4de <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/f96e4de>`_ Convert MassiveDataAnalyzer tests to async

  Update tests to match asynchronous analyzer API and new AnalyzerOptions. Imports pytest_asyncio and AnalyzerOptions, add analyzer_options fixture, mark relevant tests with pytest.mark.asyncio and await analyze_data. Restore cache key/ttl assertions for aggregate/trade/quote tests and inject AnalyzerOptions into MassiveDataAnalyzer construction. Remove legacy direct handler tests that are no longer required.


Version 0.2.15 (2026-02-18)
===========================

- `5f166de <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/5f166de>`_ Add TopTradesAnalyzer for Redis trade stats

  Introduce TopTradesAnalyzer: a Redis-backed, stateless analyzer that stores recent trades per symbol (LPUSH + LTRIM) and keeps a sliding window (max 1000 trades, 5m TTL). The analyzer aggregates per-symbol metrics (total_volume, trade_count, avg_size, max_size, time_span_ms, latest trade info) by scanning trade lists, and emits MarketDataAnalyzerResult payloads: a global widget with all symbol stats and individual widgets for the top 100 symbols by volume (10s TTL). Publishing is cluster-throttled via a distributed NX key (5s interval). The implementation includes Redis pipeline writes, defensive parsing, OpenTelemetry tracing spans, and observability counters for processed/published/errors. Uses MarketDataCache and clients provided by AnalyzerOptions.

- `f5050f7 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/f5050f7>`_ Remove opentelemetry-distro dependency

  Remove opentelemetry-distro from pyproject.toml dependencies. requirements.txt was also updated (binary diff) to reflect dependency changes so the requirements no longer include the removed package.

- `865c16b <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/865c16b>`_ MassiveDataAnalyzer: add tracing and metrics

  Refactor MassiveDataAnalyzer to inherit from Analyzer and accept AnalyzerOptions in the constructor. Add observability: initialize tracer and meter, instrument analyze_data and event handlers with tracing spans, and add counters for processed, luld, agg, trade, quote and unknown events. Convert analyze_data to async, remove per-instance cache flag fields, and consistently return results with cache keys/TTLs for agg/trade/quote events. Keep existing event handling behavior while improving telemetry.

- `48cf700 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/48cf700>`_ Rename leaderboard cache keys and enrich result docs

  Update LeaderboardAnalyzer to use leaderboard-scoped cache keys and rename the publish/throttle keys to avoid collisions. market_data_cache_keys: remove generic MARKET_* keys, add LEADERBOARD_MARKET_DAY_KEY, LEADERBOARD_MARKET_OPEN_RESET_KEY, and LEADERBOARD_PUBLISH_THROTTLE_KEY (renamed from PUBLISH_THROTTLE_KEY). market_data_analyzer_result: expand class docstring to describe purpose and fields (data, cache_key, cache_ttl, publish_key). market_data_pubsub_keys: clean up by removing commented/unused scanner entries.

- `f3bfb9c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/f3bfb9c>`_ Add error metrics and improve logging for MDC

  Add dedicated OpenTelemetry counters for general, timeout, and HTTP errors in MarketDataCache to improve observability. Upgrade exception logging to error level with stack_info and exc_info for timeout, aiohttp.ClientError, and generic exceptions, and increment the corresponding counters in each handler. Keeps existing negative-cache TTL behavior on failures and preserves raising on unexpected exceptions.


Version 0.2.14 (2026-02-17)
===========================

- `ecbdb07 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ecbdb07>`_ Reverting distributed tracing changes in MDL

  https://github.com/kuhl-haus/kuhl-haus-mdp/issues/3


Version 0.2.13 (2026-02-13)
===========================

- `1a5f932 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/1a5f932>`_ Reduce log verbosity and remove tracing comments

  Lowered logging levels across the mdp package (info/warning -> debug) to reduce noisy logs for normal subscription, cache, and API error paths. Removed module-level logging.basicConfig from helpers/utils to avoid configuring global logging, and cleaned up unused tracer import / commented span decorators in MassiveDataListener. No functional behavior changes besides logging level adjustments.


Version 0.2.12 (2026-02-13)
===========================

- `b685a43 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/b685a43>`_ Handle missing avg volume with negative cache

  If average volume lookup fails, log a warning instead of raising an exception; set avg_volume to 0 and use MarketDataCacheTTL.NEGATIVE_CACHE_SESSION for cache_ttl before writing. This prevents exception propagation and enables negative caching to avoid repeated lookups for missing data.


Version 0.2.11 (2026-02-13)
===========================

- `a2725e3 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a2725e3>`_ Propagate OTEL context to worker processes

  Capture and propagate OpenTelemetry trace context from the parent into spawned worker processes and enable auto-instrumentation in children. Adds injecting the current context when starting a Process and extracting/attaching it in the child entrypoint; also initializes OTel auto-instrumentation via sitecustomize in the child. Small typing and logging enhancements were included. pyproject and requirements updated to include OpenTelemetry packages.

  https://github.com/kuhl-haus/kuhl-haus-mdp/issues/2


Version 0.2.10 (2026-02-12)
===========================

- `040defd <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/040defd>`_ Add OpenTelemetry observability & metrics

  Introduce OpenTelemetry tracing and metrics across the MDP service. Adds new helpers/observability.py and registers opentelemetry-api/sdk in dependencies. Instrumented core components (leaderboard_analyzer, market_data_cache, massive_data_listener, massive_data_processor, massive_data_queues, widget_data_service, widget_data_service) to create meters/counters and wrap key methods with tracing spans; adjusted logging levels to use debug for cache/publish ops. Added negative cache TTLs to MarketDataCacheTTL and updated tests to assert negative-cache behavior and debug logging. These changes enable tracing and metric collection for monitoring and error/operation counts.


Version 0.2.9 (2026-02-11)
==========================

- `b9d542f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/b9d542f>`_ Initialize structured logging in MDP

  Import setup_logging and call it in MassiveDataProcessor.__init__ so structured logging is configured before obtaining the module logger. Ensures the component uses the application-wide logging format/configuration; no other functional changes.


Version 0.2.8 (2026-02-11)
==========================

- `bbfca6c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/bbfca6c>`_ Add structured logging and refactor components to use loggers

  Introduce an opinionated structured logging helper (kuhl_haus.mdp.helpers.structured_logging) and comprehensive unit tests. Refactor components to use logging.getLogger(__name__) instead of injected or module-level settings: MassiveDataListener, MassiveDataQueues, and WidgetDataService (removed Settings-based logging setup). Add python-json-logger to dependencies (pyproject.toml and requirements.txt updated) to support JSON formatting. This centralizes logging configuration and enables consistent, testable structured logs across the package.


Version 0.2.7 (2026-02-09)
==========================

- `2f725d9 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/2f725d9>`_ Replace duplicated metric with processing_error

  Rename the 'duplicated' counter to 'processing_error' and update exception handling to catch DataAnalysisException (imported from exceptions). Log data-analysis errors with exc_info and increment the new processing_error metric; adjust the generic exception log message. Update ProcessManager status keys to read 'decoding_error' and expose the new 'processing_errors' metric so metrics reflect the renamed field.


Version 0.2.6 (2026-02-09)
==========================

- `423a8de <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/423a8de>`_ Add DataAnalysisException and error handling

  Introduce a DataAnalysisException class and use it to surface analysis errors from LeaderboardAnalyzer instead of logging and returning None. Change MarketDataCache to log and return 0 when no prior periods are found rather than raising a generic Exception. Adds new exceptions package and a DataAnalysisException that accepts an optional cause to improve error propagation and clarity.


Version 0.2.5 (2026-02-09)
==========================

- `6ba435a <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/6ba435a>`_ Normalize falsy leaderboard fields to 0

  Use event.get(key) or 0 instead of event.get(key, 0) for several leaderboard fields so None or other falsy values are normalized to 0 when building the Redis mapping. Affected fields: official_open_price, high, low, aggregate_vwap, average_size, start_timestamp, and end_timestamp. This prevents storing None/empty values and keeps numeric fields consistent.


Version 0.2.4 (2026-02-09)
==========================

- `ba4ae7c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ba4ae7c>`_ Default avg_volume to 0 and log errors

  Set avg_volume to 0 when falsy to avoid storing None-like values, and raise the logging level from debug to error when pipeline execution fails so mapping details are recorded as errors. These changes improve robustness of leaderboard updates and make failures easier to diagnose.


Version 0.2.3 (2026-02-06)
==========================

- `1735a51 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/1735a51>`_ [BUGFIX] Exception on Null result from Analyzer

  Oops


Version 0.2.2 (2026-02-06)
==========================

- `56a1fdc <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/56a1fdc>`_ [BREAKING CHANGE] MDP Metrics

  **Removing 'dropped'; Adding 'published'**

  1. The 'dropped' metric didn't make any sense. The analyzer throttles downstream publication rates; the messages aren't actually dropped.

  2. The analyzer returns an array of MarketDataAnalyzerResults for downstream publication. The analyzer returns None or an empty array if it is not ready to publish.

  3. The 'published' counter will be incremented for each MarketDataAnalyzerResult published to Redis.


Version 0.2.1 (2026-02-06)
==========================

- `79a306c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/79a306c>`_ Try to handle null exception writing to leaderboard

Version 0.2.0 (2026-02-05)
==========================

- `8eba911 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/8eba911>`_ [Version 0.2.0] Leaderboard Analyzer

  Replacing the suboptimal Top Stocks Analyzer and Massive Data Analyzer combination with a single Leaderboard Analyzer implementation.


Version 0.1.18 (2026-02-04)
===========================

- `bdc7842 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/bdc7842>`_ Update .readthedocs.yml

Version 0.1.17 (2026-02-04)
===========================

- `0ce3604 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/0ce3604>`_ Update publish-to-pypi.yml
- `820e66b <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/820e66b>`_ Upgrade to Python 3.14
- `cb1b60a <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/cb1b60a>`_ Fix docstrings in utils.py
- `afd799d <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/afd799d>`_ Update project description in README.md
- `897bcaa <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/897bcaa>`_ Update Market_Data_Processing_C4.png

Version 0.1.16 (2026-01-14)
===========================

- `525eb72 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/525eb72>`_ Update to pre-market reset bugfix

  It seems resetting the symbol data cache wasn't quite enough. I'm just going to reset like it is a new day and see if that fixes the issue.  Anything is better than manual restart.

- `8b7ccb1 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/8b7ccb1>`_ Removed commented code

Version 0.1.15 (2026-01-13)
===========================

- `165e5f7 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/165e5f7>`_ BUGFIX: Pre-market reset

  Problem: Pre-market reset only works one-time.  self.pre_market_reset is set to False when TopStocksAnalyzer is initialized. self.pre_market_reset is set to True after the first pre-market reset with no mechanism to flip it back to False other than restarting the server/process.

  Solution: Set self.pre_market_reset to False when the cache is reset on each new day.


Version 0.1.14 (2026-01-09)
===========================

- `bbf44f2 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/bbf44f2>`_ Return top 500 stocks by volume

  Was 100 but I decided to increase it to 500 to match the other two scanners.  The increase in overall payload is a worthwhile trade-off.

  Average payload @100: 60KB

  Average payload @500: 300KB

  Average total payload for all 3 scanners:

  Before: 660KB

  After: 900KB


Version 0.1.13 (2026-01-09)
===========================

- `2e4fa32 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/2e4fa32>`_ delete ticker snapshot on exception
- `ba01412 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ba01412>`_ Fixed docs namespaces

Version 0.1.12 (2026-01-08)
===========================

- `1493c1a <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/1493c1a>`_ Reorganized namespace

  * Removed 'integ'

  * Removed 'models'

  * Added 'data' - contains cache-related data classes that were in previously in 'models'

  * Added 'enum' - contains Enums that were previously in 'models'


Version 0.1.11 (2026-01-08)
===========================

- `d13af9e <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/d13af9e>`_ Delete ticker snapshot from cache on KeyError

Version 0.1.10 (2026-01-06)
===========================

- `ac8a24d <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ac8a24d>`_ Remove unnecessary load on MDC Part 2

  oops, forgot the tests.

- `82e61b1 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/82e61b1>`_ Added exception logging in TopStocks
- `473a577 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/473a577>`_ Remove unnecessary load on MDC

  The cached entry is not used but adds unnecessary overhead.

- `2bdd1e6 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/2bdd1e6>`_ Easier to maintain cache TTLs

  Easier to maintain because the tests more resistant to refactoring.  TTL duration can be changed to arbitrary values by editing a single line of code in an Enum.  Prior to this change, adjusting the TTL would break the tests and require a bunch of search & replace ops to fix them.


Version 0.1.9 (2026-01-06)
==========================

- `c92042a <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/c92042a>`_ BUGFIX: TopStocks Scanner

  Fix: Return when get_avg_volume and get_ticker_snapshot fail after max tries.

  Justification: Storing zeros in the cache for snapshot and avg volume breaks things.  It is better to simply not process the event.  Free float, however, is optional/experimental.

- `996b4e4 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/996b4e4>`_ Fixed documentation URL in pyproject

Version 0.1.8 (2026-01-05)
==========================

- `203af5e <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/203af5e>`_ Added free float

  Note: this uses an experimental API and may break without warning


Version 0.1.7 (2026-01-05)
==========================

- `282b6ff <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/282b6ff>`_ Fixed MarketDataCache bugs

  Hard to validate this stuff during the weekend when there's no actual market data.  Integration is always hell.


Version 0.1.6 (2026-01-04)
==========================

- `e2a98b1 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/e2a98b1>`_ Specify Analyzer class in MarketDataScanner ctor

  This is kind of messy but the MarketDataScanner should not be dependent on a concrete class of Analyzer.  These components need to be refactored anyways so this will do for now.

- `1344b3e <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/1344b3e>`_ Added importlib_metadata

  Exception during document build on readthedocs.io:

  ModuleNotFoundError: No module named 'importlib_metadata'

- `ad84ee1 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ad84ee1>`_ Prefer readthedocs publishing

  I'm already hosting ur.janky.click on my github pages so publishing docs to github doesn't work correctly.

- `48a4685 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/48a4685>`_ Update README.rst
- `dad34f9 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/dad34f9>`_ Added create docs workflow

Version 0.1.5 (2026-01-03)
==========================

- `3bef87a <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/3bef87a>`_ Update publish-to-pypi.yml

Version 0.1.4 (2026-01-03)
==========================

- `ec19b41 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ec19b41>`_ Market Data Cache implementation

  Added cache-integrated async methods to get ticker snapshots, average volume, and free float.  The get_ticker_snapshot and get_avg_volume methods in TopStocksAnalyzer were removed in favor of the MarketDataCache implementations.

  Free float uses an experimental API from Massive. If it works well, I won't need to add another provider to get it.  I'll see how it works next week and make a decision based on real-world results.

- `54e213a <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/54e213a>`_ Add pytest-asyncio to test dependencies
- `ad201df <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ad201df>`_ Moved integ/utils.py to helpers

Version 0.1.3 (2025-12-31)
==========================

- `a09c40a <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a09c40a>`_ Only build images on non-tagged mainline pushes
- `47dc4b3 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/47dc4b3>`_ Test publishing on non-tagged mainline pushes.
- `facc3c9 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/facc3c9>`_ refactored TopStocksCacheItem

Version 0.1.2 (2025-12-31)
==========================

- `d7dc656 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/d7dc656>`_ Converted Massive data analyzer from async to sync

  There's no I/O in the MassiveDataAnalyzer so no point handling async.


Version 0.1.1 (2025-12-30)
==========================

- `7516f32 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7516f32>`_ test coverage for message SerDe and queue name resolver
- `3013c6a <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/3013c6a>`_ Added components description to readme file

Version 0.1.0 (2025-12-26)
==========================

- `8662309 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/8662309>`_ Dynamic versioning with setuptools-scm
- `0579b19 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/0579b19>`_ Update CodeQL badge on readme
- `d49436b <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/d49436b>`_ Add CodeQL analysis workflow configuration

Version 0.0.1 (2025-12-24)
==========================

- `0bd1d06 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/0bd1d06>`_ Install via pip instead of PDM
- `a42fe54 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a42fe54>`_ Revert "Hacky work-around for ModuleNotFound error in PDM build."

  This reverts commit 77b1d0e88a8b8854c303fc606f10af821f057717.

- `ee4d58a <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ee4d58a>`_ Added importlib_metadata to requirements.txt
- `77b1d0e <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/77b1d0e>`_ Hacky work-around for ModuleNotFound error in PDM build.
- `1f8a6b2 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/1f8a6b2>`_ Install test dependencies in workflow
- `f6303f6 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/f6303f6>`_ Initial commit

