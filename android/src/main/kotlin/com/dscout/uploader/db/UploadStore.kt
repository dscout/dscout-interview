package com.dscout.uploader.db

/**
 * Persistence for uploads and their parts. Stands in for the Room DAOs
 * (`UploadDao`, `MediaUploadPartDao`) in the production app.
 */
interface UploadStore {
    fun insert(record: UploadRecord): Long
    fun get(id: Long): UploadRecord?
    fun all(): List<UploadRecord>
    fun update(record: UploadRecord)

    /** started = true, stopped = false */
    fun startUpload(id: Long)

    /** stopped = true */
    fun stopUpload(id: Long)

    /** failed = true */
    fun markFailed(id: Long)

    /** Clears all presign/progress state so the upload starts over. */
    fun resetUpload(id: Long)

    /** Lowest-id upload after [afterId] that is started, not stopped, not failed, and not on S3. */
    fun nextPending(afterId: Long): UploadRecord?
    fun pendingCount(): Int

    fun parts(uploadId: Long): List<UploadPart>
    fun replaceParts(uploadId: Long, parts: List<UploadPart>)
    fun nextPartToUpload(uploadId: Long): UploadPart?
    fun markPartUploaded(uploadId: Long, partNumber: Int, etag: String)
    fun markEtagReported(uploadId: Long, partNumber: Int)
    fun deleteParts(uploadId: Long)
}
