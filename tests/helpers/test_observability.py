import importlib
from unittest.mock import patch

import pytest

from kuhl_haus.mdp.helpers import observability


# ── module-level attributes ──────────────────────────────────────────


def test_ob_package_name_expect_correct_value():
    # Arrange / Act
    sut = observability.package_name

    # Assert
    assert sut == "kuhl-haus-mdp"


def test_ob_version_with_installed_pkg_expect_string():
    # Arrange / Act
    sut = observability.__version__

    # Assert
    assert isinstance(sut, str)
    assert len(sut) > 0


def test_ob_version_with_missing_pkg_expect_dev_fallback():
    # Arrange / Act
    with patch(
        "importlib.metadata.version",
        side_effect=observability.PackageNotFoundError(),
    ):
        importlib.reload(observability)
        sut = observability.__version__

    # Assert
    assert sut == "0.0.0-dev"

    # Cleanup — reload to restore real version
    importlib.reload(observability)


def test_ob_module_tracer_expect_tracer_instance():
    # Arrange / Act
    sut = observability.tracer

    # Assert
    assert sut is not None
    assert hasattr(sut, "start_as_current_span")


def test_ob_module_meter_expect_meter_instance():
    # Arrange / Act
    sut = observability.meter

    # Assert
    assert sut is not None
    assert hasattr(sut, "create_counter")


# ── _resolve_version ─────────────────────────────────────────────────


def test_ob_resolve_version_with_none_expect_default():
    # Arrange / Act
    sut = observability._resolve_version(None)

    # Assert
    assert sut == observability.__version__


def test_ob_resolve_version_with_empty_expect_default():
    # Arrange / Act
    sut = observability._resolve_version("")

    # Assert
    assert sut == observability.__version__


def test_ob_resolve_version_with_known_pkg_expect_its_version():
    # Arrange
    with patch(
        "kuhl_haus.mdp.helpers.observability.version",
        return_value="1.2.3",
    ):
        # Act
        sut = observability._resolve_version("some-pkg")

    # Assert
    assert sut == "1.2.3"


def test_ob_resolve_version_with_unknown_pkg_expect_fallback():
    # Arrange
    with patch(
        "kuhl_haus.mdp.helpers.observability.version",
        side_effect=observability.PackageNotFoundError(),
    ):
        # Act
        sut = observability._resolve_version("no-such-pkg")

    # Assert
    assert sut == observability.__version__


# ── get_tracer ───────────────────────────────────────────────────────


def test_ob_get_tracer_with_name_expect_tracer_returned():
    # Arrange
    name = "my.module"

    # Act
    sut = observability.get_tracer(name)

    # Assert
    assert sut is not None
    assert hasattr(sut, "start_as_current_span")


def test_ob_get_tracer_with_name_expect_otel_called():
    # Arrange
    with patch(
        "kuhl_haus.mdp.helpers.observability.trace"
    ) as mock_trace:
        # Act
        sut = observability.get_tracer("test.mod")

    # Assert
    mock_trace.get_tracer.assert_called_once_with(
        "test.mod", observability.__version__,
    )
    assert sut is mock_trace.get_tracer.return_value


def test_ob_get_tracer_with_pkg_name_expect_pkg_version():
    # Arrange
    with patch(
        "kuhl_haus.mdp.helpers.observability.trace"
    ) as mock_trace, patch(
        "kuhl_haus.mdp.helpers.observability.version",
        return_value="9.8.7",
    ):
        # Act
        sut = observability.get_tracer(
            "mod", pkg_name="other-pkg",
        )

    # Assert
    mock_trace.get_tracer.assert_called_once_with(
        "mod", "9.8.7",
    )
    assert sut is mock_trace.get_tracer.return_value


# ── get_meter ────────────────────────────────────────────────────────


def test_ob_get_meter_with_name_expect_meter_returned():
    # Arrange
    name = "my.module"

    # Act
    sut = observability.get_meter(name)

    # Assert
    assert sut is not None
    assert hasattr(sut, "create_counter")


def test_ob_get_meter_with_name_expect_otel_called():
    # Arrange
    with patch(
        "kuhl_haus.mdp.helpers.observability.metrics"
    ) as mock_metrics:
        # Act
        sut = observability.get_meter("test.mod")

    # Assert
    mock_metrics.get_meter.assert_called_once_with(
        "test.mod", observability.__version__,
    )
    assert sut is mock_metrics.get_meter.return_value


def test_ob_get_meter_with_pkg_name_expect_pkg_version():
    # Arrange
    with patch(
        "kuhl_haus.mdp.helpers.observability.metrics"
    ) as mock_metrics, patch(
        "kuhl_haus.mdp.helpers.observability.version",
        return_value="4.5.6",
    ):
        # Act
        sut = observability.get_meter(
            "mod", pkg_name="other-pkg",
        )

    # Assert
    mock_metrics.get_meter.assert_called_once_with(
        "mod", "4.5.6",
    )
    assert sut is mock_metrics.get_meter.return_value


# ── backwards compatibility ──────────────────────────────────────────


def test_ob_get_tracer_with_no_pkg_expect_default_version():
    # Arrange
    with patch(
        "kuhl_haus.mdp.helpers.observability.trace"
    ) as mock_trace:
        # Act
        observability.get_tracer("x")

    # Assert
    mock_trace.get_tracer.assert_called_once_with(
        "x", observability.__version__,
    )


def test_ob_get_meter_with_no_pkg_expect_default_version():
    # Arrange
    with patch(
        "kuhl_haus.mdp.helpers.observability.metrics"
    ) as mock_metrics:
        # Act
        observability.get_meter("x")

    # Assert
    mock_metrics.get_meter.assert_called_once_with(
        "x", observability.__version__,
    )


# ── edge cases ───────────────────────────────────────────────────────


@pytest.mark.parametrize("name", [
    "short",
    "dotted.module.name",
    "",
])
def test_ob_get_tracer_with_various_names_expect_no_error(
    name,
):
    # Arrange / Act
    sut = observability.get_tracer(name)

    # Assert
    assert sut is not None


@pytest.mark.parametrize("name", [
    "short",
    "dotted.module.name",
    "",
])
def test_ob_get_meter_with_various_names_expect_no_error(
    name,
):
    # Arrange / Act
    sut = observability.get_meter(name)

    # Assert
    assert sut is not None
