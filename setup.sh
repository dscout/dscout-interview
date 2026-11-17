#!/usr/bin/env bash
# Checks toolchains, installs the harness's dependencies, and runs every test
# suite. Safe to re-run. Sections warn and skip rather than aborting, so a
# partial toolchain (e.g. no Xcode) still gets the rest working.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

any_failed=0

section() {
  echo
  echo "== $1 =="
}

# --- Node / backend harness ------------------------------------------------
section "Backend harness (Node)"
node_ok=0
if ! command -v node >/dev/null 2>&1; then
  echo "node not found. Install Node 20+ (e.g. 'brew install node' or https://nodejs.org) and re-run."
  any_failed=1
elif (cd backend && npm install && npm test); then
  node_ok=1
  echo "Harness installed and self-tests passed."
else
  echo "Harness install or self-tests failed — see output above."
  any_failed=1
fi

# --- Kotlin engine -----------------------------------------------------------
section "Kotlin engine (JDK 17)"
# 'command -v java' is not enough on macOS: /usr/bin/java exists as a stub
# even with no JDK installed, and only fails once actually invoked.
if ! java_version_output=$(java -version 2>&1); then
  echo "No working Java runtime found. Install JDK 17 (e.g. 'brew install openjdk@17')."
  echo "If Android Studio is installed, its bundled JBR works too:"
  echo "  export JAVA_HOME=\"/Applications/Android Studio.app/Contents/jbr/Contents/Home\""
  any_failed=1
elif [ "$node_ok" -ne 1 ]; then
  echo "java found: $(echo "$java_version_output" | head -1)"
  echo "Skipping tests: they need the backend harness, which isn't set up."
  any_failed=1
elif (cd android && ./gradlew test); then
  echo "Kotlin engine tests passed."
else
  echo "Kotlin engine tests failed — see output above."
  any_failed=1
fi

# --- Swift engine ------------------------------------------------------------
section "Swift engine (Xcode)"
if [ "$(uname)" != "Darwin" ] || ! command -v swift >/dev/null 2>&1; then
  echo "Skipping: needs macOS with Xcode (install from the App Store, open it once to accept the license)."
elif [ "$node_ok" -ne 1 ]; then
  echo "Skipping tests: they need the backend harness, which isn't set up."
  any_failed=1
elif (cd ios && swift test); then
  echo "Swift engine tests passed."
else
  echo "Swift engine tests failed — see output above."
  any_failed=1
fi

# --- Summary ------------------------------------------------------------
section "Next steps"
echo "Harness:  cd backend && npm run dev     (http://127.0.0.1:4000, logs every request)"
echo "Kotlin:   cd android && ./gradlew test"
echo "Swift:    cd ios && swift test          (or open ios/Package.swift in Xcode)"
echo "See AGENTS.md, then backend/AGENTS.md and android/ or ios/AGENTS.md."

if [ "$any_failed" -ne 0 ]; then
  echo
  echo "One or more sections above need attention."
  exit 1
fi
