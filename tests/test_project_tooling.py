from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 compatibility.
    import tomli as tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
DEPLOY_TEST_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy-test.yml"
TEST_SYSTEMD_UNIT = PROJECT_ROOT / "deploy" / "systemd" / "telegram-goals-bot-test.service"


def test_app_package_imports() -> None:
    import app

    assert app.__name__ == "app"


def test_pytest_smoke() -> None:
    assert PROJECT_ROOT.exists()


def test_forbidden_infrastructure_dependencies_absent() -> None:
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    dependencies = pyproject["project"].get("dependencies", [])
    optional_dependencies = pyproject["project"].get("optional-dependencies", {})
    dependency_text = "\n".join(dependencies)
    for group_dependencies in optional_dependencies.values():
        dependency_text += "\n" + "\n".join(group_dependencies)

    forbidden_terms = ("docker", "postgres", "psycopg", "redis", "celery", "kubernetes")

    assert not any(term in dependency_text.lower() for term in forbidden_terms)


def test_console_script_points_to_runtime_entrypoint() -> None:
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["telegram-goals-bot"] == "app.runtime:main"


def test_runtime_does_not_reference_runtime_not_implemented_error_path() -> None:
    runtime_source = (PROJECT_ROOT / "app" / "runtime.py").read_text(encoding="utf-8")

    assert "RuntimeNotImplementedError" not in runtime_source
    assert "live Telegram polling runtime is not implemented" not in runtime_source


def test_deploy_test_workflow_uses_test_environment() -> None:
    workflow = DEPLOY_TEST_WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "environment: test" in workflow
    assert "environment: production" not in workflow
    assert "push:" not in workflow
    assert "pull_request:" not in workflow


def test_deploy_test_workflow_uses_test_scoped_secrets() -> None:
    workflow = DEPLOY_TEST_WORKFLOW.read_text(encoding="utf-8")

    assert "TEST_VPS_APP_DIR" in workflow
    assert "TEST_VPS_SERVICE_NAME" in workflow
    assert "secrets.VPS_APP_DIR" not in workflow
    assert "secrets.VPS_SERVICE_NAME" not in workflow
    assert "APP_DIR='$VPS_APP_DIR'" not in workflow
    assert "SERVICE_NAME='$VPS_SERVICE_NAME'" not in workflow
    assert "/opt/telegram_goals_bot_test" in workflow
    assert "telegram-goals-bot-test.service" in workflow
    assert "telegram-goals-bot.service" not in workflow


def test_test_systemd_unit_targets_test_app_dir_and_service() -> None:
    unit = TEST_SYSTEMD_UNIT.read_text(encoding="utf-8")

    assert "Description=Telegram Goals Bot Test" in unit
    assert "WorkingDirectory=/opt/telegram_goals_bot_test/current" in unit
    assert "EnvironmentFile=/opt/telegram_goals_bot_test/shared/.env" in unit
    assert "ExecStart=/opt/telegram_goals_bot_test/current/.venv/bin/telegram-goals-bot --env-file /opt/telegram_goals_bot_test/shared/.env run" in unit
    assert "ReadWritePaths=/opt/telegram_goals_bot_test/shared" in unit
    assert "/opt/telegram_goals_bot/current" not in unit
