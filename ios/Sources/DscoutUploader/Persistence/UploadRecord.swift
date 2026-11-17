import Foundation

/// One file the participant has captured and we owe the server.
///
/// State is tracked with independent flags; see `UploadRecord.status` for how
/// the UI reads them.
public struct UploadRecord: Codable, Equatable {
    public var id: Int64
    public var filePath: String
    public var fileSize: Int64
    /// The entry (answer) this media belongs to. Passed through at presign.
    public var entryID: String?
    public var createdAt: Date

    public var started = false
    public var stopped = false
    public var failed = false
    public var onS3 = false

    /// Server-side upload id, returned by presign.
    public var serverUploadID: String?
    public var partsTotal = 0
    public var partsUploaded = 0

    public init(id: Int64 = 0, filePath: String, fileSize: Int64, entryID: String? = nil, createdAt: Date = Date()) {
        self.id = id
        self.filePath = filePath
        self.fileSize = fileSize
        self.entryID = entryID
        self.createdAt = createdAt
    }
}

/// A slice of a file and its presigned URL. Single-part uploads have one.
public struct UploadPart: Codable, Equatable {
    public var uploadID: Int64
    public var partNumber: Int
    public var url: URL
    /// Bytes accepted by S3.
    public var uploaded = false
    public var etag: String?
    /// ETag acknowledged by our server.
    public var etagReported = false

    public init(uploadID: Int64, partNumber: Int, url: URL) {
        self.uploadID = uploadID
        self.partNumber = partNumber
        self.url = url
    }
}

public enum UploadStatus: Equatable {
    case created, queued, paused, failed, done
}

extension UploadRecord {
    public var status: UploadStatus {
        if onS3 { return .done }
        if failed { return .failed }
        if stopped { return .paused }
        if started { return .queued }
        return .created
    }
}
