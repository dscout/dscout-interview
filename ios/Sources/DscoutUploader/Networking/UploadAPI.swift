import Foundation

public enum APIResult<Value> {
    case success(Value)
    case httpError(code: Int, body: String)
    case networkError(Error)
}

public struct PresignRequest: Encodable {
    public var filename: String
    public var size: Int64
    /// Omitted for single-part uploads.
    public var parts: Int?
    public var entryId: String?
}

public struct PresignResponse: Decodable {
    public var id: String
    public var key: String
    public var parts: Int
    /// Set for single-part uploads.
    public var url: URL?
    /// Set for multipart uploads; index 0 is part 1.
    public var partUrls: [URL]?
}

/// Our backend (not S3). See backend/AGENTS.md for the contract.
public protocol UploadAPI {
    func presign(_ request: PresignRequest) -> APIResult<PresignResponse>
    func reportPart(uploadID: String, partNumber: Int, etag: String) -> APIResult<Void>
}

public final class HTTPUploadAPI: UploadAPI {
    private struct ReportPartBody: Encodable {
        var partNumber: Int
        var etag: String
    }

    private let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL, session: URLSession) {
        self.baseURL = baseURL
        self.session = session
    }

    public func presign(_ request: PresignRequest) -> APIResult<PresignResponse> {
        post("uploads", body: request) { try JSONDecoder().decode(PresignResponse.self, from: $0) }
    }

    public func reportPart(uploadID: String, partNumber: Int, etag: String) -> APIResult<Void> {
        post("uploads/\(uploadID)/parts", body: ReportPartBody(partNumber: partNumber, etag: etag)) { _ in () }
    }

    private func post<Body: Encodable, Value>(_ path: String, body: Body, parse: (Data) throws -> Value) -> APIResult<Value> {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        do {
            request.httpBody = try JSONEncoder().encode(body)
        } catch {
            return .networkError(error)
        }

        let (responseData, response, error) = session.synchronousDataTask(with: request)
        if let error {
            return .networkError(error)
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        let data = responseData ?? Data()
        guard (200..<300).contains(status) else {
            return .httpError(code: status, body: String(decoding: data, as: UTF8.self))
        }
        do {
            return .success(try parse(data))
        } catch {
            return .networkError(error)
        }
    }
}
