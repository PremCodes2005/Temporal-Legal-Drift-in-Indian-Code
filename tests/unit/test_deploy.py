"""Always-on deployment: missed-run alerting, the --check exit code, systemd unit wiring and the alert script."""

from __future__ import annotations

import configparser
import io
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from temporal_legal_drift.cli import build_parser, main
from temporal_legal_drift.monitoring import MonitoringService

ROOT = Path(__file__).resolve().parents[2]
UNITS = ROOT / "deploy/systemd"


def _unit(name: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read(UNITS / name)
    return parser


class Clock:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


class MissedRunAlertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        state = self.root / "data/monitoring/state.v1.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({"sources": {"india_code": {
            "last_attempt_at": "2026-10-12T00:00:00+00:00", "last_success_at": "2026-10-12T00:05:00+00:00",
            "next_eligible_at": "2026-10-13T00:00:00+00:00", "last_status": "OK"}}}))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def alerts(self, now: str) -> list[str]:
        return [alert["code"] for alert in MonitoringService(self.root, {}, clock=Clock(now)).health()["alerts"]]

    def test_healthy_within_the_window_and_the_grace_period(self) -> None:
        self.assertEqual(self.alerts("2026-10-12T12:00:00+00:00"), [])
        self.assertEqual(self.alerts("2026-10-13T01:59:00+00:00"), [])  # hourly trigger may still be on its way

    def test_trigger_that_stops_firing_is_reported_as_a_missed_run(self) -> None:
        self.assertEqual(self.alerts("2026-10-13T02:01:00+00:00"), ["SCHEDULER_MISSED_RUN"])

    def test_repeated_source_failures_are_reported_as_stale_ingestion(self) -> None:
        self.assertIn("INGESTION_STALE", self.alerts("2026-10-14T00:06:00+00:00"))

    def test_check_flag_turns_alerts_into_a_failing_exit_code(self) -> None:
        from datetime import UTC, datetime, timedelta

        now = datetime.now(UTC)  # the CLI uses the wall clock, so the healthy state is built relative to it
        state = self.root / "data/monitoring/state.v1.json"
        state.write_text(json.dumps({"sources": {"india_code": {
            "last_attempt_at": (now - timedelta(hours=1)).isoformat(), "last_success_at": (now - timedelta(hours=1)).isoformat(),
            "next_eligible_at": (now + timedelta(hours=23)).isoformat(), "last_status": "OK"}}}))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--project-root", str(self.root), "monitor-health", "--check"]), 0)
        stale = json.loads(state.read_text())
        stale["sources"]["india_code"].update(next_eligible_at="2020-01-01T00:00:00+00:00")
        state.write_text(json.dumps(stale))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--project-root", str(self.root), "monitor-health", "--check"]), 3)
            self.assertEqual(main(["--project-root", str(self.root), "monitor-health"]), 0)  # plain report never fails


class SystemdUnitTests(unittest.TestCase):
    def test_timers_are_persistent_so_downtime_does_not_silently_skip_a_run(self) -> None:
        for name in ("tldrift-monitor.timer", "tldrift-health.timer"):
            self.assertEqual(_unit(name)["Timer"]["Persistent"], "true", name)
        # Hourly on the hour UTC (:30 IST): the 01:00 UTC (06:30 IST) trigger is the daily slot, the others catch up a missed one.
        self.assertEqual(_unit("tldrift-monitor.timer")["Timer"]["OnCalendar"], "*-*-* *:00:00 UTC")

    def test_both_jobs_alert_on_failure_and_call_real_cli_commands(self) -> None:
        parser = build_parser()
        for name, expected in (("tldrift-monitor.service", ["monitor-run", "--owner", "systemd@%H", "--daily-at", "06:30",
                                                             "--timezone", "Asia/Kolkata", "--notify"]),
                               ("tldrift-health.service", ["monitor-notify", "--check"])):
            unit = _unit(name)
            self.assertEqual(unit["Unit"]["OnFailure"], "tldrift-alert@%n.service")
            command = shlex.split(unit["Service"]["ExecStart"])
            self.assertTrue(command[0].endswith("/.venv/bin/tldrift"))
            self.assertEqual(command[1:], expected)
            parser.parse_args([part.replace("%H", "host") for part in command[1:]])  # the command exists
        self.assertTrue((ROOT / shlex.split(_unit("tldrift-alert@.service")["Service"]["ExecStart"])[0]
                         .replace("/srv/temporal-legal-drift/", "")).is_file())

    def test_launchd_wrapper_runs_the_same_daily_slot_with_real_cli_commands(self) -> None:
        script = (ROOT / "deploy/launchd/run.sh").read_text()
        installer = (ROOT / "deploy/launchd/install.sh").read_text()
        self.assertIn("<key>Minute</key><integer>30</integer>", installer)  # hourly at :30, as on systemd
        self.assertIn('TLDRIFT_DAILY_AT:-06:30', script)
        self.assertIn('TLDRIFT_TIMEZONE:-Asia/Kolkata', script)
        parser = build_parser()
        parser.parse_args(["monitor-run", "--owner", "launchd@host", "--daily-at", "06:30", "--timezone", "Asia/Kolkata", "--notify"])
        parser.parse_args(["monitor-notify", "--check"])
        self.assertEqual(subprocess.run(["sh", "-n", str(ROOT / "deploy/launchd/run.sh")]).returncode, 0)

    def test_no_secret_is_committed_in_the_environment_example(self) -> None:
        text = (UNITS / "tldrift.env.example").read_text()
        self.assertIn("TLDRIFT_HEARTBEAT_URL=\n", text)
        self.assertNotRegex(text, r"(?i)(token|password|secret|apikey)=\S")


class AlertScriptTests(unittest.TestCase):
    def run_alert(self, command: str) -> tuple[subprocess.CompletedProcess, str]:
        with tempfile.TemporaryDirectory() as directory:
            sink = Path(directory) / "alert.txt"
            env = {**os.environ, "TLDRIFT_ALERT_COMMAND": command.replace("SINK", str(sink)),
                   "TLDRIFT_ROOT": str(ROOT), "TLDRIFT_BIN": "true"}
            result = subprocess.run([str(ROOT / "deploy/alert.sh"), "tldrift-monitor.service"], env=env,
                                    capture_output=True, text=True, timeout=30)
            return result, sink.read_text() if sink.exists() else ""

    def test_alert_command_receives_the_failed_unit(self) -> None:
        result, delivered = self.run_alert("cat > SINK")
        self.assertEqual(result.returncode, 0)
        self.assertIn("tldrift-monitor.service failed", delivered)

    def test_failed_alert_delivery_is_not_silent(self) -> None:
        result, _ = self.run_alert("exit 9")
        self.assertEqual(result.returncode, 1)
        self.assertIn("tldrift-monitor.service failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
