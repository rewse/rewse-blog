#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
THEME_DIR="$REPO_ROOT/themes/blowfish"
LAYOUTS_DIR="$REPO_ROOT/layouts"

# Step 1: Get current and latest version
cd "$THEME_DIR"
CURRENT_TAG=$(git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD)
echo "Current Blowfish version: $CURRENT_TAG"

git fetch --tags
LATEST_TAG=$(git tag --sort=-v:refname | head -1)
echo "Latest Blowfish version: $LATEST_TAG"

if [ "$CURRENT_TAG" = "$LATEST_TAG" ]; then
  echo "Already up to date."
  exit 0
fi

# Step 2: Check which custom layouts were changed upstream
echo ""
echo "=== Checking custom layouts for upstream changes ==="
CHANGED_FILES=()

while IFS= read -r file; do
  # Get relative path from layouts/ (e.g., partials/footer.html)
  rel_path="${file#"$LAYOUTS_DIR/"}"
  theme_file="$THEME_DIR/layouts/$rel_path"

  if [ ! -f "$theme_file" ]; then
    continue
  fi

  # Check if this file changed between current and latest tag
  if git diff --quiet "$CURRENT_TAG" "$LATEST_TAG" -- "layouts/$rel_path" 2>/dev/null; then
    continue
  fi

  CHANGED_FILES+=("$rel_path")
  echo "CHANGED: layouts/$rel_path"
done < <(find "$LAYOUTS_DIR" -type f -name "*.html")

# Step 3: Update submodule to latest tag
echo ""
echo "=== Updating submodule to $LATEST_TAG ==="
git checkout "$LATEST_TAG"
cd "$REPO_ROOT"

if [ ${#CHANGED_FILES[@]} -eq 0 ]; then
  echo ""
  echo "No custom layouts were affected by this update."
  echo "Done! Run 'git add themes/blowfish && git commit' to finalize."
  exit 0
fi

# Step 4: Show diffs and offer to merge
echo ""
echo "=== ${#CHANGED_FILES[@]} custom layout(s) have upstream changes ==="
echo ""

for rel_path in "${CHANGED_FILES[@]}"; do
  echo "────────────────────────────────────────"
  echo "File: layouts/$rel_path"
  echo "────────────────────────────────────────"
  echo "Upstream diff ($CURRENT_TAG → $LATEST_TAG):"
  cd "$THEME_DIR"
  git diff "$CURRENT_TAG" "$LATEST_TAG" -- "layouts/$rel_path"
  cd "$REPO_ROOT"
  echo ""

  read -rp "Merge upstream changes into your custom file? [y/n/d(iff)] " choice
  case "$choice" in
    y|Y)
      # Three-way merge using the old upstream as base
      base_content=$(cd "$THEME_DIR" && git show "$CURRENT_TAG:layouts/$rel_path")
      new_content=$(cd "$THEME_DIR" && git show "$LATEST_TAG:layouts/$rel_path")
      custom_file="$LAYOUTS_DIR/$rel_path"

      base_tmp=$(mktemp)
      new_tmp=$(mktemp)
      echo "$base_content" > "$base_tmp"
      echo "$new_content" > "$new_tmp"

      if git merge-file "$custom_file" "$base_tmp" "$new_tmp"; then
        echo "✓ Merged cleanly."
      else
        echo "⚠ Merge conflicts detected in $custom_file — resolve manually."
      fi
      rm -f "$base_tmp" "$new_tmp"
      ;;
    d|D)
      echo "Diff between your custom file and new upstream:"
      diff --color=auto "$LAYOUTS_DIR/$rel_path" <(cd "$THEME_DIR" && git show "$LATEST_TAG:layouts/$rel_path") || true
      ;;
    *)
      echo "Skipped."
      ;;
  esac
  echo ""
done

echo "=== Update complete ==="
echo "Review changes, then run:"
echo "  git add themes/blowfish layouts/"
echo "  git commit -m 'chore: update Blowfish theme to $LATEST_TAG'"
