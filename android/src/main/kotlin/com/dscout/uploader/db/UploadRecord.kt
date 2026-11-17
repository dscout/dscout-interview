package com.dscout.uploader.db

import kotlinx.serialization.Serializable

/**
 * One file the participant has captured and we owe the server.
 *
 * Mirrors the `upload` table in the production Room schema. State is tracked
 * with independent flags; see [com.dscout.uploader.status] for how the UI
 * reads them.
 */
@Serializable
data class UploadRecord(
    val id: Long = 0,
    val filePath: String,
    val fileSize: Long,
    /** The entry (answer) this media belongs to. Passed through at presign. */
    val entryId: String? = null,
    val createdAt: Long = System.currentTimeMillis(),

    val started: Boolean = false,
    val stopped: Boolean = false,
    val failed: Boolean = false,
    val onS3: Boolean = false,

    /** Server-side upload id, returned by presign. */
    val serverUploadId: String? = null,
    val partsTotal: Int = 0,
    val partsUploaded: Int = 0,
)

/** Mirrors the `media_upload_part` table. Single-part uploads have one row. */
@Serializable
data class UploadPart(
    val uploadId: Long,
    val partNumber: Int,
    /** Presigned PUT URL for this part. */
    val url: String,
    /** Bytes accepted by S3. */
    val uploaded: Boolean = false,
    val etag: String? = null,
    /** ETag acknowledged by our server. */
    val etagReported: Boolean = false,
)
