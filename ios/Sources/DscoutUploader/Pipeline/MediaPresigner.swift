import Foundation

final class MediaPresigner {
    private let store: UploadStore
    private let api: UploadAPI
    private let planner: PartPlanner

    init(store: UploadStore, api: UploadAPI, planner: PartPlanner) {
        self.store = store
        self.api = api
        self.planner = planner
    }

    func presignIfNeeded(_ record: UploadRecord) -> UploadResult {
        // Already presigned on an earlier pass; resume with the stored part URLs.
        if !store.parts(for: record.id).isEmpty {
            return .success
        }

        let fileURL = URL(fileURLWithPath: record.filePath)
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            return .failure
        }

        let partCount = planner.partCount(fileSize: record.fileSize)
        let request = PresignRequest(
            filename: fileURL.lastPathComponent,
            size: record.fileSize,
            parts: partCount > 1 ? partCount : nil,
            entryId: record.entryID
        )

        switch api.presign(request) {
        case .success(let presign):
            let urls = presign.partUrls ?? [presign.url].compactMap { $0 }
            let parts = urls.enumerated().map { index, url in
                UploadPart(uploadID: record.id, partNumber: index + 1, url: url)
            }
            store.replaceParts(for: record.id, with: parts)

            var updated = record
            updated.serverUploadID = presign.id
            updated.partsTotal = urls.count
            updated.partsUploaded = 0
            store.save(updated)
            return .success

        case .httpError(let code, _):
            if code == 404 {
                store.markFailed(record.id)
                return .failure
            }
            return .retry

        case .networkError:
            return .retry
        }
    }
}
