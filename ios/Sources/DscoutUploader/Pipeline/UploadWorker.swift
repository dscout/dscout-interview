import Foundation

/// Processes pending uploads one at a time on a serial queue. In the app the
/// host calls `start()` when the scene becomes active, after a questionnaire
/// is submitted, and from the background processing task.
///
/// Each pass walks pending uploads in id order. If any asked to be retried,
/// another pass is scheduled after a delay.
final class UploadWorker {
    private let store: UploadStore
    private let logic: UploadLogic
    private let retryDelay: TimeInterval
    private let queue = DispatchQueue(label: "com.dscout.uploader.worker")
    private let lock = NSLock()
    private var running = false
    private var retryScheduled = false
    private var invalidated = false

    init(store: UploadStore, logic: UploadLogic, retryDelay: TimeInterval) {
        self.store = store
        self.logic = logic
        self.retryDelay = retryDelay
    }

    var isRunning: Bool {
        lock.lock()
        defer { lock.unlock() }
        return running
    }

    func start() {
        lock.lock()
        // A retry pass is already scheduled; it will pick everything up.
        if retryScheduled || running || invalidated {
            lock.unlock()
            return
        }
        running = true
        lock.unlock()

        queue.async { [weak self] in
            self?.runPass()
        }
    }

    /// Stops scheduling further passes. The upload in flight, if any, finishes.
    func invalidate() {
        lock.lock()
        invalidated = true
        lock.unlock()
    }

    private func runPass() {
        var needsRetry = false
        var lastID: Int64 = 0
        while !isInvalidated, let next = store.nextPending(after: lastID) {
            lastID = next.id
            switch logic.performUpload(id: next.id) {
            case .success, .failure:
                break
            case .retry:
                needsRetry = true
            }
        }

        lock.lock()
        running = false
        retryScheduled = needsRetry
        lock.unlock()

        if needsRetry {
            queue.asyncAfter(deadline: .now() + retryDelay) { [weak self] in
                guard let self else { return }
                self.lock.lock()
                self.retryScheduled = false
                self.lock.unlock()
                self.start()
            }
        }
    }

    private var isInvalidated: Bool {
        lock.lock()
        defer { lock.unlock() }
        return invalidated
    }
}
