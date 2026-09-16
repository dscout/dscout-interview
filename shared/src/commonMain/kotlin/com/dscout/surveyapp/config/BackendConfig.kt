package com.dscout.surveyapp.config

/**
 * Holds the backend base URL for the current build.
 *
 * The value can't live in `shared` as a constant because it differs per
 * platform (and per environment), so each app host supplies it during
 * startup instead — see `MainActivity` on Android and `iosAppApp` on iOS.
 */
object BackendConfig {
    private var baseUrl: String? = null

    fun configure(baseUrl: String) {
        this.baseUrl = baseUrl
    }

    /** The host configures this before any UI is shown. */
    fun requireBaseUrl(): String = baseUrl!!
}
