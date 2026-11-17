package com.dscout.uploader.upload

import com.dscout.uploader.db.UploadRecord
import com.dscout.uploader.db.UploadStore
import com.dscout.uploader.s3.S3Client
import com.dscout.uploader.s3.S3Errors
import java.io.File
import java.io.IOException

class SinglePartUpload(
    store: UploadStore,
    record: UploadRecord,
    private val s3: S3Client,
) : BaseUpload(store, record) {

    override fun upload(): UploadResult {
        val part = store.parts(record.id).firstOrNull() ?: return UploadResult.RETRY
        val file = File(record.filePath)
        if (!file.exists()) {
            return UploadResult.FAILURE
        }

        val response = try {
            s3.put(part.url, file)
        } catch (e: IOException) {
            return UploadResult.RETRY
        }

        if (S3Errors.isExpired(response.body)) {
            resetUploadState()
            return UploadResult.RETRY
        }

        // The server learns about single-part uploads from S3 directly; nothing to report.
        onUploadComplete()
        return UploadResult.SUCCESS
    }
}
