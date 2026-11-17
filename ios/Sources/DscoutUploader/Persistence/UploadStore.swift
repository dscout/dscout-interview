import Foundation

/// Persistence for uploads and their parts. Stands in for the Core Data
/// `Media` / `MediaDropletEntity` entities in the production app.
public protocol UploadStore: AnyObject {
    func insert(_ record: UploadRecord) -> Int64
    func get(_ id: Int64) -> UploadRecord?
    func all() -> [UploadRecord]
    func save(_ record: UploadRecord)

    /// started = true, stopped = false
    func startUpload(_ id: Int64)
    /// stopped = true
    func stopUpload(_ id: Int64)
    /// failed = true
    func markFailed(_ id: Int64)
    /// Clears all presign/progress state so the upload starts over.
    func resetUpload(_ id: Int64)

    /// Lowest-id upload after `afterID` that is started, not stopped, not failed, and not on S3.
    func nextPending(after afterID: Int64) -> UploadRecord?
    func pendingCount() -> Int

    func parts(for uploadID: Int64) -> [UploadPart]
    func replaceParts(for uploadID: Int64, with parts: [UploadPart])
    func nextPartToUpload(for uploadID: Int64) -> UploadPart?
    func markPartUploaded(_ uploadID: Int64, partNumber: Int, etag: String)
    func markEtagReported(_ uploadID: Int64, partNumber: Int)
    func deleteParts(for uploadID: Int64)
}
