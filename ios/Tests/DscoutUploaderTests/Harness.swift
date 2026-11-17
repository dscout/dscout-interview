import Foundation

/// Test access to the Node upload harness in ../backend.
///
/// By default the first test to touch `Harness` boots `node src/server.js` on a
/// free port, logging to .build/harness.log. Set HARNESS_URL to point at one
/// you're already running instead (e.g. `npm run dev` to watch its log).
enum Harness {
    static let url: URL = {
        if let override = ProcessInfo.processInfo.environment["HARNESS_URL"] {
            return URL(string: override)!
        }
        return boot()
    }()

    /// Clears uploads, faults, and config. Call before each test.
    static func reset() {
        send("POST", "__reset", body: "{}")
    }

    /// Registers a fault rule; see backend/src/faults.js for the shape, e.g.
    /// `addFault(#"{"route":"s3","part":2,"action":{"type":"status","status":500}}"#)`
    static func addFault(_ ruleJSON: String) {
        send("POST", "__faults", body: ruleJSON)
    }

    static func setURLTTL(seconds: Int) {
        send("PUT", "__config", body: #"{"urlTtlSeconds":\#(seconds)}"#)
    }

    static func upload(_ id: String) -> ServerUpload {
        try! JSONDecoder().decode(ServerUpload.self, from: send("GET", "uploads/\(id)"))
    }

    static func uploads() -> [ServerUpload] {
        try! JSONDecoder().decode([ServerUpload].self, from: send("GET", "uploads"))
    }

    @discardableResult
    private static func send(_ method: String, _ path: String, body: String? = nil) -> Data {
        var request = URLRequest(url: url.appendingPathComponent(path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = body?.data(using: .utf8)

        let semaphore = DispatchSemaphore(value: 0)
        var result: (Data?, URLResponse?, Error?) = (nil, nil, nil)
        URLSession.shared.dataTask(with: request) { data, response, error in
            result = (data, response, error)
            semaphore.signal()
        }.resume()
        semaphore.wait()

        let status = (result.1 as? HTTPURLResponse)?.statusCode ?? 0
        let data = result.0 ?? Data()
        precondition((200..<300).contains(status), "\(method) /\(path) -> \(status): \(String(decoding: data, as: UTF8.self)) \(result.2.map(String.init(describing:)) ?? "")")
        return data
    }

    private static func boot() -> URL {
        let packageRoot = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent() // DscoutUploaderTests
            .deletingLastPathComponent() // Tests
            .deletingLastPathComponent() // ios
        let backend = packageRoot.deletingLastPathComponent().appendingPathComponent("backend")
        precondition(
            FileManager.default.fileExists(atPath: backend.appendingPathComponent("node_modules").path),
            "Harness dependencies missing. Run `npm install` in \(backend.path) first."
        )

        let logURL = packageRoot.appendingPathComponent(".build/harness.log")
        try? FileManager.default.createDirectory(at: logURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        let log = try! FileHandle(forWritingTo: logURL)

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["node", "src/server.js"]
        process.currentDirectoryURL = backend
        var environment = ProcessInfo.processInfo.environment
        environment["PORT"] = "0"
        process.environment = environment
        process.standardOutput = log
        process.standardError = log
        try! process.run()
        atexit { Harness.process?.terminate() }
        Harness.process = process

        let deadline = Date().addingTimeInterval(10)
        while Date() < deadline {
            let text = (try? String(contentsOf: logURL, encoding: .utf8)) ?? ""
            if let range = text.range(of: #"listening on (http://\S+)"#, options: .regularExpression) {
                let match = text[range].replacingOccurrences(of: "listening on ", with: "")
                return URL(string: match)!
            }
            precondition(process.isRunning, "Harness exited early:\n\(text)")
            Thread.sleep(forTimeInterval: 0.05)
        }
        preconditionFailure("Harness didn't start within 10s")
    }

    private static var process: Process?
}

struct ServerUpload: Decodable {
    var id: String
    var key: String
    var filename: String
    var entryId: String?
    var size: Int64
    var parts: Int
    var multipart: Bool
    /// "pending" | "complete" | "failed"
    var status: String
    var failureReason: String?
    var partsStored: [Int]
    var partsReported: [Int]
    var assembledSize: Int64?
    var sha256: String?
}
