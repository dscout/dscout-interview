import DscoutUploader
import XCTest

final class UploaderTests: XCTestCase {
    private var directory: URL!
    private var uploader: Uploader!

    override func setUp() {
        super.setUp()
        Harness.reset()
        directory = makeTempDirectory()
        uploader = Uploader(config: testConfig(), store: FileUploadStore(fileURL: directory.appendingPathComponent("uploads.json")))
    }

    override func tearDown() {
        uploader.invalidate()
        try? FileManager.default.removeItem(at: directory)
        super.tearDown()
    }

    private func serverUpload(_ id: Int64) throws -> ServerUpload {
        Harness.upload(try XCTUnwrap(uploader.record(id: id)?.serverUploadID))
    }

    func testSinglePartUploadReachesTheServerIntact() throws {
        let file = makeMediaFile(in: directory, size: 500, name: "photo.jpg")

        let id = uploader.enqueue(fileURL: file, entryID: "entry-1")

        eventually { uploader.status(id: id) == .done }
        let server = try serverUpload(id)
        XCTAssertEqual(server.status, "complete")
        XCTAssertEqual(server.sha256, sha256(of: file))
        XCTAssertEqual(server.entryId, "entry-1")
    }

    func testMultipartUploadReachesTheServerIntact() throws {
        let file = makeMediaFile(in: directory, size: 5_000)

        let id = uploader.enqueue(fileURL: file)

        eventually { uploader.status(id: id) == .done }
        let server = try serverUpload(id)
        XCTAssertEqual(server.parts, 5)
        XCTAssertEqual(server.status, "complete")
        XCTAssertEqual(server.sha256, sha256(of: file))
    }

    func testUploadsRunInTheOrderTheyWereEnqueued() {
        let ids = (1...3).map { uploader.enqueue(fileURL: makeMediaFile(in: directory, size: 2_000, name: "clip\($0).mp4")) }

        eventually { ids.allSatisfy { uploader.status(id: $0) == .done } }
        XCTAssertEqual(Harness.uploads().map(\.id), ids.map { uploader.record(id: $0)?.serverUploadID })
    }

    func testRetriesAPartAfterATransientS3Error() throws {
        Harness.addFault(#"{"route":"s3","part":2,"action":{"type":"status","status":503}}"#)
        let file = makeMediaFile(in: directory, size: 3_000)

        let id = uploader.enqueue(fileURL: file)

        eventually { uploader.status(id: id) == .done }
        let server = try serverUpload(id)
        XCTAssertEqual(server.status, "complete")
        XCTAssertEqual(server.sha256, sha256(of: file))
    }
}
