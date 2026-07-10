from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 compatibility.
    import tomli as tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


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
