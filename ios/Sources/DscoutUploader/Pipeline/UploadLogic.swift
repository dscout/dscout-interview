import Foundation

/// Runs one upload as far as it can go: presign (if needed), then PUT bytes.
final class UploadLogic {
    private let store: UploadStore
    private let presigner: MediaPresigner
    private let s3: S3Client
    private let api: UploadAPI
    private let planner: PartPlanner

    init(store: UploadStore, presigner: MediaPresigner, s3: S3Client, api: UploadAPI, planner: PartPlanner) {
        self.store = store
        self.presigner = presigner
        self.s3 = s3
        self.api = api
        self.planner = planner
    }

    func performUpload(id: Int64) -> UploadResult {
        guard let record = store.get(id) else { return .failure }

        let presigned = presigner.presignIfNeeded(record)
        guard case .success = presigned else { return presigned }

        // Re-read: presigning wrote the server id and part count.
        guard let current = store.get(id) else { return .failure }
        let upload: BaseUpload = current.partsTotal == 1
            ? SinglePartUpload(store: store, record: current, s3: s3)
            : MultipartUpload(store: store, record: current, s3: s3, api: api, planner: planner)
        return upload.upload()
    }
}
