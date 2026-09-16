# iosApp

A SwiftUI shell hosting the `shared` Compose Multiplatform module. See the top-level `AGENTS.md` first for repo-wide context (tech stack, backend contract, current skeleton state).

## What's here

- `iosAppApp.swift` — `@main` app entry point. Reads the backend base URL out of `Info.plist`, hands it to `shared`'s `BackendConfig`, and wraps `ContentView()` in a `WindowGroup`.
- `ContentView.swift` — a `UIViewControllerRepresentable` (`ComposeView`) wrapping `MainViewControllerKt.MainViewController()`, the Kotlin/Native-generated bridge into `shared`'s Compose UI. Swift-only UI chrome (if any) belongs here or in new Swift files; anything that's really app logic belongs in `shared/src/commonMain` instead.
- `Info.plist` — holds the `BackendBaseURL` value the app reads at startup, plus a scoped ATS (App Transport Security) exception for `localhost`/`127.0.0.1` only, needed because the backend serves plain HTTP.
- The `Compile Kotlin` build phase (in the Xcode project's target build settings) runs `./gradlew :shared:embedAndSignAppleFrameworkForXcode` automatically before every build — you don't need to run this manually except to sanity-check the Kotlin side compiles in isolation.

## Build / run

Open `iosApp.xcodeproj` in Xcode, select the `iosApp` scheme and any simulator, and run (⌘R). Editing Kotlin in `shared/` and rebuilding in Xcode is enough to pick up changes — the embed script re-runs automatically as part of the build.

## Signing

Simulator builds need no signing. A physical device build requires selecting a development team under the target's Signing & Capabilities tab. This project is designed around simulator use, so device signing shouldn't come up.

## Networking gotcha

Unlike the Android emulator, the iOS Simulator shares the host machine's network namespace — `127.0.0.1` reaches the host directly. That's already the `BackendBaseURL` value in `Info.plist`.

## If the framework embed step fails

This project was set up assuming a reasonably current Xcode (validated against the Xcode 15/16 generation). If you're on a materially newer Xcode and see linker errors mentioning the `Shared` framework, check the `Compile Kotlin` build phase's log first (in Xcode's build log navigator) — that's where a Kotlin/Native ↔ Xcode toolchain mismatch will surface. Bumping the Kotlin version in `gradle/libs.versions.toml` to one that supports the newer Xcode is the usual fix.
