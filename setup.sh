#!/usr/bin/env bash
# Gets the backend, Android app, and iOS app runnable with minimal manual
# steps. Safe to re-run. Individual sections warn and skip rather than
# aborting the whole script, so partial toolchains still make progress.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

any_failed=0

section() {
  echo
  echo "== $1 =="
}

# --- OS -----------------------------------------------------------------
section "Checking OS"
OS="$(uname)"
if [ "$OS" != "Darwin" ]; then
  echo "This is not macOS. Backend and Android setup will proceed; iOS setup requires Xcode on macOS and will be skipped."
fi

# --- Node / backend -------------------------------------------------------
section "Backend (Node)"
if ! command -v node >/dev/null 2>&1; then
  echo "node not found. Install Node 20+ (e.g. 'brew install node' or https://nodejs.org) and re-run."
  any_failed=1
else
  echo "node $(node -v) found."
  if (cd backend && npm install); then
    echo "Backend dependencies installed."
  else
    echo "npm install failed in backend/ — see output above."
    any_failed=1
  fi
fi

# --- JDK ------------------------------------------------------------------
section "Java (for Gradle/Android)"
# 'command -v java' is not enough on macOS: /usr/bin/java exists as a stub
# even with no JDK installed, and only fails once actually invoked.
java_ok=0
if java_version_output=$(java -version 2>&1); then
  java_ok=1
  echo "java found: $(echo "$java_version_output" | head -1)"
else
  echo "No working Java runtime found. Gradle needs JDK 17+."
  echo "If Android Studio is installed, point JAVA_HOME at its bundled JBR instead of installing a separate JDK, e.g.:"
  echo "  export JAVA_HOME=\"/Applications/Android Studio.app/Contents/jbr/Contents/Home\""
  any_failed=1
fi

# --- Android SDK ------------------------------------------------------------
section "Android SDK"
if [ -n "${ANDROID_HOME:-}" ] || [ -n "${ANDROID_SDK_ROOT:-}" ] || command -v adb >/dev/null 2>&1; then
  echo "Android SDK environment detected."
else
  echo "No ANDROID_HOME/ANDROID_SDK_ROOT set and 'adb' not on PATH."
  echo "Open Android Studio once (it installs the SDK), then set ANDROID_HOME to the SDK location it reports."
fi

# --- Gradle build -----------------------------------------------------------
section "Gradle build (shared + androidApp)"
if [ "$java_ok" -eq 1 ]; then
  if ./gradlew :shared:build :androidApp:assembleDebug; then
    echo "Gradle build succeeded."
  else
    echo "Gradle build failed — see output above."
    any_failed=1
  fi
else
  echo "Skipping Gradle build: no Java runtime found."
  any_failed=1
fi

# --- Xcode / iOS ------------------------------------------------------------
section "iOS (Xcode)"
if [ "$OS" = "Darwin" ]; then
  if command -v xcodebuild >/dev/null 2>&1 && xcode-select -p >/dev/null 2>&1 && [ -d "$(xcode-select -p)/../Applications/Xcode.app" ] 2>/dev/null; then
    if xcodebuild -project iosApp/iosApp.xcodeproj -scheme iosApp -sdk iphonesimulator -configuration Debug build; then
      echo "iOS build succeeded."
    else
      echo "iOS build failed — see output above."
      any_failed=1
    fi
  else
    echo "Full Xcode not found (only Command Line Tools, or Xcode missing)."
    echo "Install Xcode from the App Store, open it once to accept the license, then run: xcode-select --install"
  fi
else
  echo "Skipping (not macOS)."
fi

# --- Summary ------------------------------------------------------------
section "Next steps"
echo "Backend:   cd backend && npm start        (serves http://localhost:4000)"
echo "Android:   open this repo in Android Studio, run the 'androidApp' configuration on any emulator"
echo "iOS:       open iosApp/iosApp.xcodeproj in Xcode, run the 'iosApp' scheme on any simulator"
echo "See AGENTS.md for repo context, and androidApp/AGENTS.md, iosApp/AGENTS.md, backend/AGENTS.md for platform-specific notes."

if [ "$any_failed" -ne 0 ]; then
  echo
  echo "One or more sections above need attention before everything is fully runnable."
  exit 1
fi
