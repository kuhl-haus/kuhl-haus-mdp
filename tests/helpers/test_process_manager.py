import asyncio
from multiprocessing import Process, Queue
from multiprocessing.synchronize import Event as MPEvent
from queue import Empty, Full
from unittest.mock import MagicMock, patch

import pytest

from kuhl_haus.mdp.helpers.process_manager import (
    ProcessManager,
    _setup_otel_auto_instrumentation,
)


# ── helpers ──────────────────────────────────────────────────────────


class _FakeWorker:
    """Minimal async worker for testing _run_worker."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.running = True
        self.processed = 10
        self.errors = 2
        self.decoding_error = 1
        self.published = 5
        self.processing_error = 3
        self.mdq_connected = True
        self.mdc_connected = True
        self.restarts = 0
        self.start_called = False
        self.stop_called = False

    async def start(self):
        self.start_called = True
        while self.running:
            await asyncio.sleep(0.05)

    async def stop(self):
        self.stop_called = True


class _FailingWorker:
    """Worker whose start() raises immediately."""

    def __init__(self, **kwargs):
        self.running = False

    async def start(self):
        raise RuntimeError("boom")

    async def stop(self):
        pass


class _NoRunningAttrWorker:
    """Worker without a 'running' attribute (hits hasattr branch)."""

    def __init__(self, **kwargs):
        self.start_called = False
        self.stop_called = False

    async def start(self):
        self.start_called = True
        await asyncio.sleep(60)  # Will be cancelled

    async def stop(self):
        self.stop_called = True


class _StopFailsWorker:
    """Worker whose stop() raises (hits final stop() exception branch)."""

    def __init__(self, **kwargs):
        self.running = True

    async def start(self):
        while self.running:
            await asyncio.sleep(0.05)

    async def stop(self):
        raise RuntimeError("stop failed")


# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def sut():
    return ProcessManager()


# ── __init__ ─────────────────────────────────────────────────────────


def test_pm_init_with_defaults_expect_empty_dicts():
    # Arrange / Act
    sut = ProcessManager()

    # Assert
    assert sut.processes == {}
    assert sut.shutdown_events == {}
    assert sut.status_queues == {}


# ── start_worker ─────────────────────────────────────────────────────


@patch(
    "kuhl_haus.mdp.helpers.process_manager.Process"
)
def test_pm_start_worker_with_valid_class_expect_process_started(
    mock_process_cls, sut
):
    # Arrange
    mock_proc = MagicMock(spec=Process)
    mock_proc.pid = 1234
    mock_process_cls.return_value = mock_proc

    # Act
    with patch("multiprocessing.Event") as mock_event, \
         patch("multiprocessing.Queue") as mock_queue, \
         patch("opentelemetry.context.get_current"), \
         patch("opentelemetry.propagate.inject"):
        mock_event.return_value = MagicMock(spec=MPEvent)
        mock_queue.return_value = MagicMock()
        sut.start_worker("test", _FakeWorker, foo="bar")

    # Assert
    assert "test" in sut.processes
    assert "test" in sut.shutdown_events
    assert "test" in sut.status_queues
    mock_proc.start.assert_called_once()


# ── stop_process ─────────────────────────────────────────────────────


def test_pm_stop_process_with_alive_proc_expect_join_called(sut):
    # Arrange
    mock_proc = MagicMock(spec=Process)
    mock_proc.is_alive.return_value = False
    mock_event = MagicMock(spec=MPEvent)
    sut.processes["w1"] = mock_proc
    sut.shutdown_events["w1"] = mock_event
    sut.status_queues["w1"] = MagicMock(spec=Queue)

    # Act
    sut.stop_process("w1", timeout=5.0)

    # Assert
    mock_event.set.assert_called_once()
    mock_proc.join.assert_called_once_with(timeout=5.0)
    mock_proc.kill.assert_not_called()


def test_pm_stop_process_with_hung_proc_expect_force_kill(sut):
    # Arrange
    mock_proc = MagicMock(spec=Process)
    mock_proc.is_alive.return_value = True
    mock_event = MagicMock(spec=MPEvent)
    sut.processes["w1"] = mock_proc
    sut.shutdown_events["w1"] = mock_event
    sut.status_queues["w1"] = MagicMock(spec=Queue)

    # Act
    sut.stop_process("w1", timeout=1.0)

    # Assert
    mock_proc.kill.assert_called_once()
    assert mock_proc.join.call_count == 2


def test_pm_stop_process_with_unknown_name_expect_noop(sut):
    # Arrange — no processes registered

    # Act
    sut.stop_process("nonexistent")

    # Assert — no exception raised
    assert "nonexistent" not in sut.processes


# ── stop_all ─────────────────────────────────────────────────────────


def test_pm_stop_all_with_multiple_procs_expect_all_stopped(sut):
    # Arrange
    for name in ("a", "b", "c"):
        mock_proc = MagicMock(spec=Process)
        mock_proc.is_alive.return_value = False
        sut.processes[name] = mock_proc
        sut.shutdown_events[name] = MagicMock(spec=MPEvent)
        sut.status_queues[name] = MagicMock(spec=Queue)

    # Act
    sut.stop_all(timeout=2.0)

    # Assert
    for name in ("a", "b", "c"):
        sut.shutdown_events[name].set.assert_called_once()
        sut.processes[name].join.assert_called_once_with(
            timeout=2.0
        )


def test_pm_stop_all_with_no_procs_expect_noop(sut):
    # Arrange — empty

    # Act
    sut.stop_all()

    # Assert — no exception
    assert sut.processes == {}


# ── get_status ───────────────────────────────────────────────────────


def test_pm_get_status_with_unknown_name_expect_not_alive(sut):
    # Arrange — no processes

    # Act
    result = sut.get_status("missing")

    # Assert
    assert result == {"alive": False}


def test_pm_get_status_with_queue_data_expect_merged(sut):
    # Arrange
    mock_proc = MagicMock(spec=Process)
    mock_proc.is_alive.return_value = True
    mock_proc.pid = 42
    mock_queue = MagicMock()
    mock_queue.get_nowait.return_value = {
        "processed": 100,
        "running": True,
    }
    sut.processes["w1"] = mock_proc
    sut.shutdown_events["w1"] = MagicMock(spec=MPEvent)
    sut.status_queues["w1"] = mock_queue

    # Act
    result = sut.get_status("w1")

    # Assert
    assert result["alive"] is True
    assert result["pid"] == 42
    assert result["processed"] == 100
    assert result["running"] is True


def test_pm_get_status_with_empty_queue_expect_base_only(sut):
    # Arrange
    mock_proc = MagicMock(spec=Process)
    mock_proc.is_alive.return_value = True
    mock_proc.pid = 99
    mock_queue = MagicMock()
    mock_queue.get_nowait.side_effect = Empty()
    sut.processes["w1"] = mock_proc
    sut.shutdown_events["w1"] = MagicMock(spec=MPEvent)
    sut.status_queues["w1"] = mock_queue

    # Act
    result = sut.get_status("w1")

    # Assert
    assert result == {"alive": True, "pid": 99}


def test_pm_get_status_with_queue_error_expect_base_only(sut):
    # Arrange
    mock_proc = MagicMock(spec=Process)
    mock_proc.is_alive.return_value = False
    mock_proc.pid = 7
    mock_queue = MagicMock()
    mock_queue.get_nowait.side_effect = OSError("broken")
    sut.processes["w1"] = mock_proc
    sut.shutdown_events["w1"] = MagicMock(spec=MPEvent)
    sut.status_queues["w1"] = mock_queue

    # Act
    result = sut.get_status("w1")

    # Assert
    assert result["alive"] is False
    assert result["pid"] == 7
    assert "processed" not in result


# ── _run_worker (static) ─────────────────────────────────────────────


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_shutdown_expect_clean_stop(
    mock_otel,
):
    # Arrange
    shutdown_event = MagicMock(spec=MPEvent)
    call_count = 0

    def is_set_side_effect():
        nonlocal call_count
        call_count += 1
        return call_count > 2

    shutdown_event.is_set.side_effect = is_set_side_effect
    status_queue = MagicMock()

    # Act
    ProcessManager._run_worker(
        _FakeWorker, shutdown_event, status_queue, None
    )

    # Assert
    mock_otel.assert_called_once()
    assert status_queue.put_nowait.called


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_trace_ctx_expect_attached(
    mock_otel,
):
    # Arrange
    shutdown_event = MagicMock(spec=MPEvent)
    shutdown_event.is_set.side_effect = [False, True]
    status_queue = MagicMock()
    trace_ctx = {"traceparent": "00-abc-def-01"}

    # Act
    with patch(
        "opentelemetry.context.attach"
    ) as mock_attach, patch(
        "opentelemetry.propagate.extract"
    ) as mock_extract:
        ProcessManager._run_worker(
            _FakeWorker, shutdown_event, status_queue,
            trace_ctx
        )

    # Assert
    mock_extract.assert_called_once_with(trace_ctx)
    mock_attach.assert_called_once()


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_failing_worker_expect_no_crash(
    mock_otel,
):
    # Arrange
    shutdown_event = MagicMock(spec=MPEvent)
    shutdown_event.is_set.side_effect = [False, True]
    status_queue = MagicMock()

    # Act — should not raise
    ProcessManager._run_worker(
        _FailingWorker, shutdown_event, status_queue, None
    )

    # Assert
    mock_otel.assert_called_once()


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_full_queue_expect_skip(
    mock_otel,
):
    # Arrange
    shutdown_event = MagicMock(spec=MPEvent)
    call_count = 0

    def is_set_side_effect():
        nonlocal call_count
        call_count += 1
        return call_count > 2

    shutdown_event.is_set.side_effect = is_set_side_effect
    status_queue = MagicMock()
    status_queue.put_nowait.side_effect = Full()

    # Act — should not raise despite Full queue
    ProcessManager._run_worker(
        _FakeWorker, shutdown_event, status_queue, None
    )

    # Assert
    mock_otel.assert_called_once()


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_kwargs_expect_passed_to_worker(
    mock_otel,
):
    # Arrange
    shutdown_event = MagicMock(spec=MPEvent)
    shutdown_event.is_set.side_effect = [False, True]
    status_queue = MagicMock()
    captured = {}

    class _CapturingWorker:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.running = False

        async def start(self):
            pass

        async def stop(self):
            pass

    # Act
    ProcessManager._run_worker(
        _CapturingWorker, shutdown_event, status_queue,
        None, my_arg="hello"
    )

    # Assert
    assert captured["my_arg"] == "hello"


# ── _setup_otel_auto_instrumentation ─────────────────────────────────


def test_setup_otel_with_success_expect_initialize_called():
    # Arrange
    mock_site = MagicMock()
    mock_parent = MagicMock()
    mock_parent.sitecustomize = mock_site
    import sys

    # Act
    with patch.dict(sys.modules, {
        "opentelemetry.instrumentation"
        ".auto_instrumentation": mock_parent,
        "opentelemetry.instrumentation"
        ".auto_instrumentation"
        ".sitecustomize": mock_site,
    }):
        _setup_otel_auto_instrumentation()

    # Assert
    mock_site.initialize.assert_called_once()


def test_setup_otel_with_import_error_expect_no_crash():
    # Arrange — function catches all exceptions

    # Act — should not raise
    _setup_otel_auto_instrumentation()

    # Assert — no exception raised


# ── additional _run_worker branch coverage ───────────────────────────


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_trace_attach_failure_expect_warning(
    mock_otel,
):
    # Arrange — attach() raises, hitting lines 81-82
    shutdown_event = MagicMock(spec=MPEvent)
    shutdown_event.is_set.side_effect = [False, True]
    status_queue = MagicMock()
    trace_ctx = {"traceparent": "00-abc-def-01"}

    # Act
    with patch(
        "opentelemetry.context.attach",
        side_effect=RuntimeError("attach failed")
    ), patch("opentelemetry.propagate.extract"):
        ProcessManager._run_worker(
            _FakeWorker, shutdown_event, status_queue,
            trace_ctx
        )

    # Assert — no crash, worker still ran
    mock_otel.assert_called_once()


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_no_running_attr_expect_skip(
    mock_otel,
):
    # Arrange — worker has no 'running' attr (hits hasattr False branch)
    shutdown_event = MagicMock(spec=MPEvent)
    shutdown_event.is_set.side_effect = [False, True]
    status_queue = MagicMock()

    # Act — should not raise
    ProcessManager._run_worker(
        _NoRunningAttrWorker, shutdown_event, status_queue, None
    )

    # Assert
    mock_otel.assert_called_once()


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_stop_failure_expect_error_logged(
    mock_otel,
):
    # Arrange — worker.stop() raises (hits lines 198-199)
    shutdown_event = MagicMock(spec=MPEvent)
    shutdown_event.is_set.side_effect = [False, True]
    status_queue = MagicMock()

    # Act — should not raise despite stop() failing
    ProcessManager._run_worker(
        _StopFailsWorker, shutdown_event, status_queue, None
    )

    # Assert
    mock_otel.assert_called_once()


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_status_reporter_exception_expect_continue(
    mock_otel,
):
    # Arrange — status_queue.put_nowait raises non-Full exception (line 125-126)
    shutdown_event = MagicMock(spec=MPEvent)
    call_count = 0

    def is_set_side_effect():
        nonlocal call_count
        call_count += 1
        return call_count > 2

    shutdown_event.is_set.side_effect = is_set_side_effect
    status_queue = MagicMock()
    status_queue.put_nowait.side_effect = RuntimeError("queue broken")

    # Act — should not raise
    ProcessManager._run_worker(
        _FakeWorker, shutdown_event, status_queue, None
    )

    # Assert
    mock_otel.assert_called_once()


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_init_failure_expect_worker_none(
    mock_otel,
):
    # Arrange — worker_class() raises, so worker=None in finally (line 195→exit)

    class _InitFailsWorker:
        def __init__(self, **kwargs):
            raise RuntimeError("init failed")

    shutdown_event = MagicMock(spec=MPEvent)
    shutdown_event.is_set.side_effect = [False, True]
    status_queue = MagicMock()

    # Act — should not raise
    ProcessManager._run_worker(
        _InitFailsWorker, shutdown_event, status_queue, None
    )

    # Assert
    mock_otel.assert_called_once()


def test_pm_setup_otel_with_runtime_error_expect_no_crash():
    # Arrange — initialize() raises RuntimeError (line 274-275)
    import sys
    mock_site = MagicMock()
    mock_site.initialize.side_effect = RuntimeError("otel broken")
    mock_parent = MagicMock()
    mock_parent.sitecustomize = mock_site

    # Act — should not raise
    with patch.dict(sys.modules, {
        "opentelemetry.instrumentation"
        ".auto_instrumentation": mock_parent,
        "opentelemetry.instrumentation"
        ".auto_instrumentation"
        ".sitecustomize": mock_site,
    }):
        _setup_otel_auto_instrumentation()

    # Assert — no crash


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_worker_task_cancel_exception_expect_logged(
    mock_otel,
):
    # Arrange — worker.start() raises RuntimeError on cancellation (lines 169-170)

    class _CancelRaisesWorker:
        def __init__(self, **kwargs):
            self.running = True

        async def start(self):
            try:
                while self.running:
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                raise RuntimeError("cleanup failed during cancel")

        async def stop(self):
            pass

    shutdown_event = MagicMock(spec=MPEvent)
    shutdown_event.is_set.side_effect = [False, True]
    status_queue = MagicMock()

    # Act — should not crash
    ProcessManager._run_worker(
        _CancelRaisesWorker, shutdown_event, status_queue, None
    )

    # Assert
    mock_otel.assert_called_once()


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_delayed_shutdown_expect_status_reporter_loops(
    mock_otel,
):
    # Arrange — shutdown takes >1s so status_reporter hits the
    # asyncio.TimeoutError pass on line 132 at least once.
    # Also exercises signal handler line 86 via direct call.

    class _DelayedWorker:
        def __init__(self, **kwargs):
            self.running = True

        async def start(self):
            while self.running:
                await asyncio.sleep(0.05)

        async def stop(self):
            pass

    shutdown_event = MagicMock(spec=MPEvent)
    # Return False for ~1.5s worth of 0.1s polls (15 calls), then True
    shutdown_event.is_set.side_effect = (
        [False] * 15 + [True]
    )
    status_queue = MagicMock()

    # Act
    ProcessManager._run_worker(
        _DelayedWorker, shutdown_event, status_queue, None
    )

    # Assert — status_queue.put_nowait called multiple times
    assert status_queue.put_nowait.call_count >= 1
    mock_otel.assert_called_once()


@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_fatal_loop_error_expect_logged(
    mock_otel,
):
    # Arrange — loop.run_until_complete raises (lines 204-205)
    shutdown_event = MagicMock(spec=MPEvent)
    status_queue = MagicMock()

    original_new_event_loop = asyncio.new_event_loop

    def create_failing_loop():
        loop = original_new_event_loop()
        original_run = loop.run_until_complete

        def failing_run(coro):
            # Close the coroutine to prevent "never awaited" warning
            coro.close()
            raise RuntimeError("fatal loop error")

        loop.run_until_complete = failing_run
        return loop

    with patch("asyncio.new_event_loop", side_effect=create_failing_loop):
        # Act — should not crash
        ProcessManager._run_worker(
            _FakeWorker, shutdown_event, status_queue, None
        )

    # Assert
    mock_otel.assert_called_once()




@patch(
    "kuhl_haus.mdp.helpers.process_manager"
    "._setup_otel_auto_instrumentation"
)
def test_pm_run_worker_with_pending_tasks_expect_cleanup(
    mock_otel,
):
    # Arrange — worker leaves dangling tasks that need cleanup (lines 211, 215-217)

    class _LeakyWorker:
        def __init__(self, **kwargs):
            self.running = True

        async def start(self):
            # Create a dangling task that won't finish
            async def background():
                await asyncio.sleep(999)

            asyncio.create_task(background())
            while self.running:
                await asyncio.sleep(0.05)

        async def stop(self):
            pass

    shutdown_event = MagicMock(spec=MPEvent)
    shutdown_event.is_set.side_effect = [False, True]
    status_queue = MagicMock()

    # Act — should clean up pending tasks in finally block
    ProcessManager._run_worker(
        _LeakyWorker, shutdown_event, status_queue, None
    )

    # Assert
    mock_otel.assert_called_once()
