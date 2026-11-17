import DscoutUploader
import XCTest

final class FileUploadStoreTests: XCTestCase {
    func testStateSurvivesANewStoreInstanceOnTheSameFile() {
        let fileURL = makeTempDirectory().appendingPathComponent("uploads.json")
        let store = FileUploadStore(fileURL: fileURL)
        let id = store.insert(UploadRecord(filePath: "/tmp/a.mp4", fileSize: 10))
        store.startUpload(id)
        store.replaceParts(for: id, with: [
            UploadPart(uploadID: id, partNumber: 1, url: URL(string: "http://a")!),
            UploadPart(uploadID: id, partNumber: 2, url: URL(string: "http://b")!),
        ])
        store.markPartUploaded(id, partNumber: 1, etag: "\"etag-1\"")
        store.markEtagReported(id, partNumber: 1)

        let reopened = FileUploadStore(fileURL: fileURL)

        XCTAssertEqual(reopened.get(id)?.started, true)
        XCTAssertEqual(reopened.nextPartToUpload(for: id)?.partNumber, 2)
        XCTAssertEqual(reopened.insert(UploadRecord(filePath: "/tmp/b.mp4", fileSize: 1)), id + 1)
    }

    func testNextPendingSkipsStoppedAndFinishedUploads() {
        let store = FileUploadStore(fileURL: makeTempDirectory().appendingPathComponent("uploads.json"))
        let stopped = store.insert(UploadRecord(filePath: "a", fileSize: 1))
        let done = store.insert(UploadRecord(filePath: "b", fileSize: 1))
        let pending = store.insert(UploadRecord(filePath: "c", fileSize: 1))
        [stopped, done, pending].forEach(store.startUpload)
        store.stopUpload(stopped)
        var finished = store.get(done)!
        finished.onS3 = true
        store.save(finished)

        XCTAssertEqual(store.nextPending(after: 0)?.id, pending)
        XCTAssertNil(store.nextPending(after: pending))
        XCTAssertEqual(store.pendingCount(), 1)
    }
}
