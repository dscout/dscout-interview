package com.dscout.uploader.worker

import com.dscout.uploader.db.UploadStore
import com.dscout.uploader.upload.UploadLogic
import com.dscout.uploader.upload.UploadResult
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Processes pending uploads one at a time. Port of `UploadServiceLogicImpl`:
 * in the app this runs inside the foreground `UploadService`, which calls
 * [start] on launch, on connectivity regained, and from the hourly heartbeat.
 *
 * Each pass walks pending uploads in id order. If any asked to be retried,
 * another pass is scheduled after a delay.
 */
class UploadWorker(
    private val store: UploadStore,
    private val logic: UploadLogic,
    private val scope: CoroutineScope,
    private val retryDelayMillis: Long,
) {
    private val running = AtomicBoolean(false)
    private var retryJob: Job? = null

    val isRunning: Boolean get() = running.get()

    fun start() {
        // A retry pass is already scheduled; it will pick everything up.
        if (retryJob?.isActive == true) return
        if (!running.compareAndSet(false, true)) return

        scope.launch {
            var needsRetry = false
            var lastId = 0L
            while (true) {
                val next = store.nextPending(afterId = lastId) ?: break
                lastId = next.id
                when (logic.performUpload(next.id)) {
                    UploadResult.SUCCESS -> Unit
                    UploadResult.RETRY -> needsRetry = true
                    UploadResult.FAILURE -> Unit
                }
            }
            running.set(false)
            if (needsRetry) scheduleRetry()
        }
    }

    private fun scheduleRetry() {
        retryJob = scope.launch {
            delay(retryDelayMillis)
            retryJob = null
            start()
        }
    }
}
