"""E2E tests for scripts/validate-features.py and the FEATURES.json manifest."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "validate-features.py"
FEATURES_FILE = REPO_ROOT / "FEATURES.json"


def run_validate(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *extra_args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


# --- Real manifest validation ---


class TestRealManifest:
    """Validate the actual FEATURES.json shipped with the project."""

    def test_features_json_exists(self):
        assert FEATURES_FILE.exists(), "FEATURES.json must exist in the repo root"

    def test_features_json_is_valid_json(self):
        data = json.loads(FEATURES_FILE.read_text(encoding="utf-8"))
        assert "features" in data
        assert isinstance(data["features"], list)

    def test_all_critical_files_exist(self):
        data = json.loads(FEATURES_FILE.read_text(encoding="utf-8"))
        for feature in data["features"]:
            for filepath in feature.get("critical_files", []):
                full_path = REPO_ROOT / filepath
                assert full_path.exists(), (
                    f"Feature '{feature['id']}' declares critical file "
                    f"'{filepath}' but it does not exist"
                )

    def test_validate_script_passes_on_real_manifest(self):
        result = run_validate()
        assert result.returncode == 0, f"Validation failed:\n{result.stdout}"
        assert "all OK" in result.stdout

    def test_validate_script_quiet_mode(self):
        result = run_validate("--quiet")
        assert result.returncode == 0
        assert result.stdout == ""


# --- Synthetic manifest tests (use tmp_path to isolate) ---


@pytest.fixture()
def fake_repo(tmp_path):
    """Create a minimal repo structure with a copy of the validation script."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()

    # Copy the validation script but patch REPO_ROOT to point to tmp_path
    script_text = SCRIPT.read_text(encoding="utf-8")
    patched = script_text.replace(
        "REPO_ROOT = Path(__file__).resolve().parent.parent",
        f'REPO_ROOT = Path(r"{tmp_path}")',
    )
    (scripts_dir / "validate-features.py").write_text(patched, encoding="utf-8")

    return tmp_path


def run_fake_validate(fake_repo: Path, *extra_args: str) -> subprocess.CompletedProcess:
    script = fake_repo / "scripts" / "validate-features.py"
    return subprocess.run(
        [sys.executable, str(script), *extra_args],
        capture_output=True,
        text=True,
        cwd=str(fake_repo),
    )


class TestMissingManifest:
    def test_fails_when_features_json_missing(self, fake_repo):
        result = run_fake_validate(fake_repo)
        assert result.returncode == 1


class TestMalformedManifest:
    def test_fails_on_invalid_json(self, fake_repo):
        (fake_repo / "FEATURES.json").write_text("not json{{{", encoding="utf-8")
        result = run_fake_validate(fake_repo)
        assert result.returncode == 1

    def test_fails_when_features_key_missing(self, fake_repo):
        (fake_repo / "FEATURES.json").write_text('{"version": 1}', encoding="utf-8")
        result = run_fake_validate(fake_repo)
        assert result.returncode == 1

    def test_fails_when_features_is_not_array(self, fake_repo):
        (fake_repo / "FEATURES.json").write_text(
            '{"features": "not-a-list"}', encoding="utf-8"
        )
        result = run_fake_validate(fake_repo)
        assert result.returncode == 1


class TestFeatureEntryValidation:
    def test_fails_on_missing_required_keys(self, fake_repo):
        manifest = {"features": [{"id": "test"}]}
        (fake_repo / "FEATURES.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = run_fake_validate(fake_repo)
        assert result.returncode == 1
        assert "missing required keys" in result.stdout

    def test_fails_on_duplicate_feature_ids(self, fake_repo):
        (fake_repo / "a.py").touch()
        manifest = {
            "features": [
                {"id": "dup", "name": "First", "critical_files": ["a.py"]},
                {"id": "dup", "name": "Second", "critical_files": ["a.py"]},
            ]
        }
        (fake_repo / "FEATURES.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = run_fake_validate(fake_repo)
        assert result.returncode == 1
        assert "duplicate" in result.stdout.lower()

    def test_fails_on_missing_critical_file(self, fake_repo):
        manifest = {
            "features": [
                {"id": "test", "name": "Test", "critical_files": ["does_not_exist.py"]}
            ]
        }
        (fake_repo / "FEATURES.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = run_fake_validate(fake_repo)
        assert result.returncode == 1
        assert "critical file missing" in result.stdout

    def test_fails_when_api_endpoints_not_array(self, fake_repo):
        (fake_repo / "a.py").touch()
        manifest = {
            "features": [
                {
                    "id": "test",
                    "name": "Test",
                    "critical_files": ["a.py"],
                    "api_endpoints": "not-a-list",
                }
            ]
        }
        (fake_repo / "FEATURES.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = run_fake_validate(fake_repo)
        assert result.returncode == 1

    def test_passes_valid_manifest(self, fake_repo):
        (fake_repo / "main.py").touch()
        manifest = {
            "version": 1,
            "features": [
                {
                    "id": "test-feature",
                    "name": "Test Feature",
                    "critical_files": ["main.py"],
                    "api_endpoints": ["/test"],
                }
            ],
        }
        (fake_repo / "FEATURES.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = run_fake_validate(fake_repo)
        assert result.returncode == 0
        assert "all OK" in result.stdout

    def test_passes_with_multiple_features(self, fake_repo):
        (fake_repo / "a.py").touch()
        (fake_repo / "b.py").touch()
        manifest = {
            "features": [
                {"id": "feat-a", "name": "A", "critical_files": ["a.py"]},
                {"id": "feat-b", "name": "B", "critical_files": ["b.py"]},
            ]
        }
        (fake_repo / "FEATURES.json").write_text(json.dumps(manifest), encoding="utf-8")
        result = run_fake_validate(fake_repo)
        assert result.returncode == 0


class TestPreCommitHook:
    def test_hook_file_exists(self):
        hook = REPO_ROOT / ".git" / "hooks" / "pre-commit"
        assert hook.exists(), "pre-commit hook must be installed"

    def test_hook_calls_validate_script(self):
        hook = REPO_ROOT / ".git" / "hooks" / "pre-commit"
        content = hook.read_text(encoding="utf-8")
        assert "validate-features.py" in content
