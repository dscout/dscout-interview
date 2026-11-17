package com.dscout.uploader

data class UploaderConfig(
    val baseUrl: String,
    /** S3 requires every part but the last to be at least 5 MiB; the harness doesn't. */
    val partSize: Int = 5 * 1024 * 1024,
    val maxParts: Int = 1000,
    /** How long to wait before another pass when any upload asked to be retried. */
    val retryDelayMillis: Long = 5 * 60 * 1000,
)
