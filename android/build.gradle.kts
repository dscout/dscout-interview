// Plain Kotlin/JVM so `./gradlew test` runs anywhere with a JDK — no Android
// SDK or emulator. In the real app this engine sits behind a foreground
// service; see AGENTS.md for what's simulated here.
plugins {
    kotlin("jvm") version "2.2.0"
    kotlin("plugin.serialization") version "2.2.0"
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
    // Tests boot the Node harness from ../backend (see HarnessServer).
    systemProperty("harness.dir", rootDir.resolve("../backend").absolutePath)
    testLogging {
        events("passed", "failed", "skipped")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
