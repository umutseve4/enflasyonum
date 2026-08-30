import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "persist-evidence.sh"


def run(*args, cwd, env=None, check=True):
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=check,
        text=True,
        capture_output=True,
    )


def make_repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    run("git", "init", "--bare", str(remote), cwd=tmp_path)
    run("git", "init", "-b", "main", str(repo), cwd=tmp_path)
    run("git", "config", "user.name", "test", cwd=repo)
    run("git", "config", "user.email", "test@example.com", cwd=repo)
    (repo / "README.md").write_text("initial\n", encoding="utf-8")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "persist-evidence.sh").write_bytes(SCRIPT.read_bytes())
    run("git", "add", ".", cwd=repo)
    run("git", "commit", "-m", "initial", cwd=repo)
    run("git", "remote", "add", "origin", str(remote), cwd=repo)
    run("git", "push", "-u", "origin", "main", cwd=repo)
    return repo


def persist(
    repo: Path,
    run_id: int,
    attempt: int,
    payload: str,
    *,
    source_sha: str = "a" * 40,
    check: bool = True,
):
    artifact = repo / "artifacts" / "live.txt"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text(payload, encoding="utf-8")
    env = os.environ | {
        "GITHUB_RUN_ID": str(run_id),
        "GITHUB_RUN_ATTEMPT": str(attempt),
        "GITHUB_SHA": source_sha,
    }
    return run(
        "bash",
        "scripts/persist-evidence.sh",
        "live-ingest",
        "artifacts/live.txt",
        "ci: persist evidence",
        cwd=repo,
        env=env,
        check=check,
    )


def latest(repo: Path):
    raw = run(
        "git",
        "show",
        "origin/main:artifacts/evidence/live-ingest/latest.json",
        cwd=repo,
    ).stdout
    return json.loads(raw)


def test_newer_projection_wins_and_each_run_has_a_ref(tmp_path):
    repo = make_repo(tmp_path)
    persist(repo, 200, 1, "newer\n")
    persist(repo, 100, 1, "older\n")

    assert latest(repo)["run_id"] == 200
    artifact = run("git", "show", "origin/main:artifacts/live.txt", cwd=repo).stdout
    assert artifact == "newer\n"
    refs = run(
        "git",
        "ls-remote",
        "--heads",
        "origin",
        "refs/heads/evidence/*",
        cwd=repo,
    ).stdout
    assert "refs/heads/evidence/live-ingest/200-1" in refs
    assert "refs/heads/evidence/live-ingest/100-1" in refs


def test_run_attempt_breaks_ties(tmp_path):
    repo = make_repo(tmp_path)
    persist(repo, 500, 1, "attempt one\n")
    persist(repo, 500, 2, "attempt two\n")
    persist(repo, 500, 1, "attempt one\n")

    assert latest(repo)["run_id"] == 500
    assert latest(repo)["run_attempt"] == 2
    artifact = run("git", "show", "origin/main:artifacts/live.txt", cwd=repo).stdout
    assert artifact == "attempt two\n"


def test_same_identity_and_payload_is_idempotent(tmp_path):
    repo = make_repo(tmp_path)
    persist(repo, 300, 2, "same\n")
    result = persist(repo, 300, 2, "same\n")
    assert "already exists with identical payload" in result.stdout
    assert latest(repo)["run_attempt"] == 2


def test_same_identity_with_different_payload_fails_closed(tmp_path):
    repo = make_repo(tmp_path)
    persist(repo, 400, 1, "first\n")
    result = persist(repo, 400, 1, "different\n", check=False)
    assert result.returncode != 0
    artifact = run("git", "show", "origin/main:artifacts/live.txt", cwd=repo).stdout
    assert artifact == "first\n"


def test_invalid_slug_and_traversal_are_rejected(tmp_path):
    repo = make_repo(tmp_path)
    artifact = repo / "artifacts" / "live.txt"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text("payload\n", encoding="utf-8")
    env = os.environ | {
        "GITHUB_RUN_ID": "1",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "a" * 40,
    }
    invalid_slug = run(
        "bash",
        "scripts/persist-evidence.sh",
        "../bad",
        "artifacts/live.txt",
        "message",
        cwd=repo,
        env=env,
        check=False,
    )
    traversal = run(
        "bash",
        "scripts/persist-evidence.sh",
        "live-ingest",
        "artifacts/../README.md",
        "message",
        cwd=repo,
        env=env,
        check=False,
    )
    assert invalid_slug.returncode == 64
    assert traversal.returncode == 64


def test_script_never_uses_force_push():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--force" not in text
    assert "--force-with-lease" not in text
