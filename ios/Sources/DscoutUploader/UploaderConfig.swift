import Foundation

public struct UploaderConfig {
    public var baseURL: URL
    /// S3 requires every part but the last to be at least 5 MiB; the harness doesn't.
    public var partSize: Int
    public var maxParts: Int
    /// How long to wait before another pass when any upload asked to be retried.
    public var retryDelay: TimeInterval

    public init(
        baseURL: URL,
        partSize: Int = 5 * 1024 * 1024,
        maxParts: Int = 1000,
        retryDelay: TimeInterval = 5 * 60
    ) {
        self.baseURL = baseURL
        self.partSize = partSize
        self.maxParts = maxParts
        self.retryDelay = retryDelay
    }
}
