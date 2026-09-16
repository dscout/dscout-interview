rootProject.name = "dscout-interview"

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
}

// iosApp is an Xcode project, not a Gradle module — it is not included here.
include(":shared")
include(":androidApp")
