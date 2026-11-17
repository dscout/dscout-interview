package com.dscout.uploader

import com.dscout.uploader.api.HttpUploadApi
import com.dscout.uploader.api.UploadApi
import com.dscout.uploader.db.UploadRecord
import com.dscout.uploader.db.UploadStore
import com.dscout.uploader.s3.S3Client
import com.dscout.uploader.upload.MediaPresigner
import com.dscout.uploader.upload.PartPlanner
import com.dscout.uploader.upload.UploadLogic
import com.dscout.uploader.worker.UploadWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import okhttp3.OkHttpClient
import java.io.File
import java.util.concurrent.TimeUnit

enum class UploadStatus { CREATED, QUEUED, PAUSED, FAILED, DONE }

fun UploadRecord.status(): UploadStatus = when {
    onS3 -> UploadStatus.DONE
    failed -> UploadStatus.FAILED
    stopped -> UploadStatus.PAUSED
    started -> UploadStatus.QUEUED
    else -> UploadStatus.CREATED
}

/**
 * Entry point for the rest of the app. Questionnaire code calls [enqueue] when
 * the participant captures media; the host calls [start] whenever uploads
 * might be able to make progress (app launch, connectivity regained).
 */
class Uploader(
    config: UploaderConfig,
    private val store: UploadStore,
    httpClient: OkHttpClient = defaultHttpClient(),
    api: UploadApi = HttpUploadApi(config.baseUrl, httpClient),
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
) {
    private val planner = PartPlanner(config.partSize, config.maxParts)
    private val s3 = S3Client(httpClient)
    private val logic = UploadLogic(store, MediaPresigner(store, api, planner), s3, api, planner)
    private val worker = UploadWorker(store, logic, scope, config.retryDelayMillis)

    val isRunning: Boolean get() = worker.isRunning

    fun enqueue(file: File, entryId: String? = null): Long {
        val id = store.insert(
            UploadRecord(filePath = file.absolutePath, fileSize = file.length(), entryId = entryId),
        )
        upload(id)
        return id
    }

    /** Starts (or resumes a paused) upload. */
    fun upload(id: Long) {
        val record = store.get(id) ?: return
        if (record.started && !record.stopped) return
        store.startUpload(id)
        worker.start()
    }

    /** Pauses an upload. Resume with [upload]. */
    fun cancel(id: Long) {
        store.stopUpload(id)
    }

    fun start() = worker.start()

    fun status(id: Long): UploadStatus? = store.get(id)?.status()

    /** 0.0–1.0, at part granularity. */
    fun progress(id: Long): Float {
        val record = store.get(id) ?: return 0f
        if (record.onS3) return 1f
        if (record.partsTotal == 0) return 0f
        return record.partsUploaded.toFloat() / record.partsTotal
    }

    fun record(id: Long): UploadRecord? = store.get(id)

    fun pendingCount(): Int = store.pendingCount()

    fun close() = scope.cancel()

    companion object {
        fun defaultHttpClient(): OkHttpClient = OkHttpClient.Builder()
            .writeTimeout(5, TimeUnit.MINUTES)
            .build()
    }
}
