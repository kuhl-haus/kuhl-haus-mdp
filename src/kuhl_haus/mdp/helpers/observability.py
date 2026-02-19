# kuhl_haus/mdp/helpers/observability.py

from opentelemetry import trace
from opentelemetry import metrics
from importlib.metadata import version, PackageNotFoundError

# Get version dynamically
package_name = "kuhl-haus-mdp"
try:
    __version__ = version(package_name)
except PackageNotFoundError:
    __version__ = "0.0.0-dev"  # Fallback for dev/editable installs

tracer = trace.get_tracer(package_name, __version__)
meter = metrics.get_meter(package_name, __version__)


def _resolve_version(pkg_name=None):
    """Resolve the version for a given package name.

    Args:
        pkg_name: Package name to look up. If None, returns
                  the default kuhl-haus-mdp version.

    Returns:
        Version string for the package, or the default
        __version__ if the package is not found.

    Examples:
        >>> _resolve_version()
        '1.2.3'  # current kuhl-haus-mdp version

        >>> _resolve_version("kuhl-haus-mdp-servers")
        '2.0.0'  # version of the specified package
    """
    if not pkg_name:
        return __version__
    try:
        return version(pkg_name)
    except PackageNotFoundError:
        return __version__


def get_tracer(name, pkg_name=None):
    """Get an OpenTelemetry tracer.

    Args:
        name: Tracer name (typically __name__).
        pkg_name: Optional package name to resolve version.
                  Defaults to kuhl-haus-mdp.

    Examples:
        Default usage (resolves kuhl-haus-mdp version)::

            from kuhl_haus.mdp.helpers.observability import (
                get_tracer,
            )
            tracer = get_tracer(__name__)

        Cross-package usage (resolves another package's
        version)::

            tracer = get_tracer(
                __name__,
                pkg_name="kuhl-haus-mdp-servers",
            )
    """
    return trace.get_tracer(name, _resolve_version(pkg_name))


def get_meter(name, pkg_name=None):
    """Get an OpenTelemetry meter.

    Args:
        name: Meter name (typically __name__).
        pkg_name: Optional package name to resolve version.
                  Defaults to kuhl-haus-mdp.

    Examples:
        Default usage (resolves kuhl-haus-mdp version)::

            from kuhl_haus.mdp.helpers.observability import (
                get_meter,
            )
            meter = get_meter(__name__)

        Cross-package usage (resolves another package's
        version)::

            meter = get_meter(
                __name__,
                pkg_name="kuhl-haus-mdp-servers",
            )
    """
    return metrics.get_meter(name, _resolve_version(pkg_name))
