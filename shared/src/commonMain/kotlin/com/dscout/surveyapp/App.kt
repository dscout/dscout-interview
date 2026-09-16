package com.dscout.surveyapp

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.dscout.surveyapp.model.Answer
import com.dscout.surveyapp.model.Question
import com.dscout.surveyapp.model.Survey
import com.dscout.surveyapp.model.SurveyResponse
import com.dscout.surveyapp.network.SurveyApi
import kotlinx.coroutines.launch

private sealed interface UiState {
    data object Loading : UiState
    data class Error(val message: String) : UiState
    data class InProgress(
        val survey: Survey,
        val questionIndex: Int,
        val answers: Map<String, Answer>,
    ) : UiState
    data object Submitting : UiState
    data class Confirmation(val survey: Survey, val answers: Map<String, Answer>) : UiState
}

@Composable
fun App() {
    var uiState by remember { mutableStateOf<UiState>(UiState.Loading) }
    val scope = rememberCoroutineScope()
    val api = remember { SurveyApi() }

    LaunchedEffect(Unit) {
        uiState = try {
            val survey = api.fetchSurvey()
            UiState.InProgress(survey, questionIndex = 0, answers = emptyMap())
        } catch (e: Exception) {
            UiState.Error("Backend not reachable: ${e.message}")
        }
    }

    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize().safeDrawingPadding()) {
            when (val state = uiState) {
                is UiState.Loading -> MessageScreen("Loading survey...")
                is UiState.Submitting -> MessageScreen("Submitting...")
                is UiState.Error -> MessageScreen(state.message)
                is UiState.Confirmation -> ConfirmationScreen(state.survey, state.answers)
                is UiState.InProgress -> SurveyScreen(
                    state = state,
                    onAnswerChanged = { answer ->
                        uiState = state.copy(answers = state.answers + (answer.questionId to answer))
                    },
                    onBack = {
                        if (state.questionIndex > 0) {
                            uiState = state.copy(questionIndex = state.questionIndex - 1)
                        }
                    },
                    onNext = {
                        if (state.questionIndex < state.survey.questions.lastIndex) {
                            uiState = state.copy(questionIndex = state.questionIndex + 1)
                        } else {
                            uiState = UiState.Submitting
                            scope.launch {
                                uiState = try {
                                    api.submitResponses(
                                        SurveyResponse(
                                            surveyId = state.survey.id,
                                            answers = state.answers.values.toList(),
                                        ),
                                    )
                                    UiState.Confirmation(state.survey, state.answers)
                                } catch (e: Exception) {
                                    UiState.Error("Submit failed: ${e.message}")
                                }
                            }
                        }
                    },
                )
            }
        }
    }
}

@Composable
private fun MessageScreen(message: String) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Survey App — ${platformName()}")
        Text(message)
    }
}

@Composable
private fun SurveyScreen(
    state: UiState.InProgress,
    onAnswerChanged: (Answer) -> Unit,
    onBack: () -> Unit,
    onNext: () -> Unit,
) {
    val question = state.survey.questions[state.questionIndex]
    val currentAnswer = state.answers[question.id]
    val isLastQuestion = state.questionIndex == state.survey.questions.lastIndex
    val canProceed = when (question.type) {
        "SINGLE_SELECT", "MULTI_SELECT" -> currentAnswer?.value != null
        "OPEN_TEXT" -> !currentAnswer?.value.isNullOrBlank()
        // Unrecognized question types can't be answered here, so don't
        // block the rest of the survey on one.
        else -> true
    }

    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text("Question ${state.questionIndex + 1} of ${state.survey.questions.size}")
        LinearProgressIndicator(
            progress = { (state.questionIndex + 1) / state.survey.questions.size.toFloat() },
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(modifier = Modifier.height(24.dp))
        Text(question.prompt)
        Spacer(modifier = Modifier.height(16.dp))
        QuestionContent(question, currentAnswer, onAnswerChanged)
        Spacer(modifier = Modifier.height(24.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedButton(onClick = onBack, enabled = state.questionIndex > 0) {
                Text("Back")
            }
            Button(onClick = onNext, enabled = canProceed) {
                Text(if (isLastQuestion) "Submit" else "Next")
            }
        }
    }
}

@Composable
private fun QuestionContent(
    question: Question,
    currentAnswer: Answer?,
    onAnswerChanged: (Answer) -> Unit,
) {
    when (question.type) {
        "SINGLE_SELECT" -> Column {
            question.options.orEmpty().forEach { option ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(
                        selected = currentAnswer?.value == option,
                        onClick = { onAnswerChanged(Answer(questionId = question.id, value = option)) },
                    )
                    Text(option)
                }
            }
        }

        "OPEN_TEXT" -> {
            // Held locally so the field stays responsive while typing instead of
            // waiting on a state hoist round-trip for every keystroke.
            var draft by remember { mutableStateOf(currentAnswer?.value.orEmpty()) }
            OutlinedTextField(
                value = draft,
                onValueChange = {
                    draft = it
                    onAnswerChanged(Answer(questionId = question.id, value = it))
                },
                label = { Text("Your answer") },
                modifier = Modifier.fillMaxWidth(),
            )
        }

        // Renders as checkboxes (implying multiple selections are possible),
        // but only ever tracks a single `value`, not a `values` set —
        // checking a second option silently replaces the first instead of
        // adding to it. Intentionally left this way for now.
        "MULTI_SELECT" -> Column {
            question.options.orEmpty().forEach { option ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(
                        checked = currentAnswer?.value == option,
                        onCheckedChange = { onAnswerChanged(Answer(questionId = question.id, value = option)) },
                    )
                    Text(option)
                }
            }
        }

        // Fallback for any question type this client doesn't know how to render.
        else -> Text("This question type isn't supported yet.")
    }
}

@Composable
private fun ConfirmationScreen(survey: Survey, answers: Map<String, Answer>) {
    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text("Thanks for completing \"${survey.title}\"!")
        Spacer(modifier = Modifier.height(16.dp))
        survey.questions.forEach { question ->
            val answer = answers[question.id]
            val summary = answer?.value ?: answer?.values?.joinToString() ?: "(no answer)"
            Text("${question.prompt}: $summary")
        }
    }
}
