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

[[ "$slug" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "invalid workflow slug" >&2; exit 64; }
[[ "$run_id" =~ ^[0-9]+$ && "$run_attempt" =~ ^[0-9]+$ ]] || { echo "run identity must be numeric" >&2; exit 64; }
[[ "$artifact" =~ ^artifacts/[A-Za-z0-9._/-]+$ && "$artifact" != *".."* ]] || { echo "invalid artifact path" >&2; exit 64; }
[ -f "$artifact" ] || { echo "artifact not found: $artifact" >&2; exit 66; }

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
payload="$work_dir/payload"
cp "$artifact" "$payload"
checksum="$(sha256sum "$payload" | awk '{print $1}')"
generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
record_path="artifacts/evidence/$slug/$run_id-$run_attempt.json"
latest_path="artifacts/evidence/$slug/latest.json"
evidence_ref="refs/heads/evidence/$slug/$run_id-$run_attempt"

write_manifest() {
  local destination="$1"
  mkdir -p "$(dirname "$destination")"
  python - "$destination" "$slug" "$run_id" "$run_attempt" "$source_sha" "$generated_at" "$artifact" "$checksum" <<'PY'
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
Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

verify_ref() {
  local ref="$1"
  local manifest="$2"
  git fetch --no-tags origin "+$ref:refs/remotes/evidence-verify/$slug/$run_id-$run_attempt" >/dev/null 2>&1
  local commit="refs/remotes/evidence-verify/$slug/$run_id-$run_attempt"
  local remote_checksum
  remote_checksum="$(git show "$commit:$artifact" | sha256sum | awk '{print $1}')"
  [ "$remote_checksum" = "$checksum" ] || { echo "remote payload checksum mismatch" >&2; return 1; }
  git show "$commit:$manifest" > "$work_dir/remote-manifest.json"
  python - "$work_dir/remote-manifest.json" "$slug" "$run_id" "$run_attempt" "$artifact" "$checksum" <<'PY'
import json
import sys
from pathlib import Path

path, slug, run_id, run_attempt, artifact, checksum = sys.argv[1:]
value = json.loads(Path(path).read_text(encoding="utf-8"))
assert value["workflow_slug"] == slug
assert value["run_id"] == int(run_id)
assert value["run_attempt"] == int(run_attempt)
assert value["artifact_path"] == artifact
assert value["checksum_algorithm"] == "sha256"
assert value["payload_sha256"] == checksum
PY
}

# Phase 1: persist this accepted run on a collision-free, non-force evidence ref.
git fetch --no-tags origin main
if git ls-remote --exit-code --heads origin "$evidence_ref" >/dev/null 2>&1; then
  verify_ref "$evidence_ref" "$record_path"
  echo "Evidence ref already exists with identical payload: $evidence_ref"
else
  git checkout --detach origin/main
  mkdir -p "$(dirname "$artifact")"
  cp "$payload" "$artifact"
  write_manifest "$record_path"
  git add -- "$artifact" "$record_path"
  git commit -m "$commit_message (run $run_id attempt $run_attempt) [skip ci]"
  evidence_commit="$(git rev-parse HEAD)"
  if ! git push origin "$evidence_commit:$evidence_ref"; then
    git ls-remote --exit-code --heads origin "$evidence_ref" >/dev/null 2>&1 || exit 1
  fi
  verify_ref "$evidence_ref" "$record_path"
fi

# Phase 2: project the newest run for this workflow onto main with optimistic retries.
max_attempts=8
for attempt in $(seq 1 "$max_attempts"); do
  git fetch --no-tags origin main
  git checkout --detach origin/main

  decision="newer"
  if [ -f "$latest_path" ]; then
    decision="$(python - "$latest_path" "$run_id" "$run_attempt" "$checksum" <<'PY'
import json
import sys
from pathlib import Path

path, run_id, run_attempt, checksum = sys.argv[1:]
current = json.loads(Path(path).read_text(encoding="utf-8"))
candidate_key = (int(run_id), int(run_attempt))
current_key = (int(current["run_id"]), int(current["run_attempt"]))
if candidate_key < current_key:
    print("older")
elif candidate_key == current_key:
    print("same" if current["payload_sha256"] == checksum else "conflict")
else:
    print("newer")
PY
)"
  fi

  case "$decision" in
    older)
      echo "A newer main projection already exists; immutable evidence is preserved."
      exit 0
      ;;
    same)
      current_checksum="$(sha256sum "$artifact" | awk '{print $1}')"
      [ "$current_checksum" = "$checksum" ] || { echo "latest artifact checksum mismatch" >&2; exit 1; }
      echo "Main projection already matches this run."
      exit 0
      ;;
    conflict)
      echo "same run identity has a different checksum" >&2
      exit 1
      ;;
    newer) ;;
    *) echo "unknown projection decision: $decision" >&2; exit 1 ;;
  esac

  mkdir -p "$(dirname "$artifact")"
  cp "$payload" "$artifact"
  write_manifest "$latest_path"
  git add -- "$artifact" "$latest_path"
  git commit -m "$commit_message [skip ci]"
  candidate_commit="$(git rev-parse HEAD)"
  if git push origin "$candidate_commit:refs/heads/main"; then
    git fetch --no-tags origin main
    remote_checksum="$(git show origin/main:"$artifact" | sha256sum | awk '{print $1}')"
    [ "$remote_checksum" = "$checksum" ] || { echo "main payload checksum mismatch" >&2; exit 1; }
    git show origin/main:"$latest_path" > "$work_dir/latest.json"
    python - "$work_dir/latest.json" "$run_id" "$run_attempt" "$checksum" <<'PY'
import json
import sys
from pathlib import Path
value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert (value["run_id"], value["run_attempt"], value["payload_sha256"]) == (
    int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
)
PY
    echo "Main projection persisted and verified."
    exit 0
  fi

  sleep $((attempt * 2 + RANDOM % 3))
done

echo "main projection retry budget exhausted; immutable evidence remains at $evidence_ref" >&2
exit 1
