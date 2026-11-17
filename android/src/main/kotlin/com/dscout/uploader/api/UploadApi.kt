package com.dscout.uploader.api

import kotlinx.serialization.Serializable
import java.io.IOException

sealed interface ApiResult<out T> {
    data class Success<T>(val value: T) : ApiResult<T>
    data class HttpError(val code: Int, val body: String) : ApiResult<Nothing>
    data class NetworkError(val cause: IOException) : ApiResult<Nothing>
}

@Serializable
data class PresignRequest(
    val filename: String,
    val size: Long,
    /** Omitted for single-part uploads. */
    val parts: Int? = null,
    val entryId: String? = null,
)

@Serializable
data class PresignResponse(
    val id: String,
    val key: String,
    val parts: Int,
    /** Set for single-part uploads. */
    val url: String? = null,
    /** Set for multipart uploads; index 0 is part 1. */
    val partUrls: List<String>? = null,
)

/** Our backend (not S3). See backend/AGENTS.md for the contract. */
interface UploadApi {
    fun presign(request: PresignRequest): ApiResult<PresignResponse>

    fun reportPart(uploadId: String, partNumber: Int, etag: String): ApiResult<Unit>
}
