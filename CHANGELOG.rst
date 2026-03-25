=========
Changelog
=========
Version 0.3.4 (2026-03-25)
==========================

- `1f0f16c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/1f0f16c>`_ Add ticker cache and Finlight language

  Always publish articles to the feed and include per-ticker publish entries with proper cache_key and cache_ttl. Update MarketDataCacheTTL: NEWS_FEED_LATEST -> ONE_DAY and add NEWS_TICKER -> THREE_DAYS. Set Finlight WebSocket params to include language="en" for both raw and normal article streams. Tests updated to reflect new cache_key/ttl behavior and language parameter expectations.

- `28575b6 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/28575b6>`_ chore: consolidate deps into pyproject.toml, delete requirements txt files (#39)

  - Add importlib_metadata and tzdata to [project.dependencies]

  - Add setuptools-scm, pdm, flake8 to [project.optional-dependencies].testing

  - Dockerfile: replace requirements.txt install with pip install .

  - publish-to-pypi.yml: replace two-step install with pip install .[testing]

  - CLAUDE.md: update dev install instructions, add no-requirements.txt warning

  - Delete requirements.txt and requirements-test.txt

  docs/requirements.txt retained — used by ReadTheDocs for Sphinx builds only.


Version 0.3.3 (2026-03-25)
==========================

- `fb3ac47 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/fb3ac47>`_ Version 0.3.3 (2026-03-25)
- `bb90ef0 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/bb90ef0>`_ Add ticker cache and Finlight language

  Always publish articles to the feed and include per-ticker publish entries with proper cache_key and cache_ttl. Update MarketDataCacheTTL: NEWS_FEED_LATEST -> ONE_DAY and add NEWS_TICKER -> THREE_DAYS. Set Finlight WebSocket params to include language="en" for both raw and normal article streams. Tests updated to reflect new cache_key/ttl behavior and language parameter expectations.

- `899edf9 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/899edf9>`_ fix: refactor FinlightDataListener to match working pattern (closes #37) (#38)

  Fixes all six defects identified in issue #37:

  1. WebSocketOptions/RawWebSocketOptions(takeover=True) to prevent session conflicts

  2. Direct await on connect (not asyncio.gather with swallowed exceptions)

  3. while-loop reconnect in single task — no recursive start() / task leak

  4. Task cancellation for stop() — not SDK .stop() call

  5. Property setters still trigger restart; no change to that interface

  6. includeEntities=True by default on enhanced subscriptions

  Also preserves max_reconnects support and async/sync handler dispatch

  via inspect.iscoroutinefunction() + loop.create_task().

  27 tests, 99% branch coverage.


Version 0.3.2 (2026-03-25)
==========================

- `1eca24e <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/1eca24e>`_ Version 0.3.2 (2026-03-25)
- `7ca77f6 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7ca77f6>`_ feat: FinlightDataAnalyzer — stateless news article router (closes #35) (#36)

  Adds FinlightDataAnalyzer, an Analyzer subclass for routing Finlight news

  articles to Redis pub/sub via FinlightDataProcessor.

  Routing:

  - All articles → MarketDataPubSubKeys.NEWS_FEED_LATEST (news:feed:latest)

  - Enhanced mode (companies field present): tickers from primaryListing.exchangeCode,

  US exchanges only (XNYS/XASE/XNAS)

  - Raw mode: tickers via regex (Nasdaq: TICKER), (NYSE:TICKER) etc. from title + summary

  - Per-ticker → MarketDataPubSubKeys.NEWS_TICKER (news:ticker:{ticker})

  Also adds:

  - MarketDataPubSubKeys.NEWS_FEED_LATEST and NEWS_TICKER

  - MarketDataCacheTTL.NEWS_FEED_LATEST (1 hour)

  36 tests, 99% branch coverage.

- `7171437 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7171437>`_ docs: fix Configuration Reference inaccuracies (closes #33) (#34)

  - Common: remove RABBITMQ_URL, REDIS_URL, MDQ_PUBLISHER_CONFIRMS,

  MARKET_DATA_MESSAGE_TTL — these are not universal; moved to each

  server that actually uses them

  - FDL: remove stale FINLIGHT_TICKERS, FINLIGHT_SOURCES,

  FINLIGHT_MAX_RECONNECTS (removed in FinlightSimpleListener refactor);

  add FINLIGHT_INCLUDE_ENTITIES; remove stale runtime filter endpoint note;

  add per-server RabbitMQ vars

  - MDL/MDP/LBA: add MASSIVE_API_KEY (required, previously undocumented)

  - LBA: add PARALLELISM, PREFETCH_COUNT, MAX_CONCURRENCY (previously missing)

  - WDS: add AUTH_ENABLED and AUTH_API_KEY (previously missing);

  correct REDIS_URL default (no credentials for WDS)

- `6e4ac31 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/6e4ac31>`_ Removed Configuration section from README

  Refer to the docs instead.

  https://kuhl-haus-mdp.readthedocs.io/en/latest/configuration.html


Version 0.3.1 (2026-03-25)
==========================

- `3472967 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/3472967>`_ Version 0.3.1 (2026-03-25)
- `8812802 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/8812802>`_ test: add unit tests for FinlightSimpleListener (closes #29) (#32)

  24 tests, 99% branch coverage.

  Covers: __init__ (all param combinations, API/params construction),

  start (task created, running set), stop (cancel + status cleared,

  no-op on done/no task), _run (enhanced + raw modes, connected status,

  on_article callback, reconnect on exception, CancelledError exit),

  _handle_article (to_dict called, handle_message called, articles_received

  incremented before handle_message, exception counted not raised,

  cumulative counts), parameterized mode combinations.

- `352eda6 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/352eda6>`_ Refactor FinlightSimpleListener init & logging

  Initialize and reuse FinlightApi and websocket params in __init__ (raw vs normal) instead of recreating clients on each connect. Replace module-level tracer and json usage with kuhl_haus.mdp.helpers.serde.to_dict for article serialization and pass dicts to queues.handle_message. Introduce an instance logger (self.logger) and update log calls. Remove unused query/tickers/sources/language attributes and simplify the on_article handler to schedule _handle_article on the event loop. These changes improve resource reuse, simplify the control flow, and standardize serialization.

- `c8549d4 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/c8549d4>`_ feat: add general-purpose serde helper (closes #30) (#31)

  Copies to_dict() from legion-mcp into kuhl_haus.mdp.helpers.serde.

  Recursively converts arbitrary objects (dataclasses, Pydantic models,

  nested objects, primitives) to JSON-serializable dicts.

  35 tests, 100% branch coverage.

- `b86b649 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/b86b649>`_ Remove GitHub Actions release workflow
- `fcb4c9b <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/fcb4c9b>`_ feat: add FinlightSimpleListener — verified working Finlight SDK pattern (#28)

  Adds FinlightSimpleListener using the exact pattern verified to work

  with the Finlight SDK on dev hardware:

  - WebSocketOptions(takeover=True) / RawWebSocketOptions(takeover=True)

  - includeEntities=True for entity-tagged articles (enhanced mode)

  - Sync on_article callback that schedules async queues.handle_message

  via loop.create_task() — avoids unawaited coroutine warning

  - Auto-reconnect on disconnect (5s delay)

  FinlightDataListener remains unchanged for backwards compatibility.

- `4511a64 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/4511a64>`_ fix: schedule async message_handler as task in FinlightDataListener (#27)

  The Finlight SDK calls on_article synchronously. When message_handler

  is a coroutine (e.g. FinlightDataQueues.handle_message), the call returns

  an unawaited coroutine object, triggering:

  RuntimeWarning: coroutine 'FinlightDataQueues.handle_message' was never awaited

  Fix: in async_task, detect if message_handler is a coroutine function via

  inspect.iscoroutinefunction(). If so, wrap it in a sync shim that calls

  loop.create_task() to schedule the coroutine on the running event loop.

  Sync handlers are passed through unchanged.

- `e64dd18 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/e64dd18>`_ docs: no Co-Authored-By trailers in commits (#26)
- `7cbe6c3 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7cbe6c3>`_ docs: remove contents directive from configuration.rst (#25)

  Furo-based docs handle navigation natively; manual TOC is

  unnecessary and causes a Sphinx warning.

  Co-authored-by: Tom Pounders <git@oldschool.engineer>

- `73847ec <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/73847ec>`_ docs: add Configuration Reference page (#24)

  * docs: add Configuration Reference page

  Documents all environment variables for all servers (FDL, FDP, MDL, MDP,

  LBA, WDS) organized by server with defaults and descriptions. Common

  variables (LOG_LEVEL, RABBITMQ_URL, REDIS_URL, etc.) listed once at the

  top. Added to toctree in index.rst.

  Co-Authored-By: Tom Pounders <git@oldschool.engineer>

  * docs: correct default ports in Configuration Reference

  FDL: 4203, FDP: 4204, WDS: 4202, LBA: 4210 (was 4200/4202/4200/4201)

  Co-Authored-By: Tom Pounders <git@oldschool.engineer>

  ---------

  Co-authored-by: Tom Pounders <git@oldschool.engineer>

- `40cdd50 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/40cdd50>`_ docs: add FDL and FDP to architecture docs (#23)

  - architecture.puml: add Finlight cloud, FDL and FDP packages,

  Finlight→FDL→MDQ→FDP→MDC flow, OTel/logging wiring for FDL and FDP

  - architecture.rst: add FDL and FDP to data plane components summary,

  and full component description sections with code library references

  Co-authored-by: Tom Pounders <git@oldschool.engineer>


Version 0.3.0 (2026-03-24)
==========================

- `410cfe2 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/410cfe2>`_ Update CHANGELOG for v0.3.0

  Add a new Version 0.3.0 changelog section with detailed entries. Highlights: add --bump CLI support to update-changelog.sh; change release workflow to create a release branch/PR and adopt peter-evans/create-pull-request@v7; introduce Finlight components (FinlightDataProcessor, FinlightDataQueues, FinlightDataListener) and associated tests; remove NEWS queue handling from MassiveDataQueues; various test fixes and documentation additions (CLAUDE.md, AGENTS.md), blog link updates, and CI/tooling bumps. Includes contributor and co-authorship notes and minor formatting/cleanup.

- `c3b8556 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/c3b8556>`_ Add --bump option to update-changelog.sh

  Add CLI support to update-changelog.sh to generate unreleased changelog entries and compute the next version via --bump (major|minor|patch). The script now validates arguments, determines the next semantic version from the latest v-tag, emits a dated changelog section with commit links and bodies, and handles formatting. CONTRIBUTING.rst was updated with platform-specific usage examples (bash and PowerShell) explaining how to run the script and the release workflow steps. Minor cleanup: removed an obsolete release-workflow link.

- `a049250 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a049250>`_ Updated the release workflow to use peter-evans/create-pull-request@v7

  Updated the release workflow to use `peter-evans/create-pull-request@v7` action instead of `gh pr create`.

  This action:

  1. Works with the default `GITHUB_TOKEN` without requiring a PAT

  2. Handles the branch creation and push automatically

  3. Creates the PR targeting `mainline`

  4. Automatically deletes the release branch after the PR is merged

  5. Properly handles git tags created in the workflow

  The workflow now complies with repository branch protection rules by creating a PR instead of pushing directly to mainline.

- `028e845 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/028e845>`_ Create release branch and PR in workflow

  Update the release GitHub Actions workflow to create a release branch, commit the updated CHANGELOG.rst to that branch, and open a pull request instead of directly pushing tags. Adds pull-requests: write permission, sets a release branch name in GITHUB_ENV, pushes the branch, and uses the gh CLI to create a PR targeting mainline. This prepares releases via a PR merge (after which tags can be pushed to trigger the publish job) and centralizes changelog updates in a reviewable change.

- `838470f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/838470f>`_ feat: FinlightDataProcessor component (#22)

  * test: add FinlightDataProcessor unit tests (TDD — tests first, red phase)

  Co-Authored-By: Tom Pounders <git@oldschool.engineer>

  * feat: implement FinlightDataProcessor component (closes #16)

  Mirrors MassiveDataProcessor with Finlight-specific adaptations:

  - No massive_api_key param; AnalyzerOptions receives only redis_url

  - _process_message deserializes with json.loads directly (no WebSocketMessageSerde)

  - All OTel counter names use fdp. prefix

  Co-Authored-By: Tom Pounders <git@oldschool.engineer>

  * docs: update commit authorship convention in CLAUDE.md

  Co-Authored-By: Tom Pounders <git@oldschool.engineer>

  ---------

  Co-authored-by: Tom Pounders <git@oldschool.engineer>

- `164ef71 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/164ef71>`_ Remove NEWS queue handling from MassiveDataQueues

  Remove the 'news' message type from the MassiveDataQueue enum and strip all handling for it in MassiveDataQueues.

  Reason: Massive doesn't have a WebSocket-based news feed.

- `37caccb <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/37caccb>`_ feat: FinlightDataQueues component (#21)

  * test: add FinlightDataQueues unit tests (TDD — tests first, red phase)

  * feat: implement FinlightDataQueues component (closes #20)

  Adds FinlightDataQueue enum (ARTICLES = "finlight.articles") and

  FinlightDataQueues class that publishes Finlight article data to

  RabbitMQ. Mirrors the MassiveDataQueues pattern: dedicated per-queue

  channel, passive queue verification on connect, NOT_PERSISTENT delivery,

  OpenTelemetry metrics with "fdq." prefix, and graceful shutdown.

  handle_message() accepts Pydantic models (via model_dump) or plain dicts,

  validates input type, serializes to UTF-8 JSON bytes, and publishes to

  the articles queue. _publish_message() logs errors without re-raising.

  * test: rename FinlightDataQueue.ARTICLES → NEWS in test suite (TDD — red phase)

  * feat: rename FinlightDataQueue.ARTICLES → NEWS

  - FinlightDataQueue: ARTICLES ("finlight.articles") → NEWS ("news")

  - MassiveDataQueue.NEWS removal is out of scope for this PR

- `c3ba6ea <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/c3ba6ea>`_ feat: add FinlightDataListener (FDL) component (#15) (#19)
- `551cb1b <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/551cb1b>`_ test: fix minor issues in test_structured_logging (#14)

  - test_sl_setup_with_multiple_calls_expect_last_wins: assert handler

  count is 1 after two setup_logging calls (guards against duplicate

  handler accumulation)

  - test_sl_log_exception_with_extra_fields_expect_logged: switch to JSON

  format and assert extra kwargs (user_id, code) appear under the

  'extra_fields' key in the JSON output, matching the test's intent

  - test_sl_output_with_special_message_expect_logged: strengthen the

  10k-char case to assert output.count('A') >= 10_000 rather than

  'A' in output, which would pass even on truncation

  Fixes #13

  Co-authored-by: Tom Pounders <git@oldschool.engineer>

- `a26f1c0 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a26f1c0>`_ ci: bump Docker actions to Node.js 24-compatible versions (#10) (#11)
- `42197a4 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/42197a4>`_ docs: update blog links to canonical oldschool-engineer.dev (#8) (#9)
- `5cfe3c7 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/5cfe3c7>`_ docs: add CLAUDE.md and AGENTS.md for AI agent maintainers (#7)

  Closes #6

  Co-authored-by: Tom Pounders <git@oldschool.engineer>


Version 0.2.28 (2026-02-25)
===========================

- `eec32d5 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/eec32d5>`_ Update CHANGELOG.rst for v0.2.28
- `a02de2f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a02de2f>`_ Fix: Handle LockNotOwnedError gracefully in Redis lock release

  The LockNotOwnedError was raised when a Redis distributed lock expired before the finally block could release it. Even though the code checked lock.locked(), a race condition exists where the lock can expire between the check and the release() call.

  Changes made to market_data_cache.py:

  • Added import: from redis.exceptions import LockNotOwnedError

  • Wrapped lock release in try/except LockNotOwnedError blocks in all three _fetch_*_with_lock methods:

  ◦ _fetch_free_float_with_lock (the originally reported method)

  ◦ _fetch_avg_volume_with_lock

  ◦ _fetch_snapshot_with_lock

  When a LockNotOwnedError occurs, it is now logged as a warning instead of propagating as an unhandled exception.


Version 0.2.27 (2026-02-24)
===========================

- `7304722 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7304722>`_ Update CHANGELOG.rst for v0.2.27
- `51e645f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/51e645f>`_ MDC.get_free_float - Add coordinated free-float cache and lock

  Implement coordinated fetching and caching for ticker free-float values to prevent stampeding-herd and reduce redundant API calls. Changes include:

  - Add in-process coalescing via self._pending_free_floats (asyncio.Event) so concurrent coroutines wait instead of racing.

  - Add free_float_api_duration histogram metric to measure Massive API call durations.

  - Refactor get_free_float to register/wait on an event and delegate the actual fetch to _fetch_free_float_with_lock.

  - Add _fetch_free_float_with_lock which acquires a Redis distributed lock, double-checks the cache, calls the Massive /float endpoint, applies negative caching on errors/timeouts, records metrics, writes the result to Redis, and releases the lock.

  - Add TICKER_FREE_FLOAT_LOCK key and TICKER_FREE_FLOAT_LOCK TTL enum entries.

  This prevents redundant HTTP requests across coroutines and instances, provides observability for API latency, and applies negative caching to avoid hammering the external API during failures.

- `c98d25f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/c98d25f>`_ MDC.get_avg_volume - Add avg-volume lock & in-process coalescing

  Implement coordinated avg-volume fetches to avoid stampeding herds: add an in-process pending-event map and a Redis distributed lock for per-ticker avg-volume requests. Record avg_volume_api_duration histogram, move fetch logic into _fetch_avg_volume_with_lock which double-checks cache after acquiring the lock, computes avg volume from financial ratios or daily aggs, applies negative caching on failures, and ensures lock release. Add new cache key and TTL enums for the avg-volume lock. Update tests to cover cache-hit behavior, lock acquisition/release, double-check hits, duration recording, pending-event handling, and cleanup of pending state.

- `ec1af06 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ec1af06>`_ MDC.get_ticker_snapshot - Add per-ticker locking and in-process coalescing

  Prevent stampeding-herd on ticker snapshot cache misses by adding a two-layer coordination strategy: an in-process asyncio.Event per ticker (_pending_snapshots) to collapse concurrent coroutines, and a Redis distributed lock (TICKER_SNAPSHOT_LOCK) to ensure only one instance calls the external API. Instrument the snapshot API call with a histogram (snapshot_api_duration) to collect durations for tuning lock TTL. Add a helper private method to acquire the lock, double-check the cache, fetch from the REST client, and populate Redis; ensure locks are released safely. Introduce a THIRTY_SECONDS constant and a TTL enum entry for the snapshot lock. Update unit tests to cover the new locking/event behavior and instrumentation, and add a mock lock helper.

- `bb50bb8 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/bb50bb8>`_ Add Part 5 link to README

  Add a new entry to the 'Additional Resources' section in README.rst linking to Part 5: 'Wave 1 Complete: Bugs, Bottlenecks, and Breaking 1,000 msg/s' so readers can access the latest article in the series.

- `44d4c57 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/44d4c57>`_ Fix: Explicit type annotation for data dict in ticker_snapshot_to_dict

  Added an explicit Dict[str, Any] type annotation to the data variable on line 56 of utils.py.

  Previously, the IDE inferred a narrow type (Dict[str, str | None | float | int]) from the initial dictionary literal values. When nested dicts were later assigned as values (lines 64-136), this caused type mismatch warnings. The explicit annotation resolves all the warnings by telling the type checker that data can hold Any values.

- `2fe481d <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/2fe481d>`_ Update docs links and docstring formatting

  Replace plain code references in docs/architecture.rst with Sphinx-style links to the ReadTheDocs API pages for components, enums, helpers and analyzers. Clean up examples and formatting in structured_logging.py to use reST literal blocks (::) and consistent indentation, and adjust the get_logger example. Tidy the get_massive_api_key docstring in utils.py to use ordered list/comments for resolution steps. These are documentation/code-comment improvements only and do not change runtime behavior.


Version 0.2.26 (2026-02-21)
===========================

- `0a3dc03 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/0a3dc03>`_ Update CHANGELOG.rst for v0.2.26
- `34fe6be <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/34fe6be>`_ Fix WDS pmessage bug, remove dead code, drive test coverage to 99%

  Resolves kuhl-haus/kuhl-haus-mdp#4

  See https://github.com/kuhl-haus/kuhl-haus-mdp/issues/4#issuecomment-3939560525

  - Fix silent drop of all wildcard subscription messages in WDS

  (_handle_pubsub only checked "message", not "pmessage")

  - Fix stale _pubsub_task reference in WDS stop()

  - Remove unreachable else branch in MDP start()

  - Add 31 tests (367→398) covering P0 bugs, P1 branch gaps, P2 scenarios

  - Coverage: 97% → 99% (1853 stmts, 5 missed; 364 branches, 1 partial)


Version 0.2.25 (2026-02-21)
===========================

- `29f6979 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/29f6979>`_ Update CHANGELOG.rst for v0.2.25
- `922b667 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/922b667>`_ Fix stale connection_status and auto-restart MDL on property changes

  Convert feed, market, and subscriptions from plain attributes to properties with getters/setters that keep connection_status dict in sync on every reassignment. Previously, reassigning these attributes broke the shared reference established in init, leaving connection_status stale.

  Add auto-restart behavior: when feed, market, or subscriptions are changed while the MDL is connected, the setter schedules an asyncio.create_task( self.restart()) so callers no longer need a separate API call to restart.

  Add 8 new unit tests covering:

  • connection_status stays synced after feed/market/subscriptions reassignment

  • restart is triggered when properties change while connected

  • exception branches in stop() and restart() log errors and reset state

  Patch asyncio.sleep in two existing slow tests to eliminate real sleeps.

- `e1aa22d <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/e1aa22d>`_ tests(mdl): mock asyncio.sleep and shorten test name

  Rename a long test name to a shorter one for readability and add patching of asyncio.sleep (AsyncMock) in stop/restart tests in tests/components/test_massive_data_listener.py. Patching prevents real sleeps during sut.stop() and sut.restart(), avoids delays/flakiness, and ensures assertions run with the sleep mocked.

- `903a257 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/903a257>`_ Update index.rst
- `fe014a2 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/fe014a2>`_ Add architecture docs with PlantUML support

  Move the architecture content out of README into Sphinx docs and add PlantUML-based diagrams. Adds docs/architecture.rst and a full-page architecture-diagram.rst, a custom CSS to constrain PlantUML output, and removes the large embedded SVG. Updates Sphinx/ReadTheDocs config (conf.py, index.rst, docs/requirements.txt, .readthedocs.yml) to enable PlantUML on the build environment and ignores docs/plantuml.jar in .gitignore. Also small whitespace cleanups in build scripts and README updated to link to the full docs on Read the Docs.

- `6ed5c36 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/6ed5c36>`_ Added SECURITY.md stub for GitHub Security tab

  GitHub only recognizes SECURITY.md (Markdown) for the Security tab — it does not support .rst files. Created a minimal SECURITY.md that links readers to the full security policy on Read the Docs, avoiding the need to maintain duplicate content. SECURITY.rst remains the single source of truth, consumed by Sphinx/RTD.

- `dc7a99e <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/dc7a99e>`_ Convert security policy to RST and link docs

  Remove SECURITY.md and add a reStructuredText version (SECURITY.rst) as the canonical security policy. Add docs/security.rst to include the top-level SECURITY.rst into the Sphinx docs, and update docs/index.rst to add a "Security Policy" entry in the docs table of contents. This standardizes the security documentation format for the project's Sphinx documentation.

- `51ae175 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/51ae175>`_ Remove PyCharm run configs note from CONTRIBUTING

  Delete the parenthetical mention of PyCharm run configurations in CONTRIBUTING.rst. The docs now simply instruct contributors to use the provided scripts from the project root, removing an IDE-specific reference that may be outdated or unnecessary.

- `1eab2f5 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/1eab2f5>`_ Remove sphinx-inline-tabs and update docs

  Drop the sphinx-inline-tabs extension and its dependency, and replace tab-based markup in CONTRIBUTING.rst with plain bold headings and standard code-blocks. docs/conf.py no longer lists the extension and docs/requirements.txt removes the package, so the documentation build no longer depends on sphinx-inline-tabs. Adjusted CONTRIBUTING.rst formatting/indentation to match the new markup.

- `fdb3301 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/fdb3301>`_ Use raw GitHub URLs for README figures

  Replace local figure references in README.rst with raw.githubusercontent.com links so images render when the README is viewed externally. Updated two figure references: Market_Data_Processing_C4.png and architecture.svg to point to the mainline/docs path on GitHub.


Version 0.2.24 (2026-02-21)
===========================

- `c0231df <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/c0231df>`_ Update CHANGELOG.rst for v0.2.24
- `033adf3 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/033adf3>`_ Remove setup.py/setup.cfg; clean pyproject.toml

  Delete legacy setup.py and setup.cfg and consolidate project configuration in pyproject.toml. Remove setuptools-specific sections (tool.setuptools, tool.setuptools_scm) and devpi.upload entries, drop setuptools-scm from build-system requires (using pdm backend), and simplify pytest and flake8 exclude lists. Also normalize project URLs (remove .git from Source and point Changelog to CHANGELOG.rst). These changes modernize packaging to PEP 517/518 with pdm and remove redundant legacy config.

- `c7040cc <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/c7040cc>`_ Remove README.md and tox.ini; switch to README.rst

  Delete the legacy README.md and tox.ini files and update pyproject.toml to reference README.rst instead of README.md. This aligns packaging metadata with the repository's README format and removes the standalone tox configuration.

- `7fb8194 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7fb8194>`_ Update CONTRIBUTING to use venv and pip

  Replace previous PDM-based setup with explicit virtualenv instructions and pip installs. Adds platform-specific venv activation examples (Linux/macOS and Windows), uses requirements.txt and requirements-test.txt for dependency installation, and removes older PDM install steps and PyCharm-specific notes. Also updates the release checklist to require passing workflows for the latest commit instead of only unit tests.

- `73f37f6 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/73f37f6>`_ Sphinx docs: tabs, copybutton and theme tweaks

  Replace platform-specific build instructions in CONTRIBUTING.rst with Sphinx inline tabs and language-specific code blocks for Linux/macOS and Windows. Add sphinx_copybutton and sphinx_inline_tabs to docs/conf.py and docs/requirements.txt to enable copy-buttons and inline tabs. Normalize the release version by stripping local/dev suffixes, add theme color variables, navigation keys and a GitHub footer icon, and extend intersphinx mappings for redis, fastapi and pydantic to improve documentation UX and cross-references.


Version 0.2.23 (2026-02-20)
===========================

- `ad9fdf6 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ad9fdf6>`_ Update CHANGELOG.rst for v0.2.23
- `446f05f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/446f05f>`_ Switch Sphinx docs theme to furo

  Update Sphinx theme from 'alabaster' to 'furo' in docs/conf.py and clear theme-specific options (removed custom sidebar/page width settings). Also add 'furo' to docs/requirements.txt and remove the commented-out sphinx_rtd_theme entry. This aligns docs with the furo theme and removes unused alabaster options.

- `3be0a8f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/3be0a8f>`_ Add doc build scripts and update docs

  Add cross-platform documentation build scripts (build-docs.sh and Build-Docs.ps1) that run sphinx-build, support a clean flag, and open the generated docs in the default browser. Revamp CONTRIBUTING.rst to document PDM-based workflow (Python 3.14), local build/test/style commands, CI release workflow links, and clearer contributor instructions. Update docs configuration and index (maxdepth change, sphinx-apidoc tweak) and add/adjust numerous package/module rst files (components, analyzers, data, enum, helpers, exceptions) to include new automodule entries and improve structure. Minor README formatting fix and adjust modules.rst depth.

- `a282615 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a282615>`_ Fix docstring formatting for Sphinx

  Update docstrings to use reStructuredText/Sphinx markup: replace quoted inline code with code literal (``leaderboard:*``) in widget_data_service.py, and change `Example:` to `Example::` with a blank line in structured_logging.py so examples render as code blocks and documentation is consistent.

- `12d1be3 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/12d1be3>`_ Increase toctree maxdepth to 5

  Update docs/mdp/modules.rst to raise the Sphinx toctree :maxdepth: from 4 to 5 so deeper nested pages are included in the generated table of contents.

- `1b952f5 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/1b952f5>`_ Add package docstrings and Sphinx automodules

  Add descriptive module docstrings to kuhl_haus.mdp and subpackages (analyzers, components, exceptions) to provide package-level descriptions and context. Update Sphinx RST files for mdp, analyzers, components, data, enum, and helpers by moving  "Module contents" automodule section to the top of the page, improving generated documentation page flow.


Version 0.2.22 (2026-02-20)
===========================

- `717fc36 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/717fc36>`_ Update CHANGELOG.rst for v0.2.22
- `59fcb53 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/59fcb53>`_ Disable force-tagging in release workflow

  Comment out the git tag -f and forced tag push in .github/workflows/release.yml so the workflow no longer moves or force-pushes the release tag. The job still commits and pushes the updated CHANGELOG, and a TODO was added to investigate a safe way to trigger a release without rewriting tags from CI.


Version 0.2.21 (2026-02-20)
===========================

- `4c39049 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/4c39049>`_ Update CHANGELOG.rst for v0.2.21
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

