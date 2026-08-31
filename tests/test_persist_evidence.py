import hashlib
import json
import os
import shutil
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


def evidence_env(run_id, attempt, source_sha="a" * 40, extra=None):
    env = os.environ | {
        "GITHUB_RUN_ID": str(run_id),
        "GITHUB_RUN_ATTEMPT": str(attempt),
        "GITHUB_SHA": source_sha,
    }
    if extra:
        env.update(extra)
    return env


def invoke(repo, run_id, attempt, *, source_sha="a" * 40, extra_env=None, check=True):
    return run(
        "bash",
        "scripts/persist-evidence.sh",
        "live-ingest",
        "artifacts/live.txt",
        "ci: persist evidence",
        cwd=repo,
        env=evidence_env(run_id, attempt, source_sha, extra_env),
        check=check,
    )


def persist(
    repo: Path,
    run_id: int,
    attempt: int,
    payload: str,
    *,
    source_sha: str = "a" * 40,
    extra_env=None,
    check: bool = True,
):
    artifact = repo / "artifacts" / "live.txt"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text(payload, encoding="utf-8")
    return invoke(
        repo,
        run_id,
        attempt,
        source_sha=source_sha,
        extra_env=extra_env,
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


def remote_show(repo, path, ref="origin/main"):
    return run("git", "show", f"{ref}:{path}", cwd=repo).stdout


def mutate_main(repo: Path, mutate):
    remote = run("git", "remote", "get-url", "origin", cwd=repo).stdout.strip()
    mutation_repo = repo.parent / "mutation-repo"
    run("git", "clone", "--branch", "main", remote, str(mutation_repo), cwd=repo.parent)
    run("git", "config", "user.name", "test", cwd=mutation_repo)
    run("git", "config", "user.email", "test@example.com", cwd=mutation_repo)
    mutate(mutation_repo)
    run("git", "add", "-A", cwd=mutation_repo)
    run("git", "commit", "-m", "test: mutate remote state", cwd=mutation_repo)
    run("git", "push", "origin", "HEAD:main", cwd=mutation_repo)


def write_git_wrapper(tmp_path, real_git, body):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    wrapper = bin_dir / "git"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"REAL_GIT={json.dumps(real_git)}\n"
        f"{body}\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    sleep.chmod(0o755)
    return bin_dir


def test_newer_projection_wins_and_each_run_has_a_ref(tmp_path):
    repo = make_repo(tmp_path)
    persist(repo, 200, 1, "newer\n")
    persist(repo, 100, 1, "older\n")
    assert latest(repo)["run_id"] == 200
    assert remote_show(repo, "artifacts/live.txt") == "newer\n"
    refs = run(
        "git", "ls-remote", "--heads", "origin", "refs/heads/evidence/*", cwd=repo
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
    assert remote_show(repo, "artifacts/live.txt") == "attempt two\n"


def test_same_identity_and_payload_is_idempotent_with_optimization(tmp_path):
    repo = make_repo(tmp_path)
    persist(repo, 300, 2, "same\n")
    result = persist(repo, 300, 2, "same\n", extra_env={"PYTHONOPTIMIZE": "1"})
    assert "already exists with identical canonical evidence" in result.stdout
    assert latest(repo)["run_attempt"] == 2


def test_same_identity_with_different_payload_fails_closed(tmp_path):
    repo = make_repo(tmp_path)
    persist(repo, 400, 1, "first\n")
    result = persist(repo, 400, 1, "different\n", check=False)
    assert result.returncode != 0
    assert remote_show(repo, "artifacts/live.txt") == "first\n"


def test_same_identity_with_different_source_sha_fails_closed(tmp_path):
    repo = make_repo(tmp_path)
    persist(repo, 450, 1, "same payload\n", source_sha="a" * 40)
    result = persist(
        repo, 450, 1, "same payload\n", source_sha="b" * 40, check=False
    )
    assert result.returncode != 0


def test_higher_projection_with_string_or_bool_identity_is_rejected(tmp_path):
    for bad_value in ("999", True):
        case = tmp_path / str(bad_value).lower()
        case.mkdir()
        repo = make_repo(case)
        persist(repo, 200, 1, "trusted\n")

        def corrupt(path):
            manifest_path = path / "artifacts/evidence/live-ingest/latest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["run_id"] = bad_value
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        mutate_main(repo, corrupt)
        result = persist(
            repo,
            100,
            1,
            "older\n",
            extra_env={"PYTHONOPTIMIZE": "1"},
            check=False,
        )
        assert result.returncode != 0
        refs = run(
            "git",
            "ls-remote",
            "--heads",
            "origin",
            "refs/heads/evidence/live-ingest/100-1",
            cwd=repo,
        ).stdout
        assert "refs/heads/evidence/live-ingest/100-1" in refs


def test_higher_projection_with_checksum_mismatch_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    persist(repo, 200, 1, "trusted\n")

    def corrupt(path):
        (path / "artifacts/live.txt").write_text("tampered\n", encoding="utf-8")

    mutate_main(repo, corrupt)
    result = persist(repo, 100, 1, "older\n", check=False)
    assert result.returncode != 0


def test_same_key_with_malformed_metadata_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    persist(repo, 200, 1, "trusted\n")

    def corrupt(path):
        manifest_path = path / "artifacts/evidence/live-ingest/latest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source_sha"] = "b" * 40
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    mutate_main(repo, corrupt)
    result = persist(repo, 200, 1, "trusted\n", check=False)
    assert result.returncode != 0


def test_symlink_artifact_and_parent_are_rejected(tmp_path):
    file_case = tmp_path / "file"
    file_case.mkdir()
    repo = make_repo(file_case)
    outside = tmp_path / "outside.txt"
    outside.write_text("private\n", encoding="utf-8")
    artifacts = repo / "artifacts"
    artifacts.mkdir()
    (artifacts / "live.txt").symlink_to(outside)
    result = invoke(repo, 1, 1, check=False)
    assert result.returncode != 0
    assert outside.read_text(encoding="utf-8") == "private\n"

    parent_case = tmp_path / "parent"
    parent_case.mkdir()
    repo = make_repo(parent_case)
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (repo / "artifacts").symlink_to(outside_dir, target_is_directory=True)
    (outside_dir / "live.txt").write_text("private\n", encoding="utf-8")
    result = invoke(repo, 2, 1, check=False)
    assert result.returncode != 0
    assert (outside_dir / "live.txt").read_text(encoding="utf-8") == "private\n"


def test_only_allowlisted_paths_reach_main(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "README.md").write_text("must not persist\n", encoding="utf-8")
    (repo / "secret.txt").write_text("must not persist\n", encoding="utf-8")
    persist(repo, 600, 1, "evidence\n")
    assert remote_show(repo, "README.md") == "initial\n"
    missing = run("git", "show", "origin/main:secret.txt", cwd=repo, check=False)
    assert missing.returncode != 0


def test_non_fast_forward_is_retried(tmp_path):
    repo = make_repo(tmp_path)
    real_git = shutil.which("git")
    marker = tmp_path / "failed-once"
    log = tmp_path / "pushes"
    body = f"""
if [[ "$1" == "push" && "$*" == *":refs/heads/main"* ]]; then
  echo push >> {json.dumps(str(log))}
  if [[ ! -f {json.dumps(str(marker))} ]]; then
    touch {json.dumps(str(marker))}
    exit 1
  fi
fi
exec "$REAL_GIT" "$@"
"""
    bin_dir = write_git_wrapper(tmp_path, real_git, body)
    result = persist(repo, 700, 1, "retry\n", extra_env={"PATH": f"{bin_dir}:{os.environ['PATH']}"})
    assert result.returncode == 0
    assert log.read_text(encoding="utf-8").count("push") == 2
    assert latest(repo)["run_id"] == 700


def test_immutable_ref_is_reverified_after_projection_push_failure(tmp_path):
    repo = make_repo(tmp_path)
    real_git = shutil.which("git")
    remote = run("git", "remote", "get-url", "origin", cwd=repo).stdout.strip()
    marker = tmp_path / "corrupted-once"
    body = f"""
if [[ "$1" == "push" && "$*" == *":refs/heads/main"* && ! -f {json.dumps(str(marker))} ]]; then
  touch {json.dumps(str(marker))}
  "$REAL_GIT" --git-dir={json.dumps(remote)} update-ref \\
    refs/heads/evidence/live-ingest/750-1 refs/heads/main
  exit 1
fi
exec "$REAL_GIT" "$@"
"""
    bin_dir = write_git_wrapper(tmp_path, real_git, body)
    result = persist(
        repo,
        750,
        1,
        "must remain immutable\n",
        extra_env={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        check=False,
    )
    assert result.returncode != 0
    assert "remote path is missing" in result.stderr


def test_post_push_newer_projection_is_verified_as_superseding(tmp_path):
    repo = make_repo(tmp_path)
    real_git = shutil.which("git")
    remote = run("git", "remote", "get-url", "origin", cwd=repo).stdout.strip()
    advance = tmp_path / "advance"
    run("git", "clone", remote, str(advance), cwd=tmp_path)
    run("git", "config", "user.name", "racer", cwd=advance)
    run("git", "config", "user.email", "racer@example.com", cwd=advance)

    higher_payload = "higher concurrent run\n"
    higher_checksum = hashlib.sha256(higher_payload.encode()).hexdigest()
    higher_manifest = {
        "workflow_slug": "live-ingest",
        "run_id": 999,
        "run_attempt": 1,
        "source_sha": "b" * 40,
        "generated_at": "2026-01-01T00:00:00Z",
        "artifact_path": "artifacts/live.txt",
        "checksum_algorithm": "sha256",
        "payload_sha256": higher_checksum,
    }
    injected = tmp_path / "injected"
    injected.mkdir()
    (injected / "live.txt").write_text(higher_payload, encoding="utf-8")
    (injected / "latest.json").write_text(
        json.dumps(higher_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    advance_script = tmp_path / "advance-main.sh"
    advance_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"git -C {json.dumps(str(advance))} fetch origin main\n"
        f"git -C {json.dumps(str(advance))} checkout -B injected origin/main\n"
        f"mkdir -p {json.dumps(str(advance / 'artifacts/evidence/live-ingest'))}\n"
        f"cp {json.dumps(str(injected / 'live.txt'))} "
        f"{json.dumps(str(advance / 'artifacts/live.txt'))}\n"
        f"cp {json.dumps(str(injected / 'latest.json'))} "
        f"{json.dumps(str(advance / 'artifacts/evidence/live-ingest/latest.json'))}\n"
        f"git -C {json.dumps(str(advance))} add artifacts/live.txt "
        "artifacts/evidence/live-ingest/latest.json\n"
        f"git -C {json.dumps(str(advance))} commit -m injected\n"
        f"git -C {json.dumps(str(advance))} push origin HEAD:main\n",
        encoding="utf-8",
    )
    advance_script.chmod(0o755)
    marker = tmp_path / "advanced"
    body = f"""
if [[ "$1" == "push" && "$*" == *":refs/heads/main"* ]]; then
  "$REAL_GIT" "$@"
  status=$?
  if [[ "$status" -eq 0 && ! -f {json.dumps(str(marker))} ]]; then
    touch {json.dumps(str(marker))}
    {json.dumps(str(advance_script))}
  fi
  exit "$status"
fi
exec "$REAL_GIT" "$@"
"""
    bin_dir = write_git_wrapper(tmp_path, real_git, body)
    result = persist(
        repo,
        900,
        1,
        "candidate\n",
        extra_env={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )
    assert result.returncode == 0
    assert "safely superseded" in result.stdout
    assert latest(repo)["run_id"] == 999
    assert remote_show(repo, "artifacts/live.txt") == higher_payload


def test_retry_exhaustion_keeps_immutable_ref(tmp_path):
    repo = make_repo(tmp_path)
    real_git = shutil.which("git")
    log = tmp_path / "pushes"
    body = f"""
if [[ "$1" == "push" && "$*" == *":refs/heads/main"* ]]; then
  echo push >> {json.dumps(str(log))}
  exit 1
fi
exec "$REAL_GIT" "$@"
"""
    bin_dir = write_git_wrapper(tmp_path, real_git, body)
    result = persist(
        repo,
        800,
        1,
        "durable\n",
        extra_env={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        check=False,
    )
    assert result.returncode != 0
    assert log.read_text(encoding="utf-8").count("push") == 8
    refs = run(
        "git",
        "ls-remote",
        "--heads",
        "origin",
        "refs/heads/evidence/live-ingest/800-1",
        cwd=repo,
    ).stdout
    assert "refs/heads/evidence/live-ingest/800-1" in refs
    payload = remote_show(
        repo,
        "artifacts/live.txt",
        "refs/remotes/evidence-verify/live-ingest/800-1",
    )
    assert hashlib.sha256(payload.encode()).hexdigest() == hashlib.sha256(b"durable\n").hexdigest()


def test_invalid_slug_and_paths_are_rejected(tmp_path):
    repo = make_repo(tmp_path)
    artifact = repo / "artifacts" / "live.txt"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text("payload\n", encoding="utf-8")
    env = evidence_env(1, 1)

    def invalid(slug, path):
        return run(
            "bash",
            "scripts/persist-evidence.sh",
            slug,
            path,
            "message",
            cwd=repo,
            env=env,
            check=False,
        )

    assert invalid("../bad", "artifacts/live.txt").returncode != 0
    assert invalid("live-ingest", "artifacts/../README.md").returncode != 0
    assert invalid("live-ingest", "artifacts//live.txt").returncode != 0
    assert invalid("live-ingest", "artifacts/./live.txt").returncode != 0
    reserved = "artifacts/evidence/live-ingest/latest.json"
    assert invalid("live-ingest", reserved).returncode != 0


def test_script_never_uses_assert_or_force_push():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "assert" not in text
    assert "--force" not in text
    assert "--force-with-lease" not in text
