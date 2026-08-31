#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <workflow-slug> <artifact-path> <commit-message>" >&2
  exit 64
fi

slug="$1"
artifact="$2"
commit_message="$3"
run_id="${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"
run_attempt="${GITHUB_RUN_ATTEMPT:?GITHUB_RUN_ATTEMPT is required}"
source_sha="${GITHUB_SHA:?GITHUB_SHA is required}"

[[ "$slug" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || {
  echo "invalid workflow slug" >&2
  exit 64
}
[[ "$run_id" =~ ^[0-9]+$ && "$run_attempt" =~ ^[0-9]+$ ]] || {
  echo "run identity must be numeric" >&2
  exit 64
}
[[ "$source_sha" =~ ^[0-9a-fA-F]{40}$ ]] || {
  echo "source SHA must be a 40-character hexadecimal commit ID" >&2
  exit 64
}
[[ "$artifact" =~ ^artifacts/[A-Za-z0-9._/-]+$ ]] || {
  echo "invalid artifact path" >&2
  exit 64
}
python - "$artifact" <<'PY'
import sys
from pathlib import PurePosixPath
raw = sys.argv[1]
path = PurePosixPath(raw)
parts = path.parts
valid = (
    path.as_posix() == raw
    and len(parts) >= 2
    and parts[0] == "artifacts"
    and all(part not in {"", ".", ".."} for part in parts)
    and parts[1] != "evidence"
)
if not valid:
    raise SystemExit("artifact path must be canonical and outside artifacts/evidence")
PY

repo_root="$(git rev-parse --show-toplevel)"
record_path="artifacts/evidence/$slug/$run_id-$run_attempt.json"
latest_path="artifacts/evidence/$slug/latest.json"
evidence_ref="refs/heads/evidence/$slug/$run_id-$run_attempt"
work_dir="$(mktemp -d)"
chmod 700 "$work_dir"
worktrees=()
cleanup() {
  local tree
  for tree in "${worktrees[@]}"; do
    if [ -d "$tree" ]; then
      git -C "$tree" reset --hard HEAD >/dev/null 2>&1 || true
      git -C "$repo_root" worktree remove "$tree" >/dev/null 2>&1 || true
    fi
  done
  rm -rf "$work_dir"
}
trap cleanup EXIT

validate_repo_path() {
  local root="$1"
  local target="$2"
  local require_file="$3"
  python - "$root" "$target" "$require_file" <<'PY'
import os
import stat
import sys
from pathlib import Path
repo = Path(sys.argv[1]).resolve(strict=True)
relative = Path(sys.argv[2])
candidate = repo / relative
require_file = sys.argv[3] == "yes"
current = repo
for part in relative.parts:
    if current.is_symlink():
        raise SystemExit(f"symlink is not allowed in repository path: {current}")
    current = current / part
if current.is_symlink():
    raise SystemExit(f"symlink file is not allowed: {current}")
existing_parent = candidate.parent
while not existing_parent.exists():
    existing_parent = existing_parent.parent
if not existing_parent.resolve(strict=True).is_relative_to(repo):
    raise SystemExit("repository path resolves outside repository root")
if require_file:
    info = os.lstat(candidate)
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit("repository path must be a regular file")
PY
}

validate_artifact_path() {
  local root="$1"
  local require_file="$2"
  validate_repo_path "$root" "$artifact" "$require_file"
  python - "$root" "$artifact" <<'PY'
import sys
from pathlib import Path
repo = Path(sys.argv[1]).resolve(strict=True)
candidate = repo / Path(sys.argv[2])
artifacts_root = repo / "artifacts"
existing_parent = candidate.parent
while not existing_parent.exists():
    existing_parent = existing_parent.parent
if artifacts_root.exists():
    resolved_root = artifacts_root.resolve(strict=True)
    if not existing_parent.resolve(strict=True).is_relative_to(resolved_root):
        raise SystemExit("artifact parent resolves outside artifacts root")
elif existing_parent != repo:
    raise SystemExit("unexpected artifact parent")
PY
}

validate_artifact_path "$repo_root" yes
input_checksum="$(sha256sum "$repo_root/$artifact" | awk '{print $1}')"
payload="$work_dir/payload"
cp -- "$repo_root/$artifact" "$payload"
validate_artifact_path "$repo_root" yes
checksum="$(sha256sum "$payload" | awk '{print $1}')"
post_copy_checksum="$(sha256sum "$repo_root/$artifact" | awk '{print $1}')"
[[ "$input_checksum" = "$checksum" && "$checksum" = "$post_copy_checksum" ]] || {
  echo "artifact changed while the immutable payload was captured" >&2
  exit 1
}
python - "$payload" <<'PY'
import os
import stat
import sys
info = os.lstat(sys.argv[1])
if not stat.S_ISREG(info.st_mode):
    raise SystemExit("captured payload must be a regular file")
PY
generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

create_worktree() {
  local tree="$1"
  local ref="$2"
  git worktree add --detach "$tree" "$ref" >/dev/null
  worktrees+=("$tree")
}

remove_worktree() {
  local tree="$1"
  git -C "$tree" reset --hard HEAD >/dev/null 2>&1 || true
  git worktree remove "$tree"
}

write_manifest() {
  local root="$1"
  local destination="$2"
  validate_repo_path "$root" "$destination" no
  mkdir -p "$(dirname "$root/$destination")"
  python - "$root/$destination" "$slug" "$run_id" "$run_attempt" \
    "$source_sha" "$generated_at" "$artifact" "$checksum" <<'PY'
import json
import sys
from pathlib import Path
path, slug, run_id, run_attempt, source_sha, generated_at, artifact, checksum = sys.argv[1:]
value = {
    "workflow_slug": slug,
    "run_id": int(run_id),
    "run_attempt": int(run_attempt),
    "source_sha": source_sha,
    "generated_at": generated_at,
    "artifact_path": artifact,
    "checksum_algorithm": "sha256",
    "payload_sha256": checksum,
}
Path(path).write_text(
    json.dumps(value, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
}

classify_manifest() {
  local manifest="$1"
  local actual_checksum="$2"
  python - "$manifest" "$slug" "$run_id" "$run_attempt" \
    "$source_sha" "$artifact" "$checksum" "$actual_checksum" <<'PY'
import json
import re
import sys
from datetime import datetime
from pathlib import Path
path, slug, run_id, run_attempt, source_sha, artifact, checksum, actual = sys.argv[1:]
required = {
    "workflow_slug",
    "run_id",
    "run_attempt",
    "source_sha",
    "generated_at",
    "artifact_path",
    "checksum_algorithm",
    "payload_sha256",
}
try:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    valid = isinstance(value, dict) and set(value) == required
    valid = valid and type(value.get("run_id")) is int
    valid = valid and type(value.get("run_attempt")) is int
    valid = valid and value.get("workflow_slug") == slug
    valid = valid and value.get("artifact_path") == artifact
    valid = valid and value.get("checksum_algorithm") == "sha256"
    valid = valid and isinstance(value.get("source_sha"), str)
    valid = valid and re.fullmatch(r"[0-9a-fA-F]{40}", value.get("source_sha", "")) is not None
    valid = valid and isinstance(value.get("generated_at"), str)
    if valid:
        datetime.strptime(value["generated_at"], "%Y-%m-%dT%H:%M:%SZ")
    valid = valid and isinstance(value.get("payload_sha256"), str)
    valid = valid and re.fullmatch(r"[0-9a-f]{64}", value.get("payload_sha256", "")) is not None
    valid = valid and value.get("payload_sha256") == actual
except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
    valid = False
if not valid:
    raise SystemExit("manifest or artifact consistency validation failed")
current_key = (value["run_id"], value["run_attempt"])
candidate_key = (int(run_id), int(run_attempt))
if current_key > candidate_key:
    print("superseded")
elif current_key == candidate_key:
    if value["source_sha"] == source_sha and value["payload_sha256"] == checksum:
        print("exact")
    else:
        print("conflict")
else:
    print("stale")
PY
}

remote_blob_checksum() {
  local ref="$1"
  local path="$2"
  local entry mode type
  entry="$(git ls-tree "$ref" -- "$path")"
  read -r mode type _ <<< "$entry"
  [[ "$type" = "blob" && ( "$mode" = "100644" || "$mode" = "100755" ) ]] || {
    echo "remote path is missing or is not a regular blob: $path" >&2
    return 1
  }
  git show "$ref:$path" | sha256sum | awk '{print $1}'
}

verify_ref() {
  local ref="$1"
  local manifest="$2"
  local remote_ref="refs/remotes/evidence-verify/$slug/$run_id-$run_attempt"
  git fetch --no-tags origin "+$ref:$remote_ref" >/dev/null 2>&1
  local remote_checksum result
  remote_checksum="$(remote_blob_checksum "$remote_ref" "$artifact")"
  remote_blob_checksum "$remote_ref" "$manifest" >/dev/null
  git show "$remote_ref:$manifest" > "$work_dir/remote-manifest.json"
  result="$(classify_manifest "$work_dir/remote-manifest.json" "$remote_checksum")"
  [ "$result" = "exact" ] || {
    echo "remote immutable evidence is not an exact canonical match: $result" >&2
    return 1
  }
}

verify_staging() {
  local tree="$1"
  local first="$2"
  local second="$3"
  git -C "$tree" diff --cached --name-only -z > "$work_dir/staged-paths"
  python - "$work_dir/staged-paths" "$first" "$second" <<'PY'
import sys
from pathlib import Path
actual = Path(sys.argv[1]).read_bytes().split(b"\0")
actual = [item.decode() for item in actual if item]
expected = sorted(sys.argv[2:])
if sorted(actual) != expected or len(actual) != len(expected):
    raise SystemExit(f"staged path allowlist violation: {actual!r}")
PY
}

git fetch --no-tags origin main
if git ls-remote --exit-code --heads origin "$evidence_ref" >/dev/null 2>&1; then
  verify_ref "$evidence_ref" "$record_path"
  echo "Evidence ref already exists with identical canonical evidence: $evidence_ref"
else
  evidence_tree="$work_dir/evidence-tree"
  create_worktree "$evidence_tree" origin/main
  validate_artifact_path "$evidence_tree" no
  validate_repo_path "$evidence_tree" "$record_path" no
  mkdir -p "$(dirname "$evidence_tree/$artifact")"
  cp -- "$payload" "$evidence_tree/$artifact"
  write_manifest "$evidence_tree" "$record_path"
  git -C "$evidence_tree" add -- "$artifact" "$record_path"
  verify_staging "$evidence_tree" "$artifact" "$record_path"
  git -C "$evidence_tree" commit \
    -m "$commit_message (run $run_id attempt $run_attempt) [skip ci]"
  evidence_commit="$(git -C "$evidence_tree" rev-parse HEAD)"
  if ! git push origin "$evidence_commit:$evidence_ref"; then
    git ls-remote --exit-code --heads origin "$evidence_ref" >/dev/null 2>&1 || exit 1
  fi
  verify_ref "$evidence_ref" "$record_path"
  remove_worktree "$evidence_tree"
fi

max_attempts=8
for attempt in $(seq 1 "$max_attempts"); do
  verify_ref "$evidence_ref" "$record_path"
  git fetch --no-tags origin main
  projection_tree="$work_dir/projection-tree-$attempt"
  create_worktree "$projection_tree" origin/main
  decision="stale"
  if [ -e "$projection_tree/$latest_path" ]; then
    validate_repo_path "$projection_tree" "$latest_path" yes
    validate_artifact_path "$projection_tree" yes
    current_checksum="$(sha256sum "$projection_tree/$artifact" | awk '{print $1}')"
    decision="$(classify_manifest "$projection_tree/$latest_path" "$current_checksum")"
  fi
  case "$decision" in
    superseded)
      echo "A newer verified main projection already exists; immutable evidence is preserved."
      exit 0
      ;;
    exact)
      echo "Main projection already exactly matches this run."
      exit 0
      ;;
    conflict)
      echo "same run identity has different canonical evidence" >&2
      exit 1
      ;;
    stale) ;;
    *)
      echo "unknown projection decision: $decision" >&2
      exit 1
      ;;
  esac
  validate_artifact_path "$projection_tree" no
  validate_repo_path "$projection_tree" "$latest_path" no
  mkdir -p "$(dirname "$projection_tree/$artifact")"
  cp -- "$payload" "$projection_tree/$artifact"
  write_manifest "$projection_tree" "$latest_path"
  git -C "$projection_tree" add -- "$artifact" "$latest_path"
  verify_staging "$projection_tree" "$artifact" "$latest_path"
  git -C "$projection_tree" commit -m "$commit_message [skip ci]"
  candidate_commit="$(git -C "$projection_tree" rev-parse HEAD)"
  if git push origin "$candidate_commit:refs/heads/main"; then
    git fetch --no-tags origin main
    remote_checksum="$(remote_blob_checksum origin/main "$artifact")"
    remote_blob_checksum origin/main "$latest_path" >/dev/null
    git show origin/main:"$latest_path" > "$work_dir/latest.json"
    post_push_decision="$(classify_manifest "$work_dir/latest.json" "$remote_checksum")"
    case "$post_push_decision" in
      exact)
        echo "Main projection persisted and verified."
        exit 0
        ;;
      superseded)
        echo "Main projection was safely superseded by a newer verified projection."
        exit 0
        ;;
      conflict)
        echo "same run identity has different post-push canonical evidence" >&2
        exit 1
        ;;
      stale)
        echo "main regressed to an older projection after a successful push" >&2
        exit 1
        ;;
      *)
        echo "unknown post-push decision: $post_push_decision" >&2
        exit 1
        ;;
    esac
  fi
  remove_worktree "$projection_tree"
  sleep $((attempt * 2 + RANDOM % 3))
done

echo "main projection retry budget exhausted; immutable evidence remains at $evidence_ref" >&2
exit 1
