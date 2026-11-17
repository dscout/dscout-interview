import Foundation

extension URLSession {
    /// Blocks the calling queue until the request finishes. The pipeline runs on
    /// its own serial queue, so waiting there is fine (and keeps one upload in
    /// flight at a time).
    func synchronousDataTask(with request: URLRequest, body: Data? = nil) -> (Data?, URLResponse?, Error?) {
        let semaphore = DispatchSemaphore(value: 0)
        var result: (Data?, URLResponse?, Error?) = (nil, nil, nil)
        let completion: (Data?, URLResponse?, Error?) -> Void = { data, response, error in
            result = (data, response, error)
            semaphore.signal()
        }
        let task = body.map { uploadTask(with: request, from: $0, completionHandler: completion) }
            ?? dataTask(with: request, completionHandler: completion)
        task.resume()
        semaphore.wait()
        return result
    }
}
