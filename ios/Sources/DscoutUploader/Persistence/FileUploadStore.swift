import Foundation

/// `UploadStore` backed by a JSON file, rewritten on every change. Survives
/// app termination the same way Core Data does: create a new store on the
/// same file and everything is still there.
public final class FileUploadStore: UploadStore {
    private struct Snapshot: Codable {
        var nextID: Int64 = 1
        var uploads: [UploadRecord] = []
        var parts: [UploadPart] = []
    }

    private let fileURL: URL
    private let lock = NSLock()
    private var nextID: Int64 = 1
    private var uploads: [Int64: UploadRecord] = [:]
    private var parts: [UploadPart] = []

    public init(fileURL: URL) {
        self.fileURL = fileURL
        if let data = try? Data(contentsOf: fileURL),
           let snapshot = try? JSONDecoder().decode(Snapshot.self, from: data) {
            nextID = snapshot.nextID
            snapshot.uploads.forEach { uploads[$0.id] = $0 }
            parts = snapshot.parts
        }
    }

    public func insert(_ record: UploadRecord) -> Int64 {
        locked {
            var record = record
            record.id = nextID
            nextID += 1
            uploads[record.id] = record
            persist()
            return record.id
        }
    }

    public func get(_ id: Int64) -> UploadRecord? {
        locked { uploads[id] }
    }

    public func all() -> [UploadRecord] {
        locked { uploads.values.sorted { $0.id < $1.id } }
    }

    public func save(_ record: UploadRecord) {
        locked {
            guard uploads[record.id] != nil else { return }
            uploads[record.id] = record
            persist()
        }
    }

    public func startUpload(_ id: Int64) {
        modify(id) { $0.started = true; $0.stopped = false }
    }

    public func stopUpload(_ id: Int64) {
        modify(id) { $0.stopped = true }
    }

    public func markFailed(_ id: Int64) {
        modify(id) { $0.failed = true }
    }

    public func resetUpload(_ id: Int64) {
        modify(id) {
            $0.started = false
            $0.stopped = false
            $0.failed = false
            $0.onS3 = false
            $0.serverUploadID = nil
            $0.partsTotal = 0
            $0.partsUploaded = 0
        }
    }

    public func nextPending(after afterID: Int64) -> UploadRecord? {
        locked {
            uploads.values
                .filter { $0.id > afterID && $0.isPending }
                .min { $0.id < $1.id }
        }
    }

    public func pendingCount() -> Int {
        locked { uploads.values.filter(\.isPending).count }
    }

    public func parts(for uploadID: Int64) -> [UploadPart] {
        locked { parts.filter { $0.uploadID == uploadID }.sorted { $0.partNumber < $1.partNumber } }
    }

    public func replaceParts(for uploadID: Int64, with newParts: [UploadPart]) {
        locked {
            parts.removeAll { $0.uploadID == uploadID }
            parts.append(contentsOf: newParts)
            persist()
        }
    }

    public func nextPartToUpload(for uploadID: Int64) -> UploadPart? {
        locked {
            parts
                .filter { $0.uploadID == uploadID && !$0.uploaded }
                .min { $0.partNumber < $1.partNumber }
        }
    }

    public func markPartUploaded(_ uploadID: Int64, partNumber: Int, etag: String) {
        modifyPart(uploadID, partNumber) { $0.uploaded = true; $0.etag = etag }
    }

    public func markEtagReported(_ uploadID: Int64, partNumber: Int) {
        modifyPart(uploadID, partNumber) { $0.etagReported = true }
    }

    public func deleteParts(for uploadID: Int64) {
        locked {
            parts.removeAll { $0.uploadID == uploadID }
            persist()
        }
    }

    // MARK: - Private

    private func locked<T>(_ body: () -> T) -> T {
        lock.lock()
        defer { lock.unlock() }
        return body()
    }

    private func modify(_ id: Int64, _ change: (inout UploadRecord) -> Void) {
        locked {
            guard var record = uploads[id] else { return }
            change(&record)
            uploads[id] = record
            persist()
        }
    }

    private func modifyPart(_ uploadID: Int64, _ partNumber: Int, _ change: (inout UploadPart) -> Void) {
        locked {
            guard let index = parts.firstIndex(where: { $0.uploadID == uploadID && $0.partNumber == partNumber }) else { return }
            change(&parts[index])
            persist()
        }
    }

    /// Caller must hold `lock`.
    private func persist() {
        let snapshot = Snapshot(nextID: nextID, uploads: uploads.values.sorted { $0.id < $1.id }, parts: parts)
        do {
            try FileManager.default.createDirectory(at: fileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try JSONEncoder().encode(snapshot).write(to: fileURL, options: .atomic)
        } catch {
            assertionFailure("Failed to persist uploads: \(error)")
        }
    }
}

private extension UploadRecord {
    var isPending: Bool { started && !stopped && !failed && !onS3 }
}
