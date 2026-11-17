// swift-tools-version:5.9
// Plain Swift package so `swift test` runs on any Mac with Xcode — no
// simulator or app host. In the real app this engine sits behind the
// MediaPipeline service; see AGENTS.md for what's simulated here.
import PackageDescription

let package = Package(
    name: "DscoutUploader",
    platforms: [.macOS(.v13), .iOS(.v16)],
    products: [
        .library(name: "DscoutUploader", targets: ["DscoutUploader"]),
    ],
    targets: [
        .target(name: "DscoutUploader"),
        .testTarget(name: "DscoutUploaderTests", dependencies: ["DscoutUploader"]),
    ]
)
