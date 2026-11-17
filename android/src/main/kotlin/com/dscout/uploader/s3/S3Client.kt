package com.dscout.uploader.s3

import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okio.BufferedSink
import okio.buffer
import okio.source
import java.io.File
import java.io.IOException

data class S3Response(val code: Int, val etag: String?, val body: String) {
    val isSuccessful: Boolean get() = code in 200..299
}

/** Raw PUTs to presigned URLs. No AWS SDK — the URL carries the credentials. */
class S3Client(private val client: OkHttpClient) {

    @Throws(IOException::class)
    fun put(url: String, file: File, offset: Long = 0, length: Long = file.length()): S3Response {
        val request = Request.Builder()
            .url(url)
            .put(FileRangeBody(file, offset, length, contentTypeFor(file)))
            .build()
        client.newCall(request).execute().use { response ->
            return S3Response(
                code = response.code,
                etag = response.header("ETag"),
                body = response.body?.string().orEmpty(),
            )
        }
    }

    private fun contentTypeFor(file: File): MediaType? = when (file.extension.lowercase()) {
        "mp4", "m4v" -> "video/mp4"
        "mov" -> "video/quicktime"
        "webm" -> "video/webm"
        "jpg", "jpeg" -> "image/jpeg"
        "png" -> "image/png"
        "heic" -> "image/heic"
        "m4a" -> "audio/mp4"
        else -> "application/octet-stream"
    }.toMediaTypeOrNull()

    /** Streams [length] bytes of [file] starting at [offset]. */
    private class FileRangeBody(
        private val file: File,
        private val offset: Long,
        private val length: Long,
        private val contentType: MediaType?,
    ) : RequestBody() {
        override fun contentType() = contentType
        override fun contentLength() = length
        override fun writeTo(sink: BufferedSink) {
            file.source().buffer().use { source ->
                source.skip(offset)
                sink.write(source, length)
            }
        }
    }
}

object S3Errors {
    fun isExpired(body: String): Boolean = body.contains("Request has expired")
}
