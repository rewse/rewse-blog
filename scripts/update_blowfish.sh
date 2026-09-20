#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
THEME_DIR="$REPO_ROOT/themes/blowfish"
LAYOUTS_DIR="$REPO_ROOT/layouts"

if [ "$#" -gt 1 ]; then
  echo "Usage: $0 [target-ref]" >&2
  exit 2
fi

# Step 1: Resolve the current and target revisions.
cd "$THEME_DIR"
CURRENT_COMMIT=$(git rev-parse HEAD)
CURRENT_VERSION=$(git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD)
echo "Current Blowfish version: $CURRENT_VERSION"

git fetch --tags
TARGET_EXPLICIT=false
if [ "$#" -eq 1 ]; then
  TARGET_REF=$1
  TARGET_EXPLICIT=true
else
  TARGET_REF=$(git tag --list 'v[0-9]*' --sort=-v:refname | head -1)
fi

if [ -z "$TARGET_REF" ] || ! TARGET_COMMIT=$(git rev-parse --verify "${TARGET_REF}^{commit}" 2>/dev/null); then
  echo "Blowfish target ref not found: ${TARGET_REF:-<none>}" >&2
  exit 1
fi

echo "Target Blowfish version: $TARGET_REF"

if [ "$CURRENT_COMMIT" = "$TARGET_COMMIT" ]; then
  echo "Already up to date."
  exit 0
fi

if [ "$TARGET_EXPLICIT" = false ]; then
  if git merge-base --is-ancestor "$TARGET_COMMIT" "$CURRENT_COMMIT"; then
    echo "Current revision is newer than the latest version tag; no update performed."
    exit 0
  fi
  if ! git merge-base --is-ancestor "$CURRENT_COMMIT" "$TARGET_COMMIT"; then
    echo "Latest version tag is not a fast-forward from the current revision: $TARGET_REF" >&2
    echo "Specify a target ref explicitly after reviewing the upstream history." >&2
    exit 1
  fi
fi

# Step 2: Check which custom layouts changed upstream.
echo ""
echo "=== Checking custom layouts for upstream changes ==="
CHANGED_FILES=()
CHANGE_TYPES=()

while IFS= read -r file; do
  rel_path="${file#"$LAYOUTS_DIR/"}"
  old_path="$CURRENT_COMMIT:layouts/$rel_path"
  new_path="$TARGET_COMMIT:layouts/$rel_path"
  old_exists=false
  new_exists=false

  if git cat-file -e "$old_path" 2>/dev/null; then
    old_exists=true
  fi
  if git cat-file -e "$new_path" 2>/dev/null; then
    new_exists=true
  fi

  if [ "$old_exists" = false ] && [ "$new_exists" = false ]; then
    continue
  fi
  if [ "$old_exists" = true ] && [ "$new_exists" = true ] && \
      git diff --quiet "$CURRENT_COMMIT" "$TARGET_COMMIT" -- "layouts/$rel_path"; then
    continue
  fi

  CHANGED_FILES+=("$rel_path")
  if [ "$old_exists" = false ]; then
    CHANGE_TYPES+=("added")
    echo "ADDED UPSTREAM: layouts/$rel_path"
  elif [ "$new_exists" = false ]; then
    CHANGE_TYPES+=("removed")
    echo "REMOVED UPSTREAM: layouts/$rel_path"
  else
    CHANGE_TYPES+=("changed")
    echo "CHANGED: layouts/$rel_path"
  fi
done < <(find "$LAYOUTS_DIR" -type f -name "*.html" | sort)

# Step 3: Update the submodule to the requested revision.
echo ""
echo "=== Updating submodule to $TARGET_REF ==="
git checkout --detach "$TARGET_COMMIT"
cd "$REPO_ROOT"

if [ ${#CHANGED_FILES[@]} -eq 0 ]; then
  echo ""
  echo "No custom layouts were affected by this update."
  echo "Done! Run 'git add themes/blowfish && git commit' to finalize."
  exit 0
fi

# Step 4: Show diffs and offer three-way merges where both upstream versions exist.
echo ""
echo "=== ${#CHANGED_FILES[@]} custom layout(s) have upstream changes ==="
echo ""

for index in "${!CHANGED_FILES[@]}"; do
  rel_path=${CHANGED_FILES[$index]}
  change_type=${CHANGE_TYPES[$index]}
  custom_file="$LAYOUTS_DIR/$rel_path"

  echo "────────────────────────────────────────"
  echo "File: layouts/$rel_path"
  echo "────────────────────────────────────────"
  echo "Upstream diff ($CURRENT_VERSION → $TARGET_REF):"
  cd "$THEME_DIR"
  git diff "$CURRENT_COMMIT" "$TARGET_COMMIT" -- "layouts/$rel_path"
  cd "$REPO_ROOT"
  echo ""

  if [ "$change_type" != "changed" ]; then
    echo "Automatic merge unavailable: the upstream file was $change_type. Review manually."
    echo ""
    continue
  fi

  while true; do
    read -rp "Merge upstream changes into your custom file? [y/n/d(iff)] " choice
    case "$choice" in
      y|Y)
        base_tmp=$(mktemp)
        new_tmp=$(mktemp)
        git -C "$THEME_DIR" show "$CURRENT_COMMIT:layouts/$rel_path" > "$base_tmp"
        git -C "$THEME_DIR" show "$TARGET_COMMIT:layouts/$rel_path" > "$new_tmp"

        if git merge-file "$custom_file" "$base_tmp" "$new_tmp"; then
          echo "✓ Merged cleanly."
        else
          echo "⚠ Merge conflicts detected in $custom_file — resolve manually."
        fi
        rm -f "$base_tmp" "$new_tmp"
        break
        ;;
      d|D)
        new_tmp=$(mktemp)
        git -C "$THEME_DIR" show "$TARGET_COMMIT:layouts/$rel_path" > "$new_tmp"
        echo "Diff between your custom file and new upstream:"
        git diff --no-index -- "$custom_file" "$new_tmp" || true
        rm -f "$new_tmp"
        ;;
      *)
        echo "Skipped."
        break
        ;;
    esac
  done
  echo ""
done

echo "=== Update complete ==="
echo "Review changes, then run:"
echo "  git add themes/blowfish layouts/"
echo "  git commit -m 'chore: update Blowfish theme to $TARGET_REF'"
