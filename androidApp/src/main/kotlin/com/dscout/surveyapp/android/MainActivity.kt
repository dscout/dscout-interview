package com.dscout.surveyapp.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.dscout.surveyapp.App
import com.dscout.surveyapp.config.BackendConfig

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        BackendConfig.configure(getString(R.string.backend_base_url))
        setContent { App() }
    }
}
