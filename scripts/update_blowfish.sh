#!/usr/bin/env bash
set -euo pipefail

# Physical path so it compares equal to `git rev-parse --show-toplevel`.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
THEME_DIR="$REPO_ROOT/themes/blowfish"
LAYOUTS_DIR="$REPO_ROOT/layouts"

CHANGED_FILES=()
CHANGE_TYPES=()

die() {
  printf '%s\n' "$@" >&2
  exit 1
}

theme_git() {
  git -C "$THEME_DIR" "$@"
}

# An uninitialized submodule resolves to the parent repository, so verify that
# THEME_DIR is the root of its own work tree before running any git command.
check_theme_repo() {
  local toplevel
  toplevel=$(theme_git rev-parse --show-toplevel 2>/dev/null) || toplevel=""
  if [[ "$toplevel" != "$THEME_DIR" ]]; then
    die "Blowfish submodule is not initialized: $THEME_DIR" \
      "Run 'git submodule update --init themes/blowfish' first."
  fi
  if [[ -n $(theme_git status --porcelain --untracked-files=no) ]]; then
    die "Blowfish submodule has uncommitted changes: $THEME_DIR"
  fi
}

# Prints the highest release tag, ignoring pre-releases such as v3.0.0-beta.1.
latest_version_tag() {
  theme_git tag --list 'v[0-9]*' --sort=-v:refname |
    awk '/^v[0-9]+(\.[0-9]+)*$/ && !found { print; found = 1 }'
}

# Prints the commit for a ref, preferring tags and then the remote-tracking
# branch so that a stale local branch is not used.
resolve_commit() {
  local ref=$1 candidate
  for candidate in "refs/tags/$ref" "refs/remotes/origin/$ref" "$ref"; do
    if theme_git rev-parse --quiet --verify "${candidate}^{commit}"; then
      return 0
    fi
  done
  return 1
}

upstream_has() {
  theme_git cat-file -e "$1:layouts/$2" 2>/dev/null
}

collect_changes() {
  local file rel_path change_type label

  while IFS= read -r file; do
    rel_path=${file#"$LAYOUTS_DIR/"}
    if upstream_has "$CURRENT_COMMIT" "$rel_path"; then
      if upstream_has "$TARGET_COMMIT" "$rel_path"; then
        if theme_git diff --quiet "$CURRENT_COMMIT" "$TARGET_COMMIT" -- "layouts/$rel_path"; then
          continue
        fi
        change_type=changed
        label="CHANGED"
      else
        change_type=removed
        label="REMOVED UPSTREAM"
      fi
    elif upstream_has "$TARGET_COMMIT" "$rel_path"; then
      change_type=added
      label="ADDED UPSTREAM"
    else
      continue
    fi

    CHANGED_FILES+=("$rel_path")
    CHANGE_TYPES+=("$change_type")
    echo "$label: layouts/$rel_path"
  done < <(find "$LAYOUTS_DIR" -type f | sort)
}

merge_upstream() {
  local rel_path=$1 custom_file=$2 status=0

  theme_git show "$CURRENT_COMMIT:layouts/$rel_path" > "$WORK_DIR/base"
  theme_git show "$TARGET_COMMIT:layouts/$rel_path" > "$WORK_DIR/new"
  git merge-file -L "layouts/$rel_path" -L "$CURRENT_VERSION" -L "$TARGET_REF" \
    "$custom_file" "$WORK_DIR/base" "$WORK_DIR/new" || status=$?

  # git merge-file exits with the conflict count (at most 127) or 255 on error.
  if (( status == 0 )); then
    echo "✓ Merged cleanly."
  elif (( status <= 127 )); then
    echo "⚠ Merge conflicts detected in $custom_file — resolve manually."
  else
    echo "✗ git merge-file failed for $custom_file (exit $status)." >&2
  fi
}

review_file() {
  local rel_path=$1 change_type=$2
  local custom_file="$LAYOUTS_DIR/$rel_path" choice

  echo "────────────────────────────────────────"
  echo "File: layouts/$rel_path"
  echo "────────────────────────────────────────"
  echo "Upstream diff ($CURRENT_VERSION → $TARGET_REF):"
  theme_git diff "$CURRENT_COMMIT" "$TARGET_COMMIT" -- "layouts/$rel_path"
  echo ""

  if [[ "$change_type" != changed ]]; then
    echo "Automatic merge unavailable: the upstream file was $change_type. Review manually."
    echo ""
    return
  fi

  while true; do
    # Treat end of input as "skip" so the remaining files are still reported.
    if ! read -rp "Merge upstream changes into your custom file? [y/n/d(iff)] " choice; then
      choice=""
      echo ""
    fi
    case "$choice" in
      y|Y)
        merge_upstream "$rel_path" "$custom_file"
        break
        ;;
      d|D)
        theme_git show "$TARGET_COMMIT:layouts/$rel_path" > "$WORK_DIR/new"
        echo "Diff between your custom file and new upstream:"
        git diff --no-index -- "$custom_file" "$WORK_DIR/new" || true
        ;;
      *)
        echo "Skipped."
        break
        ;;
    esac
  done
  echo ""
}

