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


def get_tracer(name):
    return trace.get_tracer(name, __version__)


def get_meter(name):
    return metrics.get_meter(name, __version__)
