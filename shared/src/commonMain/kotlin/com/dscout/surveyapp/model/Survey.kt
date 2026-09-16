package com.dscout.surveyapp.model

import kotlinx.serialization.Serializable

// Flat, stringly-typed shape (type as a string, type-specific fields
// directly on the question) rather than a discriminated/class hierarchy —
// kept small enough to read in minutes.
@Serializable
data class Survey(
    val id: String,
    val title: String,
    val questions: List<Question>,
)

@Serializable
data class Question(
    val id: String,
    val prompt: String,
    val type: String, // "SINGLE_SELECT" | "MULTI_SELECT" | "OPEN_TEXT"
    val options: List<String>? = null, // SINGLE_SELECT / MULTI_SELECT
)

@Serializable
data class Answer(
    val questionId: String,
    val value: String? = null, // SINGLE_SELECT / OPEN_TEXT
    val values: List<String>? = null, // MULTI_SELECT
)

@Serializable
data class SurveyResponse(
    val surveyId: String,
    val answers: List<Answer>,
)

@Serializable
data class StoredResponse(
    val id: String,
    val receivedAt: String,
    val surveyId: String,
    val answers: List<Answer>,
)
