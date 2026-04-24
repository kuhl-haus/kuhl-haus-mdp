=========
Changelog
=========
Version 0.4.16 (2026-04-23)
===========================

- `a4947d2 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a4947d2>`_ feat(DailyRangeAnalyzer): embed full quote in HOD/LOD alert payloads (refs #110) (#111)

Version 0.4.15 (2026-04-23)
===========================

- `067dfa9 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/067dfa9>`_ Version 0.4.15 (2026-04-23)
- `4204b92 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/4204b92>`_ fix(cache_result): honor cache_list_max in MarketDataScanner and MassiveDataProcessor (refs #108) (#109)

  Both cache_result implementations previously wrote all results as strings

  (SET/SETEX), ignoring cache_list_max. Results with cache_list_max set are

  now written as Redis lists (LPUSH + LTRIM), matching FinlightDataProcessor.

  This fixes daily_range_hod_alert and daily_range_lod_alert, which were

  storing only the most recent alert instead of the intended cap of 100.

  TTL is applied via EXPIRE after LTRIM when cache_ttl > 0.

  Redundant double-guard on cache_ttl removed (simplified to cache_ttl > 0).

  Boundary test added: cache_list_max=1 → ltrim(key, 0, 0).

  6 new tests added (3 per component); 743/743 passing.


Version 0.4.14 (2026-04-22)
===========================

- `3249f27 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/3249f27>`_ Version 0.4.14 (2026-04-22)
- `cb4c132 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/cb4c132>`_ feat(DailyRangeAnalyzer): emit HOD/LOD alert events on new session extremes (#107)

  * feat(DailyRangeAnalyzer): emit HOD/LOD alert events on new session extremes (refs #106)

  - analyze_data() now returns [state_result, *alert_results]; state is always first

  - _update_session_hod_lod() returns List[MarketDataAnalyzerResult] (was None)

  - Alerts suppressed on first tick (no prior value); only strictly new extremes emit

  - Two channels: daily_range_hod_alert / daily_range_lod_alert — shared by all tickers

  - cache_list_max=100, TTL=8h per channel (WDC layer trims oldest on overflow)

  - _make_alert() and _compute_note() added as private instance methods

  - _compute_note() formats cross-session breach notes (e.g. 'Broke pre-market high of $15.00')

  - WidgetDataCacheKeys: DAILY_RANGE_HOD_ALERT, DAILY_RANGE_LOD_ALERT added

  - WidgetDataCacheTTL: DAILY_RANGE_ALERT = EIGHT_HOURS added

  - 29 new tests; 58/58 passing

  Co-authored-by: Tom Pounders <git@oldschool.engineer>

  * test(DailyRangeAnalyzer): add missing _compute_note branch tests (refs #106)

  B1: after_hours LOD fallback — no regular_session_low, pre_market_low present

  B2: regular LOD no-breach — price above pre_market_low returns empty string

  60/60 passing.

  Co-authored-by: Tom Pounders <git@oldschool.engineer>

  * refactor(DailyRangeAnalyzer): replace _compute_note branching with data-driven constants (refs #106)

  Three module-level constants replace nested if/elif branching:

  - _NOTE_TEMPLATES: key → format string

  - _NOTE_CHECKS: (session, direction) → ordered list of keys to evaluate

  - _BREACH_CONDITIONS: key → (attr_name, condition_fn)

  _compute_note() is now a 4-line algorithm loop. Adding a new breach type

  requires only extending the constants — no changes to the method body.

  Each constant is documented to guide future maintainers.

  60/60 passing.

  Co-authored-by: Tom Pounders <git@oldschool.engineer>

  * test(DailyRangeAnalyzer): cover regular session None prior value branches (refs #106)

  B1: (regular, high) with pre_market_high = None → ''

  B2: (regular, low) with pre_market_low = None → ''

  62/62 passing.

  Co-authored-by: Tom Pounders <git@oldschool.engineer>

- `51c172c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/51c172c>`_ chore(deps): update sphinx requirement from >=3.2.1 to >=9.1.0 (#105)

  Updates the requirements on [sphinx](https://github.com/sphinx-doc/sphinx) to permit the latest version.

  - [Release notes](https://github.com/sphinx-doc/sphinx/releases)

  - [Changelog](https://github.com/sphinx-doc/sphinx/blob/master/CHANGES.rst)

  - [Commits](https://github.com/sphinx-doc/sphinx/compare/v3.2.1...v9.1.0)

  ---

  updated-dependencies:

  - dependency-name: sphinx

  dependency-version: 9.1.0

  dependency-type: direct:production

  ...


Version 0.4.13 (2026-04-17)
===========================

- `cc98e66 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/cc98e66>`_ Version 0.4.13 (2026-04-17)
- `7686ddc <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7686ddc>`_ feat(MarketDataScanner): add OpenTelemetry tracing to all methods (refs #103) (#104)

Version 0.4.12 (2026-04-15)
===========================

- `72849d0 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/72849d0>`_ Version 0.4.12 (2026-04-15)
- `33d171c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/33d171c>`_ fix(DailyRangeAnalyzer): reset HOD/LOD using 4AM ET Lua pattern (mirrors LeaderboardAnalyzer) (#101)

  Root cause (confirmed via production logs 2026-04-15):

  REST client failures during the overnight window leave _last_session as

  'after_hours'. The None→pre_market session transition never fires, so

  yesterday's HOD/LOD persist all day. Side-effect: LOD shown in regular

  session H/L is yesterday's LOD because it was lower than today's.

  Fix: adopt the same 4AM ET Lua atomic pattern used by LeaderboardAnalyzer.

  Anchor to today's 4AM ET timestamp (stable throughout the day). Lua script

  atomically compares stored vs current — only one replica resets; no session-

  transition logic; not subject to REST client availability.

  698/698 tests passing.


Version 0.4.11 (2026-04-14)
===========================

- `69a869c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/69a869c>`_ Version 0.4.11 (2026-04-14)
- `da069b0 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/da069b0>`_ fix(DailyRangeAnalyzer): scope rehydrate() to sessions elapsed today (#100)

  rehydrate() was restoring all six HOD/LOD fields unconditionally, which

  caused yesterday's regular and after-hours values to persist into the

  following day until overwritten by new ticks.

  Fix: determine the current session before scanning and only restore

  fields from sessions that have already elapsed today:

  pre_market   -> pre-market fields only

  regular      -> pre-market + regular-session fields

  after_hours  -> all six fields (correct)

  None (closed)-> skip rehydration entirely; cannot determine which

  trading day the cached data belongs to

  Also replaces the inline closure (_restore) with a direct loop over

  the session-scoped field list.

  3 new tests:

  - pre_market: only pre-market fields restored; reg and AH dicts empty

  - regular:    pre-market + regular fields restored; AH dict empty

  - closed:     scan never called; all dicts remain empty

  Updated existing tests to set explicit market status where session

  matters, and corrected the _last_session seeding integration test

  to reflect pre-market-only rehydration.

  refs #95


Version 0.4.10 (2026-04-14)
===========================

- `df4c705 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/df4c705>`_ Version 0.4.10 (2026-04-14)
- `ff590cb <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ff590cb>`_ fix(DailyRangeAnalyzer): skip non-dict Redis values during rehydrate() (#98)

  daily_range:day_boundary and daily_range:market_open_reset:* keys share

  the daily_range:* prefix. json.loads on their values returns str/int, not

  dict, causing AttributeError: 'int' object has no attribute 'get' on the

  first payload.get('symbol') call.

  Add isinstance(payload, dict) guard to skip control keys silently.

  refs #95


Version 0.4.9 (2026-04-13)
==========================

- `4041e05 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/4041e05>`_ Version 0.4.9 (2026-04-13)
- `bf6f029 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/bf6f029>`_ fix(DailyRangeAnalyzer): implement rehydrate() to restore session H/L from Redis (#96)

  * fix(DailyRangeAnalyzer): implement rehydrate() to restore session H/L from Redis

  On every restart, the six in-memory HOD/LOD dicts were wiped and the

  analyzer started tracking from zero — losing all pre-market, regular,

  and after-hours session data accumulated earlier in the trading day.

  Fix: override rehydrate() to scan all daily_range:* keys in Redis and

  restore per-symbol H/L values into the six session dicts before

  processing begins. The existing day-boundary reset at 4AM ET and

  market-open reset at 9:30AM ET handle clearing stale data naturally.

  Six new tests:

  - restore all six session fields from Redis

  - skip null session values (field not yet observed)

  - skip keys with missing Redis values (expired/deleted)

  - handle empty scan result (first startup of the day)

  - paginate through multiple SCAN batches

  - rehydrated highs preserved correctly on subsequent analyze_data() calls

  closes #95

  * style: move json import to module level

  * fix(DailyRangeAnalyzer): preserve pre-market H/L; drive resets from session transitions

  Two issues addressed:

  1. Pre-market H/L was cleared at 9:30 AM by _check_market_open_reset().

  Remove that method entirely. Pre-market H/L is only written during the

  pre_market session (gated by _get_session()), so it is naturally frozen

  at regular session open and remains visible in published payloads through

  the rest of the trading day and after-hours.

  2. Day boundary reset was driven by wall-clock time (hour < 4 guard).

  Replace with session-transition detection: reset fires on the observed

  transition from None (closed) -> pre_market. This correctly handles

  exchange holidays, early closes, and any schedule variation Massive's

  Market Status API reflects. A Redis SET NX guard (per calendar date)

  prevents duplicate resets across restarts and replicas.

  _last_session tracks the previous tick's session for transition detection.

  Tests updated: remove the four wall-clock / _check_market_open_reset tests;

  add six new tests covering session-transition-driven resets, Redis guard,

  pre-market H/L visible during regular session, and pre-market + regular H/L

  visible during after-hours.

  refs #95

  * fix(DailyRangeAnalyzer): seed _last_session from rehydrate() to prevent post-restart wipe

  After rehydrate() completed, _last_session was None. On the first

  analyze_data() call, _check_day_boundary() would see prev=None,

  session=pre_market, satisfy the transition condition, hit the Redis

  guard, and clear all six dicts — wiping everything just rehydrated.

  Fix: call _get_session() at the end of rehydrate() and store the

  result in _last_session so the first tick sees the correct previous

  state.

  Integration test updated: removes the manual sut._last_session='regular'

  workaround; now tests the actual dangerous scenario (market in pre_market

  at time of rehydrate) and asserts _last_session is seeded correctly plus

  rehydrated data survives the subsequent analyze_data() call.

  refs #95

  * docs(DailyRangeAnalyzer): fix stale rehydrate() docstring

  Remove reference to _check_market_open_reset() which no longer exists.

  Describe current behavior: _check_day_boundary() clears on

  None→pre_market transition; pre-market H/L is frozen at market open.

  refs #95


Version 0.4.8 (2026-04-10)
==========================

- `b23280c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/b23280c>`_ Version 0.4.8 (2026-04-10)
- `326ba42 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/326ba42>`_ chore: relax Python floor from 3.14 to 3.12 (#94)

  kuhl-haus-mdp-app runs on Python 3.12 (ubuntu system python) and needs

  to take a dependency on kuhl-haus-mdp. The 3.14 floor was aspirational

  (free-threaded GIL) but not practically useful before 3.15+.


Version 0.4.7 (2026-04-10)
==========================

- `b33021f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/b33021f>`_ Version 0.4.7 (2026-04-10)
- `8a12760 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/8a12760>`_ chore: remove EnhancedQuoteAnalyzer and deprecated ENHANCED_QUOTE enum members (#93)

  EnhancedQuoteAnalyzer is superseded by DailyRangeAnalyzer. The REST

  enrichment calls it contained don't belong in an async stream processor

  and were the root cause of the MDS instability (blocking I/O, pagination

  bugs, empty cache poisoning, wrong decode calls).

  Removed:

  - src/kuhl_haus/mdp/analyzers/enhanced_quote_analyzer.py

  - tests/analyzers/test_enhanced_quote_analyzer.py

  - WidgetDataCacheKeys.ENHANCED_QUOTE (deprecated since v0.4.5)

  - WidgetDataCacheTTL.ENHANCED_QUOTE (deprecated since v0.4.5)

  686 tests passing.


Version 0.4.6 (2026-04-10)
==========================

- `694a362 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/694a362>`_ Version 0.4.6 (2026-04-10)
- `faa386f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/faa386f>`_ fix: use str comparison instead of .decode() for Redis get() result (refs #91) (#92)

  redis.asyncio returns str from get(), not bytes. Calling .decode() raises

  AttributeError: 'str' object has no attribute 'decode'.

  Fix _check_day_boundary to compare existing == today directly.

  Update test fixture to reflect actual redis.asyncio return type.


Version 0.4.5 (2026-04-10)
==========================

- `18bc9c4 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/18bc9c4>`_ Version 0.4.5 (2026-04-10)
- `f06879f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/f06879f>`_ feat: add DailyRangeAnalyzer — pure HOD/LOD tracker, no REST calls (#91)

  Replaces the REST-call-heavy EnhancedQuoteAnalyzer with a focused

  DailyRangeAnalyzer that does exactly one thing: track session highs

  and lows from the quote:* feed.

  - Subscribes to quote:* feed

  - Tracks pre-market / regular / after-hours HOD/LOD in process memory

  - Publishes to daily_range:{symbol} in WDC

  - No REST API calls — no run_in_executor, no functools.partial, no enrichment

  - Day boundary reset at 4AM ET, market open reset at 9:30AM ET

  - Market status fetched via run_in_executor (one lightweight call, 60s cache)

  New enum members:

  - WidgetDataCacheKeys.DAILY_RANGE = 'daily_range'

  - WidgetDataCacheTTL.DAILY_RANGE = FOUR_DAYS

  Deprecated (but not removed yet):

  - WidgetDataCacheKeys.ENHANCED_QUOTE

  - WidgetDataCacheTTL.ENHANCED_QUOTE

  19 tests. EnhancedQuoteAnalyzer and its tests remain untouched for now.


Version 0.4.4 (2026-04-10)
==========================

- `a3fdca8 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a3fdca8>`_ Version 0.4.4 (2026-04-10)
- `30012b9 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/30012b9>`_ fix: do not memory-cache empty API responses in enrichment lookups (refs #85) (#90)

  When get_ticker_details() or list_splits() returns no results (empty

  response, not an error), the code was writing {} / [] to the in-memory

  cache permanently. This blocked all future retries because the memory

  cache is checked first — the symbol would never reach Redis or the API

  again.

  Fix: apply the same if data: guard to the write path that already existed

  on the Redis read path. On empty API response, write with _ENRICHMENT_RETRY_TTL

  (60s) to Redis and skip memory entirely, consistent with the error path.

  Affected methods: _get_overview, _get_splits (short interest/volume

  are disabled so not changed, but have the same latent bug).

  Add two regression tests covering the empty-API-response path.

- `a7f3fda <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a7f3fda>`_ Disable splits enrichment (temporary)

  Temporarily disable fetching/including split data due to ongoing issue #85. Commented out the call to _get_splits and set payload["splits"] to an empty list in EnhancedQuoteAnalyzer, and updated tests to expect an empty splits array and commented related assertions. Add TODOs linking the issue so this can be reverted once fixed.

  ref: https://github.com/kuhl-haus/kuhl-haus-mdp/issues/85


Version 0.4.3 (2026-04-10)
==========================

- `4f2d57b <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/4f2d57b>`_ Version 0.4.3 (2026-04-10)
- `3c1788c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/3c1788c>`_ Disabling short data in enhanced quote

  This is a temporary mitigation to stabilize the MDS/EnhancedQuoteAnalyzer

  ref: https://github.com/kuhl-haus/kuhl-haus-mdp/issues/85

- `fb43891 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/fb43891>`_ fix: use next()/islice() instead of list() to prevent SDK auto-pagination (refs #85) (#89)

  Also use asyncio.get_running_loop() instead of asyncio.get_event_loop() —

  get_event_loop() is deprecated in Python 3.10+ and raises in strict asyncio

  mode (Python 3.14/pytest-asyncio strict). get_running_loop() is the correct

  call inside a running async context.

  Pagination fix:

  - list_short_interest: next(iterator, None) + sort='settlement_date.desc'

  - list_short_volume: next(iterator, None) + sort='date.desc'

  - list_splits: itertools.islice(iterator, 10), no next_url follow

- `e657540 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/e657540>`_ fix: run all blocking REST calls in executor to prevent event loop blockage (#88)

  * test: add failing tests — REST calls must use run_in_executor (refs #85)

  Synchronous REST calls (get_market_status, get_ticker_details,

  list_short_interest, list_short_volume, list_splits) were being called

  directly in the async event loop, blocking all other coroutines including

  the health check endpoint. These tests prove the fix is required.

  * fix: run all blocking REST calls in executor to prevent event loop blockage (refs #85)

  All five synchronous Massive REST calls now use run_in_executor:

  - get_market_status() in _get_market_status

  - get_ticker_details() in _get_overview

  - list_short_interest() in _get_short_interest

  - list_short_volume() in _get_short_volume

  - list_splits() in _get_splits

  Calling blocking I/O directly in an async function blocks the entire event

  loop, starving all other coroutines including the FastAPI health check

  endpoint. Using run_in_executor offloads the HTTP call to a thread pool

  worker, keeping the event loop free.


Version 0.4.2 (2026-04-10)
==========================

- `7abb9ba <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7abb9ba>`_ Version 0.4.2 (2026-04-10)
- `63e342f <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/63e342f>`_ fix: do not trap Redis empty sentinel in memory cache (#87)

  * test: add failing tests for Redis empty sentinel memory trap (refs #85)

  4 failing tests proving the real bug: when Redis contains an empty sentinel

  {} (written on API failure), the Redis hit path unconditionally populates the

  in-memory cache with {}, permanently blocking future API retries even after

  the 60s sentinel TTL expires.

  Fix required: only populate memory cache when cached value is non-empty.

  * fix: do not trap Redis empty sentinel in memory cache (refs #85)

  The real bug: when Redis hit returns an empty sentinel {} (written on API

  failure), the code unconditionally did:

  self._overview_cache[symbol] = {}

  This trapped the empty result in memory permanently — after the 60s Redis

  TTL expired, the memory hit prevented any API retry.

  Fix: add 'if data:' guard on all four Redis hit paths. Empty sentinels are

  served from Redis during the 60s retry window but never stored in memory.

  After TTL expiry, memory miss → Redis miss → API retry → real data stored

  in both caches on success.

- `46f899c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/46f899c>`_ fix: self-healing enrichment cache — short retry TTL on API failure (#86)

  * test: add failing tests for enrichment cache poison fix (refs #85)

  8 failing tests proving the bug:

  - API failure caches empty result with full TTL (poisoning cache)

  - API failure populates in-memory cache (blocks retries)

  - None rest_client behaves identically to API failure

  Expected behavior: short retry TTL (≤120s) on failure, no memory cache population.

  * fix: use short retry TTL on enrichment API failure, no memory cache population (refs #85)

  Adds _ENRICHMENT_RETRY_TTL = 60s. On API failure in all four enrichment

  methods (_get_overview, _get_short_interest, _get_short_volume, _get_splits):

  - Write empty result to Redis with 60s TTL (not full TTL)

  - Do NOT populate in-memory cache

  This ensures the pod self-heals within 60 seconds after API key/connectivity

  is restored, without requiring manual cache flushing or pod restart.


Version 0.4.1 (2026-04-09)
==========================

- `f3680b4 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/f3680b4>`_ Version 0.4.1 (2026-04-09)
- `6b9388c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/6b9388c>`_ feat: EnhancedQuoteAnalyzer — session HOD/LOD tracking + enrichment via MDS (#83)

  * test: add failing tests for EnhancedQuoteAnalyzer (refs #82)

  - Add ENHANCED_QUOTE to WidgetDataCacheKeys and WidgetDataCacheTTL enums

  - Write comprehensive tests for session HOD/LOD tracking (pre-market,

  regular, after-hours, outside windows), boundary resets (4 AM ET day

  boundary and 9:30 AM ET market open), and three-tier enrichment cache

  (memory → Redis → API) for overview, short interest, short volume, and

  splits data

  - Tests cover full payload construction, None-safety, and missing symbol

  guard

  * feat: implement EnhancedQuoteAnalyzer (refs #82)

  Adds EnhancedQuoteAnalyzer with:

  - Session HOD/LOD tracking for pre-market (04:00–09:30 ET), regular

  (09:30–16:00 ET), and after-hours (16:00–20:00 ET) using in-memory

  dicts keyed by symbol; millisecond start_timestamp converted to ET

  - Day boundary reset at 4 AM ET via Lua atomic check-and-set on

  enhanced_quote:day_boundary; clears all six session dicts

  - Market open reset at 9:30 AM ET via SET NX; clears only pre-market

  dicts so regular-session tracking starts fresh

  - Three-tier enrichment cache (memory → Redis WDC → REST API) for

  ticker overview (30-day TTL), short interest (14-day), short volume

  (24h), and splits (24h)

  - Full payload: all raw quote fields plus session H/L plus enrichment

  fields; published to enhanced_quote:{symbol} with 7-day TTL

  - Fix test: use high/low values that preserve pre-populated HOD/LOD

  when the incoming event does not exceed existing extremes

  * fix: replace time-of-day session detection with market_status API call (refs #82)

  * docs: fix stale session-window comments in EnhancedQuoteAnalyzer (refs #82)

  - Remove time-window list from module docstring (session now uses market_status API)

  - Add comment in _check_market_open_reset explaining why time-of-day is intentional

  for the reset trigger (not session detection)

- `cf3db99 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/cf3db99>`_ ci: enforce 98% minimum coverage in publish-to-pypi workflow (#81)

  Adds --cov-fail-under=98 to the pytest invocation. Build will fail

  if coverage drops below 98% before a release tag can be published.

- `40c3e78 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/40c3e78>`_ Rename MDL to Massive Data Listener

  Update docs/architecture.rst to replace 'Market Data Listener (MDL)' with 'Massive Data Listener (MDL)' in two places to reflect the Massive.com provider naming. Documentation-only change; no code behavior affected.

- `e701794 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/e701794>`_ docs: fix stale MDS (Market Data Source) reference in MDL section (#79)

  MDS now refers exclusively to Market Data Scanner. The old usage in the

  MDL description referred to a legacy internal term 'Market Data Source'

  which was never adopted. Clarified that MDL implementations are

  provider-specific Listener classes.

- `fbbf2bb <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/fbbf2bb>`_ docs: add MDS component + WDC section; update enum refs for v0.4.0 (#78)

  * docs: add MDS component + WDC section; update enum refs for v0.4.0

  - Add Market Data Scanner (MDS) to Components Summary and Component Descriptions

  - Brief description in summary; full description with code libraries

  - MarketDataScanner, FinlightDataAnalyzer, AnalyzerOptions, WidgetDataCacheKeys, WidgetDataCacheTTL

  - Add Widget Data Cache (WDC) to Components Summary and Component Descriptions

  - WidgetDataCacheKeys and WidgetDataCacheTTL as primary enums

  - Update MDC description: 'internal' store, separate Redis instance from WDC

  - MarketDataPubSubKeys: note kept for backward compat; prefer WidgetDataCacheKeys for new work

  - Remove MarketDataScanner from MDP code libraries (it belongs to MDS)

  - Add WidgetDataCacheKeys to WDS code libraries

  - Update Deployment Model to include MDS and WDC in data plane list

  * feat: deprecate MarketDataPubSubKeys; update MarketDataCacheKeys docstring

  MarketDataPubSubKeys:

  - Module-level warnings.warn(DeprecationWarning) fires on import — surfaces

  in IDEs (PyCharm, VS Code) and test output

  - Added '.. deprecated::' RST directive to module and class docstrings for

  Sphinx rendering and IDE tooltip display

  - Replacement: WidgetDataCacheKeys

  MarketDataCacheKeys:

  - Updated module and class docstrings to reference WidgetDataCacheKeys as

  the home of WDC-facing keys (no deprecation — internal MDC keys remain valid)

  - Removed stale reference to MarketDataPubSubKeys in the module docstring

  * feat: deprecate WDC-facing members of MarketDataCacheTTL

  Deprecated as of v0.4.0 (moved to WidgetDataCacheTTL):

  QUOTE, TOP_TRADES_WIDGET_CACHE_TTL, TOP_TRADES_ALL_SYMBOLS_CACHE_TTL,

  TOP_STOCKS_SCANNER, TOP_VOLUME_SCANNER, TOP_GAINERS_SCANNER,

  TOP_GAPPERS_SCANNER, NEWS_FEED_LATEST, NEWS_TICKER

  - '.. deprecated::' RST directive in class docstring lists all deprecated members

  - Inline '@deprecated' comments on each deprecated member for IDE tooltip

  - Module __getattr__ + warnings.warn(DeprecationWarning) fires on member access

  - Module docstring updated to list all deprecated members with replacements

  - Non-WDC members (raw data, ticker caches, leaderboards, TOP_TRADES_TRADE_TTL)

  are not deprecated

  * feat: mark all unused enum members as deprecated (v0.4.0 dead code pass)

  Usage audit across src/ and tests/ identified the following unused members.

  All marked with @deprecated inline comments and .. deprecated:: docstring

  directives for IDE tooltip + Sphinx rendering.

  MarketDataCacheKeys (unused, no replacement):

  TOP_TRADES_WIDGET_CACHE_KEY, TOP_TRADES_ALL_SYMBOLS_CACHE_KEY,

  DAILY_AGGREGATES, TOP_TRADES_SCANNER, TOP_GAINERS_SCANNER,

  TOP_GAPPERS_SCANNER, TOP_STOCKS_SCANNER, TOP_VOLUME_SCANNER

  MarketDataCacheTTL (unused dead code, no active callers):

  NEGATIVE_CACHE_THROTTLE, LEADERBOARD_TOP_VOLUME,

  LEADERBOARD_TOP_GAPPERS, LEADERBOARD_TOP_GAINERS

  (WDC entries already marked in previous commit)

  WidgetDataCacheKeys (unused, no active callers):

  TOP_10_LISTS_SCANNER, TOP_TRADES_SCANNER_ONE_HOUR,

  TOP_TRADES_SCANNER_FIVE_MINUTES, TOP_TRADES_SCANNER_ONE_MINUTE,

  TOP_TRADES_SCANNER

  WidgetDataCacheTTL (unused, no active callers):

  TOP_TRADES_WIDGET_CACHE_TTL, TOP_TRADES_ALL_SYMBOLS_CACHE_TTL

  Not deprecated:

  MassiveDataQueue — all members used

  FinlightDataQueue — all members used

  MarketDataScannerNames — used as enum value constructors in other enums

  * fix: revert incorrect deprecations on WidgetDataCacheTTL

  TOP_TRADES_WIDGET_CACHE_TTL and TOP_TRADES_ALL_SYMBOLS_CACHE_TTL are both

  actively used in top_trades_analyzer.py — audit regex had a false negative.

  All WidgetDataCacheTTL members are in use; no deprecations warranted.

  * fix: correct false positives in deprecation pass

  After expanding audit to include tests/ and kuhl-haus-mdp-servers/:

  MarketDataCacheTTL — remove deprecation from:

  QUOTE, TOP_TRADES_WIDGET_CACHE_TTL, TOP_TRADES_ALL_SYMBOLS_CACHE_TTL,

  NEWS_FEED_LATEST, NEWS_TICKER (all have active callers)

  Remaining deprecated: NEGATIVE_CACHE_THROTTLE, LEADERBOARD_TOP_{VOLUME,GAPPERS,GAINERS},

  TOP_{STOCKS,VOLUME,GAINERS,GAPPERS}_SCANNER

  MarketDataPubSubKeys — NEWS_FEED_LATEST and NEWS_TICKER still used in tests;

  noted in docstring, class-level deprecation stands for removal in next release

  * test: migrate deprecated enum refs to WidgetDataCacheKeys/WidgetDataCacheTTL

  test_finlight_data_analyzer.py:

  - Replace MarketDataPubSubKeys with WidgetDataCacheKeys

  - Replace MarketDataCacheTTL.NEWS_FEED_LATEST/NEWS_TICKER with WidgetDataCacheTTL equivalents

  - Remove now-unused MarketDataCacheTTL import

  test_widget_data_cache_enums.py:

  - Replace MarketDataCacheTTL.QUOTE cross-comparison with direct FOUR_DAYS constant assertion

  - Remove now-unused MarketDataCacheTTL import

  71 tests pass.

- `1178397 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/1178397>`_ Refine MarketDataScanner docstrings

  Update module and class docstrings to better reflect the component's role. The text now states the scanner processes post-processed/enriched market data (not raw feeds), lists example analyzer tasks (event correlation, alert generation, trend analysis, pattern recognition), removes the single-analyzer/raw-data wording, and clarifies that this is a Redis-only processor (contrasting RabbitMQ-fed processors). These are wording/clarity changes only.

- `eb86190 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/eb86190>`_ Adding WDC and MDS to the C4 diagram (#77)

  The WDC component is described in the GitHub issue in kuhl-haus-project-roadmap.

  https://github.com/kuhl-haus/kuhl-haus-project-roadmap/issues/2

  When refactoring for this change, the MarketDataScanner was updated to conform with the Analyzer/AnalyzerOptions pattern.  It is not currently in-use but, it will be in Wave-2.

- `a732e25 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a732e25>`_ docs(architecture): add Widget Data Cache (WDC) to C4 diagram (#76)

  Splits the single Redis node into MDC and WDC:

  - MDC (db 0): internal analyzer state — leaderboards, snapshots,

  float, avg volume, ticker caches

  - WDC (db 1): client-facing results — scanner feeds, quote feed,

  news feeds, top trades; pub/sub to WDS

  Processors write analyzer results to WDC (not MDC).

  WDS subscribes to WDC pub/sub (not MDC).

  Removes CacheClient from WDS — WDS reads directly from WDC.

- `bf7bffd <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/bf7bffd>`_ docs: update configuration.rst for MDC_REDIS_URL / WDC_REDIS_URL split (#75)

  Replaces REDIS_URL with purpose-specific env vars across all server docs:

  - FDP, MDP, LBA: MDC_REDIS_URL (AnalyzerOptions) + WDC_REDIS_URL (Processor)

  - WDS: WDC_REDIS_URL only (reads widget results)

  - MDL: Redis removed entirely (was POC leftover, never used)

  refs #74


Version 0.4.0 (2026-04-07)
==========================

- `7a6d01c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7a6d01c>`_ Version 0.4.0 (2026-04-07)

  Breaking changes - please read the change log for details.

- `ac7c24c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/ac7c24c>`_ feat: introduce WidgetDataCacheKeys and WidgetDataCacheTTL enums (WDC/MDC enum split) (#73)

  * test(enums): failing tests for WidgetDataCacheKeys and WidgetDataCacheTTL

  19 tests that FAIL against the current implementation:

  - WidgetDataCacheKeys enum does not exist yet

  - WidgetDataCacheTTL enum does not exist yet

  - All analyzer files still import MarketDataPubSubKeys, not WidgetDataCacheKeys

  refs #70

  * feat: introduce WidgetDataCacheKeys and WidgetDataCacheTTL enums

  New enums:

  - WidgetDataCacheKeys: all WDC-facing keys (replaces MarketDataPubSubKeys

  + WDC entries from MarketDataCacheKeys)

  - WidgetDataCacheTTL: all WDC-facing TTLs (split from MarketDataCacheTTL)

  MarketDataPubSubKeys kept for backward compat (external consumers).

  MDC entries remain in MarketDataCacheKeys / MarketDataCacheTTL.

  Updated analyzers:

  - LeaderboardAnalyzer: WidgetDataCacheKeys/TTL for QUOTE + scanner results

  - FinlightDataAnalyzer: WidgetDataCacheKeys/TTL for news feeds

  - TopStocksAnalyzer: WidgetDataCacheKeys/TTL for scanner results

  - TopTradesAnalyzer: WidgetDataCacheKeys/TTL for widget cache keys/TTLs

  (retains MarketDataCacheKeys/TTL for internal MDC keys)

  All 19 failing tests now pass. 667/667 suite green.

  refs #70

- `fe71685 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/fe71685>`_ feat(MarketDataScanner): accept AnalyzerOptions as constructor param (WDC/MDC split) (#72)

  * test(MarketDataScanner): failing tests for AnalyzerOptions constructor param

  Tests that FAIL against the current implementation:

  - test_mds_init_with_analyzer_options_expect_used

  - test_mds_init_with_analyzer_options_expect_no_massive_api_key_param

  - test_mds_init_with_analyzer_options_expect_correct_param_order

  - test_mds_connect_uses_analyzer_options_for_rest_client

  refs #69

  * feat(MarketDataScanner): accept AnalyzerOptions as constructor param; remove self.mdc

  - Removes massive_api_key as a top-level constructor param

  - Removes self.mdc (MarketDataCache) and RESTClient — only used for incorrect

  cache=self.mdc analyzer instantiation pattern

  - Analyzer now instantiated with options=self.analyzer_options (correct pattern)

  - redis_url is now the WDC connection for result storage

  - connect() simplified: only establishes WDC Redis connection

  New signature: __init__(redis_url, subscriptions, analyzer_class, analyzer_options)

  All 4 failing tests now pass. 648/648 suite green.

  refs #69

- `dee82a3 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/dee82a3>`_ feat(MassiveDataProcessor): accept AnalyzerOptions as constructor param (WDC/MDC split) (#71)

  * test(MassiveDataProcessor): failing tests for AnalyzerOptions constructor param

  Tests that FAIL against the current implementation:

  - test_mdp_init_with_analyzer_options_expect_used

  - test_mdp_init_with_analyzer_options_expect_no_massive_api_key_param

  - test_mdp_init_with_analyzer_options_expect_analyzer_class_before_options

  - test_mdp_start_uses_analyzer_options_for_analyzer_instantiation

  refs #68

  * feat(MassiveDataProcessor): accept AnalyzerOptions as constructor param

  Removes massive_api_key as a top-level constructor param. Callers must

  now pass a pre-built AnalyzerOptions instance (MDC connection + api key).

  The redis_url param remains but now represents the WDC connection for

  result storage.

  New signature: __init__(rabbitmq_url, queue_name, redis_url,

  analyzer_class, analyzer_options, ...)

  Matches the pattern established by FinlightDataProcessor.

  All 4 failing tests now pass. 644/644 suite green.

  refs #68


Version 0.3.15 (2026-04-07)
===========================

- `9943d54 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/9943d54>`_ Version 0.3.15 (2026-04-07)
- `a9b19a6 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/a9b19a6>`_ fix(MDL): add is_market_open() + exponential backoff for transient DNS failures (#67)

  * test(MDL): failing tests for is_market_open(), exponential backoff, and max_reconnects retry limit

  Tests that FAIL against the current implementation:

  - test_mdl_is_market_open_with_open_market_expect_true

  - test_mdl_is_market_open_with_closed_market_expect_false

  - test_mdl_is_market_open_with_none_market_expect_false

  - test_mdl_is_market_open_with_dns_error_expect_false

  - test_mdl_async_task_with_transient_dns_error_expect_retry_not_fatal

  - test_mdl_async_task_with_max_retries_exhausted_expect_fatal

  (asserts get_market_status called exactly max_reconnects times before giving up)

  Reuses max_reconnects as the retry limit — no new constructor param.

  refs #66

  * fix(MDL): add market_is_open() with exponential backoff and max_reconnects retry limit

  Extracts get_market_status() call into market_is_open() -> bool with:

  - Exponential backoff: 1s → 2 → 4 → 8 → 16 → 32 → 60s cap

  - Retries up to max_reconnects times (reuses existing param, no API change)

  - Re-raises on exhaustion so the outer except fires: healthy=False,

  stop() called, k8s liveness probe kills the pod

  async_task reconnect loop now calls await market_is_open() — flat,

  readable, no nesting.

  Transient DNS failures (blip < max_reconnects) are retried silently.

  Persistent failures exhaust retries and fail fast via the fatal handler.

  All 6 failing tests now pass. 640/640 suite green.

  refs #66

- `91dee10 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/91dee10>`_ Adjust connection healthy flag handling

  Do not mark connection as unhealthy when performing a reconnection attempt; only set connection_status['healthy'] = False on unhandled exceptions. Move the healthy flag update into the exception handler and update tests accordingly (expect healthy True during reconnection attempts, and healthy False on stop/fatal error cases).

- `15009d7 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/15009d7>`_ docs: fix NEWS_FEED_CACHE_TTL and NEWS_TICKER_CACHE_TTL default values (#65)

  NEWS_FEED_LATEST = TWO_DAYS = 172800 (not 86400)

  NEWS_TICKER = SEVEN_DAYS = 604800 (not 259200)

  Tom increased both TTLs today; documentation was using stale values.


Version 0.3.14 (2026-04-06)
===========================

- `4a7c6d4 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/4a7c6d4>`_ Version 0.3.14 (2026-04-06)
- `b840b29 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/b840b29>`_ feat(FinlightDataAnalyzer): configurable cache TTLs via kwargs (#64)

  * test(FinlightDataAnalyzer): failing tests for configurable cache TTLs

  Tests that FAIL against the current implementation:

  - test_fda_init_with_no_kwargs_expect_ttl_enum_defaults

  - test_fda_init_with_ttl_kwargs_expect_custom_ttls

  - test_fda_analyze_data_with_custom_feed_ttl_expect_override_used

  - test_fda_analyze_data_with_custom_ticker_ttl_expect_override_used

  - test_fda_analyze_data_with_custom_ticker_ttl_expect_raw_ticker_override_used

  refs kuhl-haus/kuhl-haus-project-roadmap#1

  * feat(FinlightDataAnalyzer): configurable cache TTLs via AnalyzerOptions.kwargs

  Add news_feed_cache_ttl and news_ticker_cache_ttl attributes following

  the same kwargs pattern as news_feed_list_max / news_ticker_list_max.

  Both default to MarketDataCacheTTL enum values (unchanged behavior):

  - news_feed_cache_ttl: MarketDataCacheTTL.NEWS_FEED_LATEST (1 day)

  - news_ticker_cache_ttl: MarketDataCacheTTL.NEWS_TICKER (3 days)

  docs/configuration.rst updated with NEWS_FEED_CACHE_TTL and

  NEWS_TICKER_CACHE_TTL env var entries for the FDP server.

  All 5 failing tests now pass. 634/634 suite green.

  refs kuhl-haus/kuhl-haus-project-roadmap#1

- `33250e0 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/33250e0>`_ Increase client-facing cache TTLs
- `9e640ec <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/9e640ec>`_ Increase news cache TTLs to 2 and 7 days

  Extend cache durations for news-related entries: change NEWS_FEED_LATEST from ONE_DAY to TWO_DAYS and NEWS_TICKER from THREE_DAYS to SEVEN_DAYS.


Version 0.3.13 (2026-04-06)
===========================

- `7bb5d76 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/7bb5d76>`_ Version 0.3.13 (2026-04-06)
- `4318781 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/4318781>`_ perf(LeaderboardAnalyzer): eliminate redundant hgetall for quote publication (#63)

  * test(LeaderboardAnalyzer): failing tests for issue #62 — eliminate redundant hgetall

  Tests that FAIL against the current implementation:

  - test_lba_update_leaderboards_with_valid_event_expect_mapping_returned

  - test_lba_update_leaderboards_with_no_symbol_expect_none_returned

  - test_lba_update_leaderboards_with_pipe_error_expect_none_returned

  - test_lba_analyze_data_with_symbol_expect_no_hgetall

  - test_lba_analyze_data_with_no_mapping_expect_no_quote

  - test_lba_analyze_data_with_publish_and_mapping_expect_no_hgetall

  Two existing tests updated to reflect the new _update_leaderboards contract.

  refs #62

  * perf(LeaderboardAnalyzer): eliminate redundant hgetall for quote publication

  _update_leaderboards now returns Optional[dict] — the mapping it already

  has in memory. analyze_data uses that return value directly to build the

  quote result, eliminating one hgetall round-trip per agg event per symbol.

  Returns None on early exit (no symbol) or pipeline error.

  No behavior change to leaderboard publishing or throttle logic.

  All 6 failing tests now pass. 627/627 suite green.

  refs #62

- `46803c6 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/46803c6>`_ docs(CLAUDE): add bug workflow — test first directive (#61)
- `3e66aeb <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/3e66aeb>`_ Add 'Stock Selection: Why News Matters' link

  Add a new entry to the Additional Resources section in README.rst linking to the 'Stock Selection: Why News Matters' blog post. This exposes a newly published article as a reference for users.

- `4946a23 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/4946a23>`_ Added FDL and FDP to C4 diagram
- `64a53a7 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/64a53a7>`_ docs(configuration): add FDP env vars for Finlight API key and cache limits (#59)

  Documents three new environment variables in the FDP configuration table:

  - FINLIGHT_API_KEY: Finlight API key forwarded to AnalyzerOptions

  - NEWS_FEED_LIST_MAX: override for news feed Redis list size (default 10000)

  - NEWS_TICKER_LIST_MAX: override for per-ticker Redis list size (default 100)


Version 0.3.12 (2026-04-02)
===========================

- `65579da <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/65579da>`_ Version 0.3.12 (2026-04-02)
- `2dd3361 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/2dd3361>`_ feat(FinlightDataAnalyzer): make cache list limits configurable via AnalyzerOptions.kwargs (#58)

  NEWS_FEED_LIST_MAX and NEWS_TICKER_LIST_MAX enum values remain the defaults.

  Both can be overridden at runtime by passing news_feed_list_max and/or

  news_ticker_list_max in AnalyzerOptions.kwargs.

  This allows fdp_server.py to expose these limits as environment variables

  without requiring code changes.

  4 new tests:

  - Default values match enum constants when no kwargs provided

  - Custom limits accepted via kwargs

  - Feed and ticker results use overridden limits when provided

- `c3a0702 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/c3a0702>`_ feat(FinlightDataProcessor): accept AnalyzerOptions as a required parameter (#57)

  Adds required analyzer_options: AnalyzerOptions parameter to

  FinlightDataProcessor.__init__(), positioned after analyzer_class so it

  naturally follows its collaborating class.

  Callers must now explicitly supply an AnalyzerOptions instance, enabling

  them to provide Massive.com and Finlight API keys and/or subclass-specific

  kwargs to the analyzer without modifying the processor.

  Also adds a docstring to __init__ documenting all parameters.

  2 tests updated/added:

  - Explicit AnalyzerOptions instance is used as-is

  - Existing tests updated to pass required parameter

- `07e3f93 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/07e3f93>`_ feat(AnalyzerOptions): add finlight_api_key and kwargs fields (#56)

  finlight_api_key: Optional[str]

  Provides Finlight REST/WebSocket API access to analyzer subclasses,

  symmetric with the existing massive_api_key. Includes new_finlight_client()

  factory method returning a FinlightApi instance when the key is set.

  kwargs: Dict[str, Any] (defaults to empty dict)

  Escape hatch for subclass-specific configuration that does not belong

  in AnalyzerOptions itself. Allows new per-analyzer parameters without

  modifying the base class or breaking existing implementations.

  Tests:

  - Default values for both new fields

  - Constructor with explicit values

  - new_finlight_client() returns FinlightApi when key is set

  - new_finlight_client() returns None when key is absent

  - kwargs default is an empty dict

  - kwargs instances are independent (field(default_factory=dict))


Version 0.3.11 (2026-04-02)
===========================

- `df5e1ba <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/df5e1ba>`_ Version 0.3.11 (2026-04-02)
- `b57edd4 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/b57edd4>`_ feat(LeaderboardAnalyzer): add prev_day open/high/low to symbol metadata (#55)

  Extract snapshot.prev_day.open/high/low and include them in the symbol

  metadata hash alongside the existing prev_day_close/volume/vwap fields.

  Falls back to 0 when snapshot is unavailable (same pattern as existing fields).

  Closes #54

- `312bdf0 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/312bdf0>`_ Update typing and return type of get_cache

  Add Any to typing imports and update WidgetDataService.get_cache return annotation from dict to a union (list[Any] | None | Any) to better reflect the variety of cached payloads returned for initial client snapshots. This clarifies expected types for callers and tooling without changing runtime behavior.


Version 0.3.10 (2026-03-31)
===========================

- `8b6e71c <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/8b6e71c>`_ Version 0.3.10 (2026-03-31)
- `07732f4 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/07732f4>`_ fix(lba): publish quote:{symbol} on every agg, not just on leaderboard publish (#52)

  The quote result was inside the should_publish branch, so only the

  one elected instance (per second, cluster-wide) ever published a quote —

  and only for the ticker that happened to trigger the election. All other

  instances and all other tickers got no pub/sub update, only stale cache.

  Fix: build the quote result unconditionally (every instance, every agg).

  Append it to leaderboard results when should_publish is true; return it

  alone when not. Leaderboard fan-out (top-500) stays throttled. The quote

  channel is per-symbol so there is no fan-out concern.

  Effect: quote:{symbol} now receives ~1 update/sec on every active ticker

  from every LBA instance processing that ticker's agg messages.


Version 0.3.9 (2026-03-31)
==========================

- `2e3a915 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/2e3a915>`_ Version 0.3.9 (2026-03-31)
- `0ba4424 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/0ba4424>`_ fix(wds): snapshot set before iteration; fix exc_info in logger call (#51)

  Two bugs in _handle_pubsub() triggered by concurrent client disconnect:

  Bug 1 — RuntimeError: Set changed size during iteration

  self.subscriptions[feed] is a set. When another coroutine calls

  unsubscribe() while _handle_pubsub is iterating (e.g. the finally

  block in websocket_endpoint), Python raises RuntimeError.

  Fix: iterate list(self.subscriptions[feed]) — a snapshot copy.

  Bug 2 — TypeError: not all arguments converted during string formatting

  self.logger.error(f'...', e) passes the exception as a positional arg.

  The logging module tries to apply %-formatting using e as the argument,

  but the message (already an f-string) has no % tokens.

  Fix: exc_info=True — attaches the traceback correctly.

  Reported in kuhl-haus-mdp-servers#35.


Version 0.3.8 (2026-03-30)
==========================

- `fbce936 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/fbce936>`_ Version 0.3.8 (2026-03-30)
- `07082d2 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/07082d2>`_ feat: per-symbol quote pub/sub feed for Quote widget (refs #49) (#50)

  Adds a real-time per-symbol enriched quote feed to the LeaderboardAnalyzer

  pub/sub output, enabling the upcoming Quote widget to subscribe to a single

  ticker and receive live enriched data (~1/sec throttle).

  ## Changes

  ### MarketDataPubSubKeys

  - New: QUOTE = 'quote'  (used as f'quote:{symbol}')

  ### MarketDataCacheTTL

  - New: QUOTE = THREE_DAYS

  Three-day TTL for graceful degradation — stale data is better than no

  data. Timestamp in the payload lets the client display data freshness.

  ### LeaderboardAnalyzer.analyze_data()

  - Inside the existing should_publish branch, after building leaderboard

  results, reads the already-computed symbol:{symbol}:data hash from Redis

  and appends a MarketDataAnalyzerResult for quote:{symbol}.

  - No additional Massive API calls — reuses data written by _update_leaderboards().

  - Throttled to ~1/sec (same as leaderboard publish).

  ### Tests

  - Updated test_lba_analyze_data_with_publish_expect_results to mock

  redis_client.hgetall and assert the quote result is appended correctly.


Version 0.3.7 (2026-03-28)
==========================

- `03c6bb9 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/03c6bb9>`_ Version 0.3.7 (2026-03-28)
- `8e33f69 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/8e33f69>`_ feat(WidgetDataService): add optional limit param to get_cache (closes #47 step 1) (#48)

  * test(WidgetDataService): add tests for get_cache limit param

  Tests assert limit=N maps to LRANGE 0 N-1, and limit=0 (default)

  fetches all items (LRANGE 0 -1). Tests fail at this commit (red phase).

  * feat(WidgetDataService): add optional limit param to get_cache (closes #47 step 1)

  Add limit: int = 0 to get_cache(). limit=0 (default) fetches all items

  via LRANGE 0 -1 (backwards compatible). limit=N maps to LRANGE 0 N-1,

  bounding the Redis transfer to N items.

- `6b01797 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/6b01797>`_ feat(FinlightDataAnalyzer): increase news cache limits (feed 10k, ticker 100) (#46)

  * feat(FinlightDataAnalyzer): increase news cache limits (feed 10k, ticker 100)

  Increase news:feed:latest from 1,000 to 10,000 articles (~10MB Redis).

  Increase news:ticker:{ticker} from 20 to 100 articles.

  Decouples backend cache depth from frontend display limit.

  * refactor(FinlightDataAnalyzer): introduce FinlightDataCache enum for list max values

  Add FinlightDataCache enum with NEWS_FEED_LIST_MAX (10000) and

  NEWS_TICKER_LIST_MAX (100). Replace hard-coded integers in

  FinlightDataAnalyzer and its tests with enum references so cache

  limits can be changed in one place without touching tests.

  * test: remove numeric suffixes from cache_list_max test names

- `af04ac9 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/af04ac9>`_ refactor(MarketDataCache): replace aiohttp free float with RESTClient (closes #44) (#45)

  * test(MarketDataCache): update free float tests to mock RESTClient

  Replace aiohttp-based free float mocks with rest_client.list_stocks_floats

  mocks using FinancialFloat-like objects. Remove get_http_session and close

  tests (both removed with aiohttp). Remove massive_api_key from fixture and

  init assertion.

  Tests fail at this commit (red phase). Implementation follows.

  * refactor(MarketDataCache): replace aiohttp free float with RESTClient (closes #44)

  Replace experimental aiohttp GET /stocks/vX/float with

  rest_client.list_stocks_floats(ticker=ticker) — the same endpoint now

  exposed via Massive's official Python RESTClient.

  - Remove aiohttp import, get_http_session(), close(), and http_session state

  - Remove massive_api_key constructor parameter (only needed for aiohttp URL)

  - Remove aiohttp from pyproject.toml dependencies

  - Add FinancialFloat import from massive.rest.models.financials

  - Update all MarketDataCache call sites to drop massive_api_key kwarg

  - Exception handling aligned with rest of MDC: errors propagate to caller

- `880c1d8 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/880c1d8>`_ docs: replace MARKET_DATA_LISTENER_AUTO_START_ENABLED with discrete vars (#43)

  MDL: MDL_AUTO_START_ENABLED

  FDL: FDL_AUTO_START_ENABLED


Version 0.3.6 (2026-03-26)
==========================

- `6808423 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/6808423>`_ Version 0.3.6 (2026-03-26)
- `6fc9724 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/6fc9724>`_ fix(WDS): redis type() returns str not bytes (#42)

  get_cache() was comparing key_type against b'list'/b'string' (bytes),

  but redis-py returns plain strings. The condition never matched so

  lrange was never called — cache always appeared empty.

  Fix: decode bytes defensively then compare against plain strings.

  Also correct test mocks to return str (matching actual redis-py

  behavior).


Version 0.3.5 (2026-03-26)
==========================

- `8cad469 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/8cad469>`_ Version 0.3.5 (2026-03-26)
- `aa43cef <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/aa43cef>`_ feat: rolling list cache for news feeds (closes #40) (#41)

  * test: rolling list cache for news feeds (refs #40)

  Tests for:

  - MarketDataAnalyzerResult.cache_list_max field (default None)

  - FinlightDataAnalyzer: feed cache_list_max=1000, ticker cache_list_max=20

  - FinlightDataProcessor: LPUSH+LTRIM+EXPIRE path when cache_list_max set

  - WidgetDataService.get_cache: Redis list type returns parsed list

  * feat: rolling list cache for news feeds (closes #40)

  MarketDataAnalyzerResult:

  - Add cache_list_max: Optional[int] = None field

  FinlightDataAnalyzer:

  - news:feed:latest: cache_list_max=1000

  - news:ticker:{TICKER}: cache_key set + cache_list_max=20

  (previously ticker results had cache_key=None)

  FinlightDataProcessor._cache_result():

  - When cache_list_max set: LPUSH + LTRIM + EXPIRE (if TTL>0)

  - String path (SET/SETEX) unchanged for non-list keys

  WidgetDataService.get_cache():

  - Check Redis key type first (type command)

  - list → LRANGE 0 -1 → return list of parsed dicts

  - string → GET → return parsed dict (unchanged behavior)

  - none/miss → return None (string) or [] (list)


Version 0.3.4 (2026-03-25)
==========================

- `485d745 <https://github.com/kuhl-haus/kuhl-haus-mdp/commit/485d745>`_ Version 0.3.4 (2026-03-25)
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

