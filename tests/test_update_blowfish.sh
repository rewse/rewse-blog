#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$REPO_ROOT/scripts/update_blowfish.sh"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

UPSTREAM_DIR="$TMP_DIR/upstream"
REMOTE_DIR="$TMP_DIR/remote.git"
SITE_DIR="$TMP_DIR/site"
TARGET_REF="untagged-test-release"

fail() {
  printf '%s\n' "$@" >&2
  exit 1
}

mkdir -p "$UPSTREAM_DIR/layouts"
git -C "$UPSTREAM_DIR" init --initial-branch=main --quiet
git -C "$UPSTREAM_DIR" config user.email "test@example.com"
git -C "$UPSTREAM_DIR" config user.name "Test User"
printf 'upstream=old\nanchor=unchanged\ncustom=base\n' > "$UPSTREAM_DIR/layouts/example.html"
printf 'shared=base\n' > "$UPSTREAM_DIR/layouts/conflict.html"
printf 'removed upstream\n' > "$UPSTREAM_DIR/layouts/removed.html"
printf '<rss>old</rss>\n' > "$UPSTREAM_DIR/layouts/index.xml"
printf 'name = "test"\n' > "$UPSTREAM_DIR/theme.toml"
git -C "$UPSTREAM_DIR" add layouts theme.toml
git -C "$UPSTREAM_DIR" commit --quiet -m "Initial release"
git -C "$UPSTREAM_DIR" tag v2.0.0

printf 'regular latest\n' > "$UPSTREAM_DIR/release.txt"
git -C "$UPSTREAM_DIR" add release.txt
git -C "$UPSTREAM_DIR" commit --quiet -m "Regular tagged release"
git -C "$UPSTREAM_DIR" tag v3.6.0

printf 'upstream=requested\nanchor=unchanged\ncustom=base\n' > "$UPSTREAM_DIR/layouts/example.html"
printf 'shared=upstream\n' > "$UPSTREAM_DIR/layouts/conflict.html"
printf 'added upstream\n' > "$UPSTREAM_DIR/layouts/added.html"
printf '<rss>new</rss>\n' > "$UPSTREAM_DIR/layouts/index.xml"
rm "$UPSTREAM_DIR/layouts/removed.html"
git -C "$UPSTREAM_DIR" add -A layouts
git -C "$UPSTREAM_DIR" commit --quiet -m "Requested untagged release"
git -C "$UPSTREAM_DIR" tag "$TARGET_REF"
# A pre-release tag must never be chosen as the latest version.
git -C "$UPSTREAM_DIR" tag v9.0.0-beta.1
TARGET_COMMIT=$(git -C "$UPSTREAM_DIR" rev-parse "$TARGET_REF")

git clone --bare --quiet "$UPSTREAM_DIR" "$REMOTE_DIR"
mkdir -p "$SITE_DIR/layouts" "$SITE_DIR/scripts" "$SITE_DIR/themes"
cp "$SCRIPT" "$SITE_DIR/scripts/update_blowfish.sh"
git clone --quiet "$REMOTE_DIR" "$SITE_DIR/themes/blowfish"
git -C "$SITE_DIR/themes/blowfish" checkout --quiet v2.0.0
printf 'upstream=old\nanchor=unchanged\ncustom=site\n' > "$SITE_DIR/layouts/example.html"
printf 'shared=custom\n' > "$SITE_DIR/layouts/conflict.html"
printf 'custom added path\n' > "$SITE_DIR/layouts/added.html"
printf 'custom removed path\n' > "$SITE_DIR/layouts/removed.html"
printf '<rss>custom</rss>\n' > "$SITE_DIR/layouts/index.xml"

# The input ends before the prompt for index.xml, which must be skipped.

OUTPUT=$(printf 'y\nd\ny\n' | "$SITE_DIR/scripts/update_blowfish.sh" "$TARGET_REF")
ACTUAL_COMMIT=$(git -C "$SITE_DIR/themes/blowfish" rev-parse HEAD)

if [[ "$ACTUAL_COMMIT" != "$TARGET_COMMIT" ]]; then
  printf 'Expected target commit %s, got %s\n' "$TARGET_COMMIT" "$ACTUAL_COMMIT" >&2
  printf '%s\n' "$OUTPUT" >&2
  exit 1
fi

