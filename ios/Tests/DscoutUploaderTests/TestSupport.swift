import CryptoKit
import DscoutUploader
import Foundation
import XCTest

func makeTempDirectory() -> URL {
    let url = FileManager.default.temporaryDirectory.appendingPathComponent("uploader-test-\(UUID().uuidString)")
    try! FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    return url
}

/// A file of random bytes with a media extension the harness accepts.
func makeMediaFile(in directory: URL, size: Int, name: String = "clip.mp4") -> URL {
    let url = directory.appendingPathComponent(name)
    var generator = SystemRandomNumberGenerator()
    let bytes = (0..<size).map { _ in UInt8.random(in: .min ... .max, using: &generator) }
    try! Data(bytes).write(to: url)
    return url
}

func sha256(of url: URL) -> String {
    SHA256.hash(data: try! Data(contentsOf: url)).map { String(format: "%02x", $0) }.joined()
}

/// Polls `condition` until it's true or `timeout` passes.
func eventually(
    timeout: TimeInterval = 5,
    _ message: @autoclosure () -> String = "condition not met",
    file: StaticString = #filePath,
    line: UInt = #line,
    _ condition: () -> Bool
) {
    let deadline = Date().addingTimeInterval(timeout)
    while Date() < deadline {
        if condition() { return }
        Thread.sleep(forTimeInterval: 0.025)
    }
    XCTFail("Timed out after \(timeout)s: \(message())", file: file, line: line)
}

/// Small parts so multipart paths run on tiny files.
func testConfig(partSize: Int = 1024, maxParts: Int = 1000, retryDelay: TimeInterval = 0.1) -> UploaderConfig {
    UploaderConfig(baseURL: Harness.url, partSize: partSize, maxParts: maxParts, retryDelay: retryDelay)
}
