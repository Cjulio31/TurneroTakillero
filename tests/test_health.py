import sqlite3

import pytest

from app.controllers import app_state as st
from app.services.health_service import (
    LEVEL_DEGRADED,
    LEVEL_DOWN,
    LEVEL_OK,
    HealthService,
)
from app.ui.main_window import MainWindow


class Env:
    def __init__(self, ctx):
        self.ctx = ctx
        self.service = HealthService(ctx.state, ctx.db, ctx.turns, interval_ms=10_000)
        self.reports = []
        self.service.report_changed.connect(self.reports.append)

    def all_good(self):
        for component, status in (
            ("hub", st.READY),
            ("serial", st.CONNECTED),
            ("printer", st.AVAILABLE),
        ):
            self.ctx.state.set_status(component, status)


@pytest.fixture
def env(ctx):
    e = Env(ctx)
    yield e
    e.service.stop()


def test_ok_when_everything_is_up(env):
    env.all_good()
    report = env.service.start()
    assert report.level == LEVEL_OK and report.problems == ()
    assert report.summary == "Todo en orden"
    assert env.ctx.state.status("database") == st.OK


def test_degraded_lists_unavailable_components(env):
    env.all_good()
    env.service.start()
    env.ctx.state.set_status("printer", st.UNAVAILABLE)
    report = env.service.report()
    assert report.level == LEVEL_DEGRADED
    assert report.problems == ("Impresora no disponible",)
    assert env.reports[-1].level == LEVEL_DEGRADED  # reaccionó al cambio de estado sin timer


def test_turn_counts_and_errors_degrade(env):
    env.all_good()
    for mid in "ABC":
        env.ctx.turns.add(mid, "T", 1)
    env.ctx.turns.update_status("A", "COMPLETED")
    env.ctx.turns.update_status("B", "ERROR", "PRINT", "sin papel")
    report = env.service.start()
    assert (report.pending, report.errors) == (2, 1)
    assert report.level == LEVEL_DEGRADED and "1 turno(s) en error" in report.problems


def test_report_emitted_only_on_change(env):
    env.all_good()
    env.service.start()
    count = len(env.reports)
    env.service.check()
    env.service.check()
    assert len(env.reports) == count


def test_database_failure_is_down_and_recovers(env, monkeypatch):
    env.all_good()
    env.service.start()
    monkeypatch.setattr(env.ctx.db, "ping", lambda: False)
    report = env.service.check()
    assert report.level == LEVEL_DOWN and env.ctx.state.status("database") == st.ERROR
    monkeypatch.undo()
    assert env.service.check().level == LEVEL_OK


def test_failed_integrity_check_is_not_masked_by_ping(env, monkeypatch):
    env.all_good()
    monkeypatch.setattr(env.ctx.db, "is_ok", lambda: False)
    assert env.service.start().level == LEVEL_DOWN
    assert env.service.check().level == LEVEL_DOWN


def test_unreadable_turn_table_is_down(env, monkeypatch):
    def boom():
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(env.ctx.turns, "count_by_status", boom)
    assert env.service.report().level == LEVEL_DOWN


def test_ui_shows_health(qtbot, ctx):
    health = HealthService(ctx.state, ctx.db, ctx.turns)
    ctx.turns.add("A", "T", 1)
    window = MainWindow(ctx, health=health)
    qtbot.addWidget(window)
    health.start()
    health.stop()
    dash = window.pages["Inicio"]
    dash.refresh()
    assert dash._health.text() == "Pendientes: 1 · En error: 0"
    assert "OK" in dash._indicators["database"].text()
    assert "Estado:" in window.tray.status_action.text()
