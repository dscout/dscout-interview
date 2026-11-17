@testable import DscoutUploader
import XCTest

final class PartPlannerTests: XCTestCase {
    private let planner = PartPlanner(partSize: 100, maxParts: 1000)

    func testFilesSmallerThanAPartAreASinglePart() {
        XCTAssertEqual(planner.partCount(fileSize: 99), 1)
    }

    func testPartsAreFixedSizeWithAShortLastPart() {
        XCTAssertEqual(planner.partCount(fileSize: 250), 3)
        XCTAssertEqual(planner.byteRange(partNumber: 1, fileSize: 250), 0..<100)
        XCTAssertEqual(planner.byteRange(partNumber: 3, fileSize: 250), 200..<250)
    }

    func testAnExactMultipleHasNoEmptyTrailingPart() {
        XCTAssertEqual(planner.partCount(fileSize: 200), 2)
        XCTAssertEqual(planner.byteRange(partNumber: 2, fileSize: 200), 100..<200)
    }
}
