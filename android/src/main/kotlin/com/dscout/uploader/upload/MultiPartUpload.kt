package com.dscout.uploader.upload

import com.dscout.uploader.api.ApiResult
import com.dscout.uploader.api.UploadApi
import com.dscout.uploader.db.UploadRecord
import com.dscout.uploader.db.UploadStore
import com.dscout.uploader.s3.S3Client
import com.dscout.uploader.s3.S3Errors
import java.io.File
import java.io.IOException

/**
 * Uploads remaining parts in order. Each part is PUT to S3, then its ETag is
 * reported to our server; the server completes the upload once it has every
 * part's ETag.
 */
class MultiPartUpload(
    store: UploadStore,
    record: UploadRecord,
    private val s3: S3Client,
    private val api: UploadApi,
    private val planner: PartPlanner,
) : BaseUpload(store, record) {

    override fun upload(): UploadResult {
        val file = File(record.filePath)
        val serverUploadId = record.serverUploadId ?: return UploadResult.RETRY

        while (true) {
            val part = store.nextPartToUpload(record.id) ?: break
            if (!file.exists()) {
                return UploadResult.FAILURE
            }

            val offset = planner.partOffset(part.partNumber)
            val length = planner.partLength(part.partNumber, record.fileSize, offset)

            val response = try {
                s3.put(part.url, file, offset, length)
            } catch (e: IOException) {
                return UploadResult.RETRY
            }

            if (!response.isSuccessful) {
                if (S3Errors.isExpired(response.body)) {
                    resetUploadState()
                }
                return UploadResult.RETRY
            }

            val etag = response.etag.orEmpty()
            store.markPartUploaded(record.id, part.partNumber, etag)
            record = record.copy(partsUploaded = record.partsUploaded + 1)
            store.update(record)

            when (api.reportPart(serverUploadId, part.partNumber, etag)) {
                is ApiResult.Success -> store.markEtagReported(record.id, part.partNumber)
                is ApiResult.HttpError, is ApiResult.NetworkError -> return UploadResult.RETRY
            }
        }

        onUploadComplete()
        return UploadResult.SUCCESS
    }
}
