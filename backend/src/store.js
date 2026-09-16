// In-memory only — data resets on every server restart. That's intentional
// for this exercise; there is no database to install or configure.

// Flat, stringly-typed question shape (type as a string, type-specific
// fields directly on the question) rather than a discriminated/class
// hierarchy — kept small enough to read in minutes.
let survey = {
  id: "survey-1",
  title: "Sample Survey",
  questions: [
    {
      id: "q1",
      prompt: "Which platform do you primarily develop for?",
      type: "SINGLE_SELECT",
      options: ["Android", "iOS", "Both equally"],
    },
    {
      id: "q2",
      prompt: "Which of these have you used in production?",
      type: "MULTI_SELECT",
      options: [
        "Kotlin Multiplatform",
        "SwiftUI",
        "Jetpack Compose",
        "REST APIs",
      ],
    },
    {
      id: "q3",
      prompt: "What's one thing you'd improve about this app?",
      type: "OPEN_TEXT",
    },
    {
      id: "q4",
      prompt: "Anything else you'd like the team to know?",
      type: "OPEN_TEXT",
    },
  ],
};

let responses = [];

export function getSurvey() {
  return survey;
}

export function addResponse(response) {
  const stored = {
    id: `response-${responses.length + 1}`,
    receivedAt: new Date().toISOString(),
    ...response,
  };
  responses.push(stored);
  return stored;
}

export function getResponses() {
  return responses;
}
