package com.dscout.uploader.api

import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException

class HttpUploadApi(
    private val baseUrl: String,
    private val client: OkHttpClient,
) : UploadApi {

    @Serializable
    private data class ReportPartBody(val partNumber: Int, val etag: String)

    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
    private val jsonType = "application/json".toMediaType()

    override fun presign(request: PresignRequest): ApiResult<PresignResponse> =
        post("/uploads", json.encodeToString(request)) { json.decodeFromString<PresignResponse>(it) }

    override fun reportPart(uploadId: String, partNumber: Int, etag: String): ApiResult<Unit> =
        post("/uploads/$uploadId/parts", json.encodeToString(ReportPartBody(partNumber, etag))) { }

    private fun <T> post(path: String, body: String, parse: (String) -> T): ApiResult<T> {
        val request = Request.Builder()
            .url(baseUrl.trimEnd('/') + path)
            .post(body.toRequestBody(jsonType))
            .build()
        return try {
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (response.isSuccessful) {
                    ApiResult.Success(parse(text))
                } else {
                    ApiResult.HttpError(response.code, text)
                }
            }
        } catch (e: IOException) {
            ApiResult.NetworkError(e)
        }
    }
}
