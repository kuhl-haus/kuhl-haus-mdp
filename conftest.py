"""Root conftest.py — ensures kuhl_haus.mdp is resolvable in dev environments.

When another package installed in site-packages claims the ``kuhl_haus``
namespace with a regular ``__init__.py``, Python stops scanning for namespace
sub-packages. Extending ``kuhl_haus.__path__`` here ensures that
``kuhl_haus.mdp`` can always be found from the src layout during local testing.
"""
import os
import sys


def pytest_configure(config):
    src_path = os.path.join(os.path.dirname(__file__), "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # If kuhl_haus is already loaded as a regular package by another
    # distribution, extend its __path__ so kuhl_haus.mdp is still findable.
    try:
        import kuhl_haus  # noqa: F401

        kuhl_haus_src = os.path.join(src_path, "kuhl_haus")
        if (
            hasattr(kuhl_haus, "__path__")
            and kuhl_haus_src not in kuhl_haus.__path__
        ):
            kuhl_haus.__path__.append(kuhl_haus_src)
    except ImportError:
        pass
