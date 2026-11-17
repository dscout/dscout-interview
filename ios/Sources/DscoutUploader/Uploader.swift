import Foundation

/// Entry point for the rest of the app. Questionnaire code calls `enqueue`
/// when the participant captures media; the host calls `start()` whenever
/// uploads might be able to make progress (scene active, entry submitted).
public final class Uploader {
    private let store: UploadStore
    private let worker: UploadWorker

    public init(
        config: UploaderConfig,
        store: UploadStore,
        session: URLSession = URLSession(configuration: .default),
        api: UploadAPI? = nil
    ) {
        let api = api ?? HTTPUploadAPI(baseURL: config.baseURL, session: session)
        let planner = PartPlanner(partSize: config.partSize, maxParts: config.maxParts)
        let s3 = S3Client(session: session)
        let logic = UploadLogic(
            store: store,
            presigner: MediaPresigner(store: store, api: api, planner: planner),
            s3: s3,
            api: api,
            planner: planner
        )
        self.store = store
        self.worker = UploadWorker(store: store, logic: logic, retryDelay: config.retryDelay)
    }

    public var isRunning: Bool { worker.isRunning }

    @discardableResult
    public func enqueue(fileURL: URL, entryID: String? = nil) -> Int64 {
        let attributes = try? FileManager.default.attributesOfItem(atPath: fileURL.path)
        let size = (attributes?[.size] as? NSNumber)?.int64Value ?? 0
        let id = store.insert(UploadRecord(filePath: fileURL.path, fileSize: size, entryID: entryID))
        upload(id: id)
        return id
    }

    /// Starts (or resumes a paused) upload.
    public func upload(id: Int64) {
        guard let record = store.get(id) else { return }
        if record.started && !record.stopped { return }
        store.startUpload(id)
        worker.start()
    }

    /// Pauses an upload. Resume with `upload(id:)`.
    public func cancel(id: Int64) {
        store.stopUpload(id)
    }

    public func start() {
        worker.start()
    }

    public func status(id: Int64) -> UploadStatus? {
        store.get(id)?.status
    }

    /// 0.0–1.0, at part granularity.
    public func progress(id: Int64) -> Double {
        guard let record = store.get(id) else { return 0 }
        if record.onS3 { return 1 }
        guard record.partsTotal > 0 else { return 0 }
        return Double(record.partsUploaded) / Double(record.partsTotal)
    }

    public func record(id: Int64) -> UploadRecord? {
        store.get(id)
    }

    public func pendingCount() -> Int {
        store.pendingCount()
    }

    /// Stops scheduling work. Call when tearing down (e.g. between tests).
    public func invalidate() {
        worker.invalidate()
    }
}
