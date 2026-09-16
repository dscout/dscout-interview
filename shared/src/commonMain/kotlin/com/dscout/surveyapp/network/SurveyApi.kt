package com.dscout.surveyapp.network

import com.dscout.surveyapp.config.BackendConfig
import com.dscout.surveyapp.model.StoredResponse
import com.dscout.surveyapp.model.Survey
import com.dscout.surveyapp.model.SurveyResponse
import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.get
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json

class SurveyApi(
    private val baseUrl: String = BackendConfig.requireBaseUrl(),
    private val client: HttpClient = HttpClient {
        install(ContentNegotiation) { json() }
    },
) {
    suspend fun fetchSurvey(): Survey =
        client.get("$baseUrl/survey").body()

    suspend fun submitResponses(response: SurveyResponse): StoredResponse =
        client.post("$baseUrl/responses") {
            contentType(ContentType.Application.Json)
            setBody(response)
        }.body()
}