main() {
  local target_explicit=false index

  if (( $# > 1 )); then
    echo "Usage: $0 [target-ref]" >&2
    exit 2
  fi

  check_theme_repo
  WORK_DIR=$(mktemp -d)
  trap 'rm -rf "$WORK_DIR"' EXIT

  # Step 1: Resolve the current and target revisions.
  CURRENT_COMMIT=$(theme_git rev-parse HEAD)
  CURRENT_VERSION=$(theme_git describe --tags --exact-match 2>/dev/null || theme_git rev-parse --short HEAD)
  echo "Current Blowfish version: $CURRENT_VERSION"

  theme_git fetch --tags origin
  if (( $# == 1 )); then
    TARGET_REF=$1
    target_explicit=true
  else
    TARGET_REF=$(latest_version_tag)
  fi

  if [[ -z "$TARGET_REF" ]] || ! TARGET_COMMIT=$(resolve_commit "$TARGET_REF"); then
    die "Blowfish target ref not found: ${TARGET_REF:-<none>}"
  fi
  echo "Target Blowfish version: $TARGET_REF"

  if [[ "$CURRENT_COMMIT" == "$TARGET_COMMIT" ]]; then
    echo "Already up to date."
    exit 0
  fi

  if [[ "$target_explicit" == false ]]; then
    if theme_git merge-base --is-ancestor "$TARGET_COMMIT" "$CURRENT_COMMIT"; then
      echo "Current revision is newer than the latest version tag; no update performed."
      exit 0
    fi
    if ! theme_git merge-base --is-ancestor "$CURRENT_COMMIT" "$TARGET_COMMIT"; then
      die "Latest version tag is not a fast-forward from the current revision: $TARGET_REF" \
        "Specify a target ref explicitly after reviewing the upstream history."
    fi
  fi

  # Step 2: Check which custom layouts changed upstream.
  echo ""
  echo "=== Checking custom layouts for upstream changes ==="
  collect_changes

  # Step 3: Update the submodule to the requested revision.
  echo ""
  echo "=== Updating submodule to $TARGET_REF ==="
  theme_git checkout --detach "$TARGET_COMMIT"

  if (( ${#CHANGED_FILES[@]} == 0 )); then
    echo ""
    echo "No custom layouts were affected by this update."
    echo "Done! Run 'hugo', then 'git add themes/blowfish && git commit' to finalize."
    exit 0
  fi

  # Step 4: Show diffs and offer three-way merges where both upstream versions exist.
  echo ""
  echo "=== ${#CHANGED_FILES[@]} custom layout(s) have upstream changes ==="
  echo ""
  for index in "${!CHANGED_FILES[@]}"; do
    review_file "${CHANGED_FILES[$index]}" "${CHANGE_TYPES[$index]}"
  done

  echo "=== Update complete ==="
  echo "Review changes, then run:"
  echo "  hugo"
  echo "  git add themes/blowfish layouts/"
  echo "  git commit -m 'chore: update Blowfish theme to $TARGET_REF'"
}

main "$@"
