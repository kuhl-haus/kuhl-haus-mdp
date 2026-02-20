=========
Changelog
=========

Version 0.2.20 (2026-02-19)
===========================

- Add/expand docstrings across mdp package
- feat: make observability.py cross-package compatible; rewrite non-conforming tests

Version 0.2.19 (2026-02-19)
===========================

- Add market status handling to MassiveDataListener

Version 0.2.18 (2026-02-18)
===========================

- Re-enable observability: tracing & metrics
- Use instance attributes in connection_status

Version 0.2.17 (2026-02-18)
===========================

- **Performance**: Multi-channel concurrent publishing for higher throughput in MDQ

Version 0.2.16 (2026-02-18)
===========================

- Convert MassiveDataAnalyzer tests to async

Version 0.2.15 (2026-02-18)
===========================

- Add TopTradesAnalyzer for Redis trade stats
- Remove opentelemetry-distro dependency
- MassiveDataAnalyzer: add tracing and metrics
- Rename leaderboard cache keys and enrich result docs
- Add error metrics and improve logging for MDC

Version 0.2.14 (2026-02-17)
===========================

- Revert distributed tracing changes in MDL

Version 0.2.13 (2026-02-13)
===========================

- Reduce log verbosity and remove tracing comments

Version 0.2.12 (2026-02-13)
===========================

- Handle missing avg volume with negative cache

Version 0.2.11 (2026-02-13)
===========================

- Propagate OTEL context to worker processes

Version 0.2.10 (2026-02-12)
===========================

- Add OpenTelemetry observability & metrics

Version 0.2.9 (2026-02-11)
==========================

- Initialize structured logging in MDP

Version 0.2.8 (2026-02-11)
==========================

- Add structured logging and refactor components to use loggers

Version 0.2.7 (2026-02-09)
==========================

- Replace duplicated metric with processing_error

Version 0.2.6 (2026-02-09)
==========================

- Add DataAnalysisException and error handling

Version 0.2.5 (2026-02-09)
==========================

- Normalize falsy leaderboard fields to 0

Version 0.2.4 (2026-02-09)
==========================

- Default avg_volume to 0 and log errors

Version 0.2.3 (2026-02-06)
==========================

- **Bugfix**: Exception on Null result from Analyzer

Version 0.2.2 (2026-02-06)
==========================

- **Breaking Change**: MDP Metrics

Version 0.2.1 (2026-02-06)
==========================

- Try to handle null exception writing to leaderboard

Version 0.2.0 (2026-02-05)
==========================

- **Major Release**: Leaderboard Analyzer

Version 0.1.18 (2026-02-04)
===========================

- Update .readthedocs.yml

Version 0.1.17 (2026-02-04)
===========================

- Update publish-to-pypi.yml
- Upgrade to Python 3.14
- Fix docstrings in utils.py
- Update project description in README.md
- Update Market_Data_Processing_C4.png

Version 0.1.16 (2026-01-14)
===========================

- Update to pre-market reset bugfix
- Removed commented code

Version 0.1.15 (2026-01-13)
===========================

- **Bugfix**: Pre-market reset

Version 0.1.14 (2026-01-09)
===========================

- Return top 500 stocks by volume

Version 0.1.13 (2026-01-09)
===========================

- Delete ticker snapshot on exception
- Fixed docs namespaces

Version 0.1.12 (2026-01-08)
===========================

- Reorganized namespace

Version 0.1.11 (2026-01-08)
===========================

- Delete ticker snapshot from cache on KeyError

Version 0.1.10 (2026-01-06)
===========================

- Remove unnecessary load on MDC Part 2
- Added exception logging in TopStocks
- Remove unnecessary load on MDC
- Easier to maintain cache TTLs

Version 0.1.9 (2026-01-06)
==========================

- **Bugfix**: TopStocks Scanner
- Fixed documentation URL in pyproject

Version 0.1.8 (2026-01-05)
==========================

- Added free float

Version 0.1.7 (2026-01-05)
==========================

- Fixed MarketDataCache bugs

Version 0.1.6 (2026-01-04)
==========================

- Specify Analyzer class in MarketDataScanner ctor
- Added importlib_metadata
- Prefer readthedocs publishing
- Update README.rst
- Added create docs workflow

Version 0.1.5 (2026-01-03)
==========================

- Update publish-to-pypi.yml

Version 0.1.4 (2026-01-03)
==========================

- Market Data Cache implementation
- Add pytest-asyncio to test dependencies
- Moved integ/utils.py to helpers

Version 0.1.3 (2025-12-31)
==========================

- Only build images on non-tagged mainline pushes
- Test publishing on non-tagged mainline pushes
- Refactored TopStocksCacheItem

Version 0.1.2 (2025-12-31)
==========================

- Converted Massive data analyzer from async to sync

Version 0.1.1 (2025-12-30)
==========================

- Test coverage for message SerDe and queue name resolver
- Added components description to readme file

Version 0.1.0 (2025-12-26)
==========================

- Dynamic versioning with setuptools-scm
- Update CodeQL badge on readme
- Add CodeQL analysis workflow configuration

Version 0.0.1 (2025-12-24)
==========================

- Install via pip instead of PDM
- Revert "Hacky work-around for ModuleNotFound error in PDM build."
- Added importlib_metadata to requirements.txt
- Hacky work-around for ModuleNotFound error in PDM build.
- Install test dependencies in workflow
- Initial commit
