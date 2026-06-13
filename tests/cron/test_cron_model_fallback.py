"""Tests for cron job model resolution fallback (Issue #43899).

Verifies that cron jobs correctly resolve the model from config.yaml
when no explicit model override is set on the job, and that a clear
RuntimeError is raised when no model can be resolved from any source.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from cron.scheduler import run_job


class TestCronModelFallback:
    """Test cron job model resolution via actual run_job() calls."""

    _RUNTIME = {
        "api_key": "test-key",
        "base_url": "https://example.invalid/v1",
        "provider": "openai",
    }

    # ------------------------------------------------------------------
    # Model from job override (highest priority)
    # ------------------------------------------------------------------
    def test_model_from_job_override(self, tmp_path, monkeypatch):
        """Job-level model should be passed through to AIAgent."""
        job = {"id": "ov-1", "model": "gpt-4", "name": "override", "prompt": "hi"}
        fake_db = MagicMock()

        with patch("cron.scheduler._hermes_home", tmp_path),              patch("cron.scheduler._resolve_origin", return_value=None),              patch("dotenv.load_dotenv"),              patch("hermes_state.SessionDB", return_value=fake_db),              patch("hermes_cli.runtime_provider.resolve_runtime_provider",
                   return_value=self._RUNTIME),              patch("run_agent.AIAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run_conversation.return_value = {"final_response": "ok"}
            mock_agent_cls.return_value = mock_agent

            success, _, _, error = run_job(job)

        assert success is True
        assert error is None
        kwargs = mock_agent_cls.call_args.kwargs
        assert kwargs["model"] == "gpt-4", (
            f"Expected model='gpt-4' from job override, got {kwargs['model']!r}"
        )

    # ------------------------------------------------------------------
    # Model from HERMES_MODEL env var
    # ------------------------------------------------------------------
    def test_model_from_env_var(self, tmp_path, monkeypatch):
        """HERMES_MODEL env var should be used when job has no model."""
        monkeypatch.setenv("HERMES_MODEL", "claude-3-from-env")
        job = {"id": "env-1", "name": "env test", "prompt": "hi"}
        fake_db = MagicMock()

        with patch("cron.scheduler._hermes_home", tmp_path),              patch("cron.scheduler._resolve_origin", return_value=None),              patch("dotenv.load_dotenv"),              patch("hermes_state.SessionDB", return_value=fake_db),              patch("hermes_cli.runtime_provider.resolve_runtime_provider",
                   return_value=self._RUNTIME),              patch("run_agent.AIAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run_conversation.return_value = {"final_response": "ok"}
            mock_agent_cls.return_value = mock_agent

            success, _, _, error = run_job(job)

        assert success is True
        assert error is None
        kwargs = mock_agent_cls.call_args.kwargs
        assert kwargs["model"] == "claude-3-from-env", (
            f"Expected model from HERMES_MODEL, got {kwargs['model']!r}"
        )

    # ------------------------------------------------------------------
    # Model from config.yaml model.default
    # ------------------------------------------------------------------
    def test_model_from_config_yaml_default(self, tmp_path, monkeypatch):
        """Config.yaml model.default should be used as fallback."""
        (tmp_path / "config.yaml").write_text(
            "model:\n  default: hermes-3-from-config\n"
        )
        job = {"id": "cfg-1", "name": "config test", "prompt": "hi"}
        fake_db = MagicMock()

        with patch("cron.scheduler._hermes_home", tmp_path),              patch("cron.scheduler._resolve_origin", return_value=None),              patch("dotenv.load_dotenv"),              patch("hermes_state.SessionDB", return_value=fake_db),              patch("hermes_cli.runtime_provider.resolve_runtime_provider",
                   return_value=self._RUNTIME),              patch("run_agent.AIAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run_conversation.return_value = {"final_response": "ok"}
            mock_agent_cls.return_value = mock_agent

            success, _, _, error = run_job(job)

        assert success is True
        assert error is None
        kwargs = mock_agent_cls.call_args.kwargs
        assert kwargs["model"] == "hermes-3-from-config", (
            f"Expected model='hermes-3-from-config' from config.yaml, got {kwargs['model']!r}"
        )

    # ------------------------------------------------------------------
    # Model from config.yaml as string
    # ------------------------------------------------------------------
    def test_model_from_config_yaml_string(self, tmp_path, monkeypatch):
        """Config.yaml model as plain string should be used."""
        (tmp_path / "config.yaml").write_text("model: hermes-3-string\n")
        job = {"id": "cfg-2", "name": "string config", "prompt": "hi"}
        fake_db = MagicMock()

        with patch("cron.scheduler._hermes_home", tmp_path),              patch("cron.scheduler._resolve_origin", return_value=None),              patch("dotenv.load_dotenv"),              patch("hermes_state.SessionDB", return_value=fake_db),              patch("hermes_cli.runtime_provider.resolve_runtime_provider",
                   return_value=self._RUNTIME),              patch("run_agent.AIAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run_conversation.return_value = {"final_response": "ok"}
            mock_agent_cls.return_value = mock_agent

            success, _, _, error = run_job(job)

        assert success is True
        assert error is None
        kwargs = mock_agent_cls.call_args.kwargs
        assert kwargs["model"] == "hermes-3-string", (
            f"Expected model='hermes-3-string' from config.yaml string, got {kwargs['model']!r}"
        )

    # ------------------------------------------------------------------
    # RuntimeError when no model can be resolved
    # ------------------------------------------------------------------
    def test_runtime_error_when_no_model(self, tmp_path, monkeypatch):
        """RuntimeError should be raised when no model source provides one."""
        job = {"id": "fail-1", "name": "no model", "prompt": "hi"}
        fake_db = MagicMock()

        with patch("cron.scheduler._hermes_home", tmp_path),              patch("cron.scheduler._resolve_origin", return_value=None),              patch("dotenv.load_dotenv"),              patch("hermes_state.SessionDB", return_value=fake_db):
            # Ensure no config.yaml exists and no env var set
            with pytest.raises(RuntimeError, match="No model configured"):
                run_job(job)

    # ------------------------------------------------------------------
    # Job model takes priority over config.yaml
    # ------------------------------------------------------------------
    def test_job_model_overrides_config(self, tmp_path, monkeypatch):
        """Job-level model should win over config.yaml model.default."""
        (tmp_path / "config.yaml").write_text(
            "model:\n  default: should-not-be-used\n"
        )
        job = {"id": "pri-1", "model": "gpt-4-priority", "name": "priority", "prompt": "hi"}
        fake_db = MagicMock()

        with patch("cron.scheduler._hermes_home", tmp_path),              patch("cron.scheduler._resolve_origin", return_value=None),              patch("dotenv.load_dotenv"),              patch("hermes_state.SessionDB", return_value=fake_db),              patch("hermes_cli.runtime_provider.resolve_runtime_provider",
                   return_value=self._RUNTIME),              patch("run_agent.AIAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run_conversation.return_value = {"final_response": "ok"}
            mock_agent_cls.return_value = mock_agent

            success, _, _, error = run_job(job)

        assert success is True
        kwargs = mock_agent_cls.call_args.kwargs
        assert kwargs["model"] == "gpt-4-priority", (
            f"Job model should override config, got {kwargs['model']!r}"
        )

    # ------------------------------------------------------------------
    # Corrupt config.yaml does not crash (graceful degradation)
    # ------------------------------------------------------------------
    def test_corrupt_config_yaml_does_not_crash(self, tmp_path, monkeypatch):
        """Corrupt config.yaml should not crash — falls through gracefully."""
        (tmp_path / "config.yaml").write_text("{{{invalid yaml!!!")
        job = {"id": "corrupt-1", "model": "gpt-4", "name": "corrupt", "prompt": "hi"}
        fake_db = MagicMock()

        with patch("cron.scheduler._hermes_home", tmp_path),              patch("cron.scheduler._resolve_origin", return_value=None),              patch("dotenv.load_dotenv"),              patch("hermes_state.SessionDB", return_value=fake_db),              patch("hermes_cli.runtime_provider.resolve_runtime_provider",
                   return_value=self._RUNTIME),              patch("run_agent.AIAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run_conversation.return_value = {"final_response": "ok"}
            mock_agent_cls.return_value = mock_agent

            success, _, _, error = run_job(job)

        # Should still succeed because job has explicit model
        assert success is True
