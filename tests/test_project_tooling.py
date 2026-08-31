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


def test_dev_pytest_dependency_allows_security_fixed_version() -> None:
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    assert "pytest>=9.0.3,<10" in pyproject["project"]["optional-dependencies"]["dev"]


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


def test_deploy_test_workflow_has_read_only_business_sheet_diagnostic() -> None:
    workflow = DEPLOY_TEST_WORKFLOW.read_text(encoding="utf-8")
    assert "          - inspect_business_sheet" in workflow

    job_start = workflow.index("  inspect-business-sheet:\n")
    job_end = workflow.index("\n  configure-flow-registry:\n", job_start)
    job = workflow[job_start:job_end]
    assert "if: inputs.mode == 'inspect_business_sheet'" in job
    assert "environment: test" in job
    assert "permissions:\n      contents: read" in job
    assert "- name: Report configured business spreadsheet" in job
    assert 'cd "$TEST_APP_DIR/current"' in job
    assert 'spreadsheet_id = os.environ["GOOGLE_SHEETS_ID"]' in job
    assert 'os.environ["GOOGLE_APPLICATION_CREDENTIALS"]' in job
    assert "https://www.googleapis.com/auth/spreadsheets.readonly" in job
    assert 'build("sheets", "v4"' in job
    assert 'fields="properties.title"' in job
    assert ").execute()" in job
    assert 'print(f"BUSINESS_SHEET_ID={spreadsheet_id}")' in job
    assert 'print(f"BUSINESS_SHEET_TITLE={title}")' in job
    assert "BUSINESS_SHEET_TABS" not in job


def test_deploy_test_workflow_has_bounded_business_schema_migration() -> None:
    workflow = DEPLOY_TEST_WORKFLOW.read_text(encoding="utf-8")
    assert "          - migrate_business_schema" in workflow

    job_start = workflow.index("  migrate-business-schema:\n")
    job_end = workflow.index("\n  configure-flow-registry:\n", job_start)
    job = workflow[job_start:job_end]
    assert "if: inputs.mode == 'migrate_business_schema'" in job
    assert "environment: test" in job
    assert 'spreadsheet_id = os.environ["GOOGLE_SHEETS_ID"]' in job
    assert "https://www.googleapis.com/auth/spreadsheets" in job
    for header in (
        "bot_started_at",
        "consent_status",
        "flow_id",
        "last_stage_updated_at",
        "onboarding_completed_at",
        "participant_stage",
    ):
        assert f'"{header}"' in job
    assert '"Teams": ("flow_id",)' in job
    assert 'range=f"\'{sheet_name}\'"' in job
    assert 'valueRenderOption="FORMULA"' in job
    assert "used_width = max((len(row) for row in rows), default=0)" in job
    assert "start = max(len(headers), used_width)" in job
    assert "missing_sheets" in job
    assert "plans.append((sheet_name, missing, start, end))" in job
    assert "if requests:" in job
    assert "for header in required[sheet_name] if header not in verified" in job
    assert '"pasteType": "PASTE_FORMAT"' in job
    assert "Schema verification failed" in job


def test_deploy_test_workflow_creates_sensitive_shared_dirs_private() -> None:
    workflow = DEPLOY_TEST_WORKFLOW.read_text(encoding="utf-8")

    assert "install -d -m 700" in workflow
    assert "mkdir -p \\\n            \"$TEST_APP_DIR/shared/data/audio\"" not in workflow


def test_deploy_test_workflow_installs_test_systemd_unit() -> None:
    workflow = DEPLOY_TEST_WORKFLOW.read_text(encoding="utf-8")

    assert "TEST_SERVICE_USER=\"telegram-goals-bot-test\"" in workflow
    assert "sudo groupadd --system \"$TEST_SERVICE_GROUP\"" in workflow
    assert "sudo useradd --system --gid \"$TEST_SERVICE_GROUP\"" in workflow
    assert "sudo chown -R \"$TEST_SERVICE_USER:$TEST_SERVICE_GROUP\" \"$TEST_APP_DIR/shared\"" in workflow
    assert "sudo install -m 644 deploy/systemd/telegram-goals-bot-test.service" in workflow
    assert "sudo systemctl daemon-reload" in workflow
    assert "sudo systemctl restart \"$TEST_SERVICE_NAME\"" in workflow


def test_test_systemd_unit_targets_test_app_dir_and_service() -> None:
    unit = TEST_SYSTEMD_UNIT.read_text(encoding="utf-8")

    assert "Description=Telegram Goals Bot Test" in unit
    assert "WorkingDirectory=/opt/telegram_goals_bot_test/current" in unit
    assert "EnvironmentFile=/opt/telegram_goals_bot_test/shared/.env" in unit
    assert "ExecStart=/opt/telegram_goals_bot_test/current/.venv/bin/telegram-goals-bot --env-file /opt/telegram_goals_bot_test/shared/.env run" in unit
    assert "ReadWritePaths=/opt/telegram_goals_bot_test/shared" in unit
    assert "/opt/telegram_goals_bot/current" not in unit


def test_test_systemd_unit_uses_restrictive_umask() -> None:
    unit = TEST_SYSTEMD_UNIT.read_text(encoding="utf-8")

    assert "UMask=0077" in unit
