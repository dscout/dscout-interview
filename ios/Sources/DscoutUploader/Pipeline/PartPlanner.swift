import Foundation

/// Splits a file into fixed-size parts for multipart upload.
struct PartPlanner {
    let partSize: Int
    let maxParts: Int

    func partCount(fileSize: Int64) -> Int {
        if fileSize < partSize {
            return 1
        }
        let count = Int((Double(fileSize) / Double(partSize)).rounded(.up))
        return min(count, maxParts)
    }

    func byteRange(partNumber: Int, fileSize: Int64) -> Range<Int> {
        let offset = (partNumber - 1) * partSize
        let end = min(offset + partSize, Int(fileSize))
        return offset..<end
    }
}
