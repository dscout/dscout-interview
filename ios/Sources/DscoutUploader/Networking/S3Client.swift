import Foundation

struct S3Response {
    var statusCode: Int
    var etag: String?
    var body: String

    var isSuccessful: Bool { (200..<300).contains(statusCode) }
}

/// Raw PUTs to presigned URLs. No AWS SDK — the URL carries the credentials.
final class S3Client {
    private let session: URLSession

    init(session: URLSession) {
        self.session = session
    }

    func put(_ data: Data, to url: URL, contentType: String) -> Result<S3Response, Error> {
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue(contentType, forHTTPHeaderField: "Content-Type")

        let (body, response, error) = session.synchronousDataTask(with: request, body: data)
        if let error {
            return .failure(error)
        }
        let http = response as? HTTPURLResponse
        return .success(S3Response(
            statusCode: http?.statusCode ?? 0,
            etag: http?.value(forHTTPHeaderField: "ETag"),
            body: String(decoding: body ?? Data(), as: UTF8.self)
        ))
    }

    static func contentType(for url: URL) -> String {
        switch url.pathExtension.lowercased() {
        case "mp4", "m4v": return "video/mp4"
        case "mov": return "video/quicktime"
        case "webm": return "video/webm"
        case "jpg", "jpeg": return "image/jpeg"
        case "png": return "image/png"
        case "heic": return "image/heic"
        case "m4a": return "audio/mp4"
        default: return "application/octet-stream"
        }
    }
}

enum S3Errors {
    static func isExpired(_ body: String) -> Bool {
        body.contains("Request has expired")
    }
}
