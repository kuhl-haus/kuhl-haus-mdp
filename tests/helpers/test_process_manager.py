# tests\test_process_manager.py

import unittest
from unittest.mock import Mock, patch

from kuhl_haus.mdp.helpers.process_manager import ProcessManager


class TestProcessManager(unittest.TestCase):
    """Unit tests for ProcessManager."""

    def setUp(self):
        """Set up a ProcessManager instance for testing."""
        self.process_manager = ProcessManager()

    @patch("kuhl_haus.mdp.helpers.process_manager.Process")
    @patch("kuhl_haus.mdp.helpers.process_manager.Queue")
    @patch("kuhl_haus.mdp.helpers.process_manager.MPEvent")
    def test_start_worker_creates_and_starts_process(self, mock_mp_event, mock_queue, mock_process):
        """
        Test that start_worker creates and starts a process correctly.
        Scenario: A worker is started by ProcessManager.
        Expected: ProcessManager stores process, shutdown_event, and status_queue for the worker.
        """
        # Arrange
        mock_worker_class = Mock()
        worker_name = "worker_1"

        # Act
        self.process_manager.start_worker(name=worker_name, worker_class=mock_worker_class)

        # Assert
        self.assertIn(worker_name, self.process_manager.processes)
        self.assertIn(worker_name, self.process_manager.shutdown_events)
        self.assertIn(worker_name, self.process_manager.status_queues)
        mock_process.return_value.start.assert_called_once()

    @patch("kuhl_haus.mdp.helpers.process_manager.logger")
    @patch("kuhl_haus.mdp.helpers.process_manager.Process")
    def test_stop_process_stops_running_process(self, mock_process, mock_logger):
        """
        Test that stop_process stops a running process.
        Scenario: A worker process is stopped via ProcessManager.
        Expected: The process is joined or killed if it doesn't terminate within the timeout.
        """
        # Arrange
        mock_process_instance = mock_process.return_value
        mock_process_instance.is_alive.return_value = True
        mock_shutdown_event = Mock()
        worker_name = "worker_1"
        self.process_manager.processes[worker_name] = mock_process_instance
        self.process_manager.shutdown_events[worker_name] = mock_shutdown_event

        # Act
        self.process_manager.stop_process(worker_name)

        # Assert
        mock_shutdown_event.set.assert_called_once()
        # First join with timeout, then kill, then join without timeout
        self.assertEqual(mock_process_instance.join.call_count, 2)
        mock_process_instance.join.assert_any_call(timeout=10.0)
        mock_process_instance.kill.assert_called_once()

    @patch("kuhl_haus.mdp.helpers.process_manager.logger")
    def test_get_status_returns_correct_status(self, mock_logger):
        """
        Test that get_status returns the correct status for a worker.
        Scenario: A worker's status is retrieved.
        Expected: The status dictionary contains both process information and worker-specific metrics.
        """
        # Arrange
        mock_process = Mock()
        mock_process.is_alive.return_value = True
        mock_process.pid = 12345
        mock_status_queue = Mock()
        mock_status_queue.get_nowait.return_value = {"processed": 10, "errors": 1}

        worker_name = "worker_1"
        self.process_manager.processes[worker_name] = mock_process
        self.process_manager.status_queues[worker_name] = mock_status_queue

        # Act
        status = self.process_manager.get_status(worker_name)

        # Assert
        self.assertTrue(status["alive"])
        self.assertEqual(status["pid"], 12345)
        self.assertEqual(status["processed"], 10)
        self.assertEqual(status["errors"], 1)

    def test_get_status_returns_alive_false_when_worker_not_found(self):
        """
        Test that get_status returns {"alive": False} when the worker does not exist.
        Scenario: A status is requested for a nonexistent worker.
        Expected: The status indicates the worker is not alive.
        """
        # Act
        status = self.process_manager.get_status("nonexistent_worker")

        # Assert
        self.assertEqual(status, {"alive": False})


    @patch("kuhl_haus.mdp.helpers.process_manager.ProcessManager.stop_process")
    def test_stop_all_stops_all_processes(self, mock_stop_process):
        """
        Test that stop_all stops all running processes.
        Scenario: All processes are stopped via ProcessManager.
        Expected: stop_process is called for each process.
        """
        # Arrange
        self.process_manager.processes = {
            "worker_1": Mock(),
            "worker_2": Mock(),
            "worker_3": Mock()
        }

        # Act
        self.process_manager.stop_all()

        # Assert
        self.assertEqual(mock_stop_process.call_count, 3)
        # Check that stop_process was called with each worker name and the default timeout
        mock_stop_process.assert_any_call("worker_1", 10.0)
        mock_stop_process.assert_any_call("worker_2", 10.0)
        mock_stop_process.assert_any_call("worker_3", 10.0)


if __name__ == "__main__":
    unittest.main()
