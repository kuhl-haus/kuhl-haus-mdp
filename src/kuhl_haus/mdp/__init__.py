"""kuhl_haus.mdp - Market data processing pipeline.

Provides real-time market data analysis, caching, and processing components
built on WebSocket streams from Massive.com. Includes analyzers for stock and
trade data, listener and processor components, and supporting data structures.
"""

from importlib_metadata import PackageNotFoundError, version  # pragma: no cover

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = __name__
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError
