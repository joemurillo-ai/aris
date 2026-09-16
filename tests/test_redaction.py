import copy
import json
import logging
import sys
from types import SimpleNamespace

import pytest

from aris import cli
from aris.core import runner, orchestrator
from aris.core.ledger import RunLedger
from aris.core.mission_registry import MissionRegistry
from aris.core.redaction import REDACTED, redact_diagnostic, redact_text, render_exception
from aris.utils.logging import JsonFormatter


TOKEN = "sk-syntheticCredential000000000"


@pytest.mark.parametrize("text,secret", [
    ("api_key=synthetic-value", "synthetic-value"),
    ('OPENAI_API_KEY: "synthetic value with spaces"', "synthetic value with spaces"),
    ("{'password': 'synthetic password'}", "synthetic password"),
    ('client_secret="synthetic\\\"quoted"', 'synthetic'),
    ("access_token=synthetic-token; refresh_token=synthetic-token", "synthetic-token"),
    ("Authorization: Bearer synthetic.bearer/token==", "synthetic.bearer/token=="),
    ("Bearer synthetic.bearer", "synthetic.bearer"),
    ("Authorization: Basic c3ludGhldGljOnBhc3N3b3Jk", "c3ludGhldGljOnBhc3N3b3Jk"),
    (f"provider rejected {TOKEN} twice: {TOKEN}", TOKEN),
])
def test_supported_text_patterns_repeated_and_idempotent(text, secret):
    result = redact_text(text + "\n" + text)
    assert secret not in result
    assert REDACTED in result
    assert redact_text(result) == result


@pytest.mark.parametrize("text", [
    "request timed out after 30 seconds", "status=403 run_id=abc123",
    "token_count=18", "OPENAI_API_KEY is configured", "planner complete", "",
])
def test_ordinary_text_unchanged(text):
    assert redact_text(text) == text


def test_nested_context_is_copied_and_sensitive_values_replaced():
    context = {"attempt": 2, "nested": [{"API_KEY": {"raw": "synthetic"}},
               {"Authorization": "Basic synthetic", "detail": f"rejected {TOKEN}"}],
               "items": ("ordinary", {"password": "synthetic"})}
    before = copy.deepcopy(context)
    result = redact_diagnostic(context)
    assert context == before
    assert result["attempt"] == 2
    assert result["nested"][0]["API_KEY"] == REDACTED
    assert result["nested"][1]["Authorization"] == REDACTED
    assert result["items"][0] == "ordinary"
    assert TOKEN not in json.dumps(result)


def chained_error():
    try:
        raise ValueError("password=synthetic-inner")
    except ValueError as inner:
        try:
            raise RuntimeError(f"provider failed {TOKEN}") from inner
        except RuntimeError as outer:
            outer.add_note("access_token=synthetic-note")
            return outer


def test_exception_chain_notes_and_log_rendering_preserve_originals():
    exc = chained_error()
    original = str(exc)
    record = logging.LogRecord("aris.test", logging.ERROR, __file__, 1,
                               "request %s", (TOKEN,), (type(exc), exc, exc.__traceback__))
    record.ctx = {"password": "synthetic-context", "attempt": 2}
    rendered = JsonFormatter().format(record)
    for secret in (TOKEN, "synthetic-inner", "synthetic-note", "synthetic-context"):
        assert secret not in rendered
    payload = json.loads(rendered)
    assert payload["ctx"]["attempt"] == 2
    assert "ValueError" in payload["exc"]
    assert "RuntimeError" in payload["exc"]
    assert "direct cause" in payload["exc"]
    assert str(exc) == original
    assert record.args == (TOKEN,)
    assert record.ctx["password"] == "synthetic-context"
    assert TOKEN not in render_exception(exc)


def test_cli_renders_errors_without_mutating_exception(monkeypatch, capsys):
    error = chained_error()
    def fail():
        raise error
    monkeypatch.setattr(cli, "_main", fail)
    assert cli.main() == 1
    rendered = capsys.readouterr().err
    assert TOKEN not in rendered
    assert "synthetic-inner" not in rendered
    assert "RuntimeError" in rendered
    assert TOKEN in str(error)


def test_ledger_retains_payloads_but_redacts_new_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("ARIS_RUN_ID", raising=False)
    ledger = RunLedger(tmp_path)
    rec = ledger.start("run", TOKEN)
    ledger.finish(rec, TOKEN)
    historical = (tmp_path / f"{rec.run_id}.json").read_bytes()
    assert json.loads(historical)["input"] == TOKEN
    assert json.loads(historical)["output"] == TOKEN
    error = ledger.start("run", TOKEN)
    ledger.fail(error, f"provider rejected {TOKEN}")
    persisted = json.loads((tmp_path / f"{error.run_id}.json").read_text())
    assert persisted["input"] == TOKEN
    assert TOKEN not in persisted["output"]
    assert (tmp_path / f"{rec.run_id}.json").read_bytes() == historical


def test_runner_logs_and_mission_failure_are_redacted(tmp_path, monkeypatch):
    monkeypatch.delenv("ARIS_RUN_ID", raising=False)
    error = RuntimeError(f"provider rejected {TOKEN}")
    def handler(prompt):
        raise error
    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(handler=handler))
    rendered = []
    class Capture(logging.Handler):
        def emit(self, record):
            rendered.append(JsonFormatter().format(record))
    monkeypatch.setattr(runner.log, "handlers", [Capture()])
    with pytest.raises(RuntimeError) as caught:
        orchestrator.run_review_chain("synthetic prompt", tmp_path)
    assert caught.value is error
    assert TOKEN not in "\n".join(rendered)
    assert "agent_error" in "\n".join(rendered)
    mission = MissionRegistry(tmp_path / "missions").list()[0]
    assert mission.status == "failed"
    assert TOKEN not in mission.failure_reason
    for path in tmp_path.glob("*.json"):
        assert TOKEN not in json.loads(path.read_text())["output"]


@pytest.mark.parametrize("module_name", ["doctor", "smoke"])
@pytest.mark.parametrize("configured", [False, True])
def test_operational_reports_redact_errors(tmp_path, monkeypatch, module_name, configured):
    import importlib
    module = importlib.import_module(f"aris.core.{module_name}")
    monkeypatch.setattr(module, "load_dotenv", lambda *args: None)
    monkeypatch.setattr(module.Settings, "from_env", lambda: SimpleNamespace(logs_dir=tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", TOKEN if configured else "")
    if module_name == "doctor":
        monkeypatch.setattr(module, "_run", lambda *args: (0, "synthetic-branch"))
    def fail(*args, **kwargs):
        raise OSError(f"password=synthetic-storage {TOKEN}")
    monkeypatch.setattr(type(tmp_path), "mkdir", fail)
    report = getattr(module, module_name)(tmp_path / "synthetic.env")
    assert not report.ok
    assert TOKEN not in "\n".join(report.lines)
    assert "synthetic-storage" not in "\n".join(report.lines)
    if configured:
        assert "OPENAI_API_KEY: OK" in report.lines
    else:
        assert any(line.startswith("OPENAI_API_KEY: MISSING/INVALID") for line in report.lines)


@pytest.mark.parametrize("field", [
    "api_key", "openai_api_key", "access_token", "refresh_token",
    "authorization", "password", "client_secret",
])
def test_all_supported_fields(field):
    assert redact_diagnostic({field.upper(): "synthetic"}) == {field.upper(): REDACTED}
    assert "synthetic" not in redact_text(f"{field}=synthetic")


def test_successful_runner_keeps_raw_output(tmp_path, monkeypatch):
    monkeypatch.delenv("ARIS_RUN_ID", raising=False)
    monkeypatch.setattr(runner, "get_agent", lambda name: SimpleNamespace(handler=lambda prompt: TOKEN))
    assert runner.run_agent(TOKEN, "synthetic", tmp_path) == TOKEN
    persisted = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert persisted["input"] == TOKEN
    assert persisted["output"] == TOKEN


def test_mission_failure_display_does_not_rewrite_history(tmp_path, capsys):
    from aris.core.mission import Mission
    from aris.core.missions_cli import missions_show
    mission = Mission("ordinary objective")
    mission.mark_failed(f"historical error {TOKEN}")
    path = MissionRegistry(tmp_path / "missions").save(mission)
    before = path.read_bytes()
    assert missions_show(mission.mission_id, tmp_path) == 0
    assert TOKEN not in capsys.readouterr().out
    assert path.read_bytes() == before


def test_missing_ledger_and_queue_diagnostics(tmp_path, capsys):
    from aris.core.ledger_cli import ledger_show
    from aris.core.roadmap import main
    assert ledger_show(TOKEN, tmp_path) == 1
    assert main(["validate", "--queue", str(tmp_path / TOKEN)]) == 2
    output = capsys.readouterr()
    assert "Not found:" in output.out
    assert "Queue error:" in output.err
    assert TOKEN not in output.out + output.err


@pytest.mark.parametrize("action", ["show", "approve", "deny", "quarantine", "release", "retry"])
def test_missing_mission_diagnostics(action, tmp_path, capsys):
    from aris.core import missions_cli
    args = (TOKEN, tmp_path) if action == "show" else (TOKEN, "reviewer", tmp_path)
    if action not in {"show", "approve"}:
        args = (TOKEN, "reviewer", None, tmp_path)
    assert getattr(missions_cli, f"missions_{action}")(*args) == 1
    output = capsys.readouterr().out
    assert "Mission not found:" in output
    assert TOKEN not in output


@pytest.mark.parametrize("args", [[TOKEN], ["missions", "list", "--status", TOKEN], ["ping", "--" + TOKEN]])
def test_cli_parser_diagnostics_are_redacted(args, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_dotenv", lambda *args: None)
    monkeypatch.setattr(cli.Settings, "from_env", lambda: SimpleNamespace(logs_dir=tmp_path))
    monkeypatch.setattr(sys, "argv", ["aris", *args])
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 2
    output = capsys.readouterr().err
    assert "error:" in output
    assert TOKEN not in output


def test_roadmap_parser_diagnostics_are_redacted(capsys):
    from aris.core.roadmap import main
    with pytest.raises(SystemExit) as caught:
        main([TOKEN])
    assert caught.value.code == 2
    assert TOKEN not in capsys.readouterr().err


def test_parser_preserves_help_and_argument_values():
    from argparse import ArgumentParser
    from aris.utils.argparse import DiagnosticArgumentParser
    normal = ArgumentParser(prog="synthetic")
    redacting = DiagnosticArgumentParser(prog="synthetic")
    for parser in (normal, redacting):
        parser.add_argument("--prompt")
    assert redacting.format_help() == normal.format_help()
    assert redacting.parse_args(["--prompt", TOKEN]).prompt == TOKEN


@pytest.mark.parametrize("present", [False, True])
def test_secret_check_redacts_names_preserves_status(present, monkeypatch, capsys):
    from aris.core import secrets_cli
    monkeypatch.setattr(secrets_cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(secrets_cli.Settings, "from_env", lambda: SimpleNamespace())
    monkeypatch.setattr(secrets_cli, "get_secret", lambda *args: TOKEN if present else None)
    assert secrets_cli.secrets_check(["OPENAI_API_KEY", TOKEN]) == (0 if present else 2)
    output = capsys.readouterr().out
    assert TOKEN not in output
    assert f"OPENAI_API_KEY: {'OK' if present else 'MISSING'}" in output


def test_secret_set_redacts_rendering_without_changing_storage(monkeypatch, capsys):
    from aris.core import secrets_cli
    prompts, stored = [], []
    monkeypatch.setattr(secrets_cli, "load_dotenv", lambda: None)
    monkeypatch.setattr(secrets_cli.Settings, "from_env", lambda: SimpleNamespace(
        secrets_backend="keyring", secrets_service=TOKEN,
    ))
    monkeypatch.setattr(secrets_cli.getpass, "getpass", lambda prompt: prompts.append(prompt) or "synthetic value")
    monkeypatch.setitem(sys.modules, "keyring", SimpleNamespace(set_password=lambda *args: stored.append(args)))
    assert secrets_cli.secrets_set(TOKEN) == 0
    assert TOKEN not in "".join(prompts) + capsys.readouterr().out
    assert stored == [(TOKEN, TOKEN, "synthetic value")]