for expected in \
  "Target Blowfish version: $TARGET_REF" \
  "ADDED UPSTREAM: layouts/added.html" \
  "CHANGED: layouts/conflict.html" \
  "CHANGED: layouts/example.html" \
  "CHANGED: layouts/index.xml" \
  "REMOVED UPSTREAM: layouts/removed.html" \
  "Diff between your custom file and new upstream:" \
  "⚠ Merge conflicts detected" \
  "✓ Merged cleanly." \
  "Skipped." \
  "=== Update complete ==="; do
  if [[ "$OUTPUT" != *"$expected"* ]]; then
    printf 'Expected output to contain: %s\n' "$expected" >&2
    printf '%s\n' "$OUTPUT" >&2
    exit 1
  fi
done

if [[ $(cat "$SITE_DIR/layouts/example.html") != $'upstream=requested\nanchor=unchanged\ncustom=site' ]]; then
  printf 'Clean three-way merge did not preserve custom content\n' >&2
  cat "$SITE_DIR/layouts/example.html" >&2
  exit 1
fi

if ! grep -q '^<<<<<<< ' "$SITE_DIR/layouts/conflict.html" || \
    ! grep -q '^>>>>>>> ' "$SITE_DIR/layouts/conflict.html"; then
  printf 'Conflicting merge did not leave conflict markers\n' >&2
  exit 1
fi

DEFAULT_OUTPUT=$("$SITE_DIR/scripts/update_blowfish.sh" </dev/null)
DEFAULT_COMMIT=$(git -C "$SITE_DIR/themes/blowfish" rev-parse HEAD)
if [[ "$DEFAULT_COMMIT" != "$TARGET_COMMIT" ]]; then
  printf 'Default update downgraded from %s to %s\n' "$TARGET_COMMIT" "$DEFAULT_COMMIT" >&2
  exit 1
fi
if [[ "$DEFAULT_OUTPUT" != *"Target Blowfish version: v3.6.0"* ]] || \
    [[ "$DEFAULT_OUTPUT" != *"Current revision is newer than the latest version tag"* ]]; then
  printf 'Expected default update to report that the current revision is newer\n' >&2
  printf '%s\n' "$DEFAULT_OUTPUT" >&2
  exit 1
fi

if [[ $(cat "$SITE_DIR/layouts/added.html") != 'custom added path' ]] || \
    [[ $(cat "$SITE_DIR/layouts/removed.html") != 'custom removed path' ]]; then
  printf 'Added or removed upstream layout was modified automatically\n' >&2
  exit 1
fi

if [[ $(cat "$SITE_DIR/layouts/index.xml") != '<rss>custom</rss>' ]]; then
  fail 'Skipped layout was modified'
fi

# A dirty theme work tree must stop the update before checkout.
DIRTY_DIR="$TMP_DIR/dirty"
mkdir -p "$DIRTY_DIR/layouts" "$DIRTY_DIR/scripts" "$DIRTY_DIR/themes"
cp "$SCRIPT" "$DIRTY_DIR/scripts/update_blowfish.sh"
git clone --quiet "$REMOTE_DIR" "$DIRTY_DIR/themes/blowfish"
git -C "$DIRTY_DIR/themes/blowfish" checkout --quiet v2.0.0
printf 'name = "dirty"\n' > "$DIRTY_DIR/themes/blowfish/theme.toml"
if "$DIRTY_DIR/scripts/update_blowfish.sh" "$TARGET_REF" </dev/null >/dev/null 2>&1; then
  fail 'Update succeeded with uncommitted theme changes'
fi
if [[ $(git -C "$DIRTY_DIR/themes/blowfish" rev-parse HEAD) != $(git -C "$UPSTREAM_DIR" rev-parse v2.0.0) ]]; then
  fail 'Dirty theme work tree was checked out'
fi

# An uninitialized submodule must not make the script operate on the parent repository.
PARENT_DIR="$TMP_DIR/parent"
mkdir -p "$PARENT_DIR/layouts" "$PARENT_DIR/scripts" "$PARENT_DIR/themes/blowfish"
cp "$SCRIPT" "$PARENT_DIR/scripts/update_blowfish.sh"
git -C "$PARENT_DIR" init --initial-branch=main --quiet
git -C "$PARENT_DIR" config user.email "test@example.com"
git -C "$PARENT_DIR" config user.name "Test User"
git -C "$PARENT_DIR" remote add origin "$REMOTE_DIR"
git -C "$PARENT_DIR" add scripts
git -C "$PARENT_DIR" commit --quiet -m "Site"
if "$PARENT_DIR/scripts/update_blowfish.sh" v2.0.0 </dev/null >/dev/null 2>&1; then
  fail 'Update succeeded with an uninitialized submodule'
fi
if ! git -C "$PARENT_DIR" symbolic-ref --quiet HEAD >/dev/null; then
  fail 'Parent repository HEAD was detached'
fi

printf 'PASS: explicit target and layout migration paths work\n'
