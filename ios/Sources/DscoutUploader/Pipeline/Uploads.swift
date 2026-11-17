import Foundation

/// Shared bookkeeping for `SinglePartUpload` and `MultipartUpload`.
class BaseUpload {
    let store: UploadStore
    var record: UploadRecord

    init(store: UploadStore, record: UploadRecord) {
        self.store = store
        self.record = record
    }

    func upload() -> UploadResult {
        fatalError("Subclasses must override")
    }

    var fileURL: URL { URL(fileURLWithPath: record.filePath) }

    func onUploadComplete() {
        record.onS3 = true
        record.partsUploaded = record.partsTotal
        store.save(record)
        store.deleteParts(for: record.id)
    }

    /// Throw away presign state (e.g. after URLs expire) so the next pass presigns again.
    func resetUploadState() {
        store.deleteParts(for: record.id)
        store.resetUpload(record.id)
        store.startUpload(record.id)
    }
}

final class SinglePartUpload: BaseUpload {
    private let s3: S3Client

    init(store: UploadStore, record: UploadRecord, s3: S3Client) {
        self.s3 = s3
        super.init(store: store, record: record)
    }

    override func upload() -> UploadResult {
        guard let part = store.parts(for: record.id).first else { return .retry }
        guard let data = try? Data(contentsOf: fileURL) else { return .failure }

        switch s3.put(data, to: part.url, contentType: S3Client.contentType(for: fileURL)) {
        case .failure:
            return .retry
        case .success(let response):
            if S3Errors.isExpired(response.body) {
                resetUploadState()
                return .retry
            }
            // The server learns about single-part uploads from S3 directly; nothing to report.
            onUploadComplete()
            return .success
        }
    }
}

/// Uploads remaining parts in order. Each part is PUT to S3, then its ETag is
/// reported to our server; the server completes the upload once it has every
/// part's ETag.
final class MultipartUpload: BaseUpload {
    private let s3: S3Client
    private let api: UploadAPI
    private let planner: PartPlanner

    init(store: UploadStore, record: UploadRecord, s3: S3Client, api: UploadAPI, planner: PartPlanner) {
        self.s3 = s3
        self.api = api
        self.planner = planner
        super.init(store: store, record: record)
    }

    override func upload() -> UploadResult {
        guard let serverUploadID = record.serverUploadID else { return .retry }
        guard let data = try? Data(contentsOf: fileURL) else { return .failure }
        let contentType = S3Client.contentType(for: fileURL)

        while let part = store.nextPartToUpload(for: record.id) {
            let range = planner.byteRange(partNumber: part.partNumber, fileSize: record.fileSize)

            let response: S3Response
            switch s3.put(data.subdata(in: range), to: part.url, contentType: contentType) {
            case .failure:
                return .retry
            case .success(let result):
                response = result
            }

            guard response.isSuccessful else {
                if S3Errors.isExpired(response.body) {
                    resetUploadState()
                }
                return .retry
            }

            let etag = response.etag ?? ""
            store.markPartUploaded(record.id, partNumber: part.partNumber, etag: etag)
            record.partsUploaded += 1
            store.save(record)

            switch api.reportPart(uploadID: serverUploadID, partNumber: part.partNumber, etag: etag) {
            case .success:
                store.markEtagReported(record.id, partNumber: part.partNumber)
            case .httpError, .networkError:
                return .retry
            }
        }

        onUploadComplete()
        return .success
    }
}
