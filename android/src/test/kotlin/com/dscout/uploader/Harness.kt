package com.dscout.uploader

import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Test access to the Node upload harness in ../backend.
 *
 * By default the first test to touch [Harness] boots `node src/server.js` on a
 * free port, logging to build/harness.log. Set HARNESS_URL to point at one
 * you're already running instead (e.g. `npm run dev` to watch its log).
 */
object Harness {
    val url: String by lazy { System.getenv("HARNESS_URL") ?: boot() }

    private val client = OkHttpClient()
    private val json = Json { ignoreUnknownKeys = true }
    private val jsonType = "application/json".toMediaType()

    /** Clears uploads, faults, and config. Call before each test. */
    fun reset() = send("POST", "/__reset", "{}")

    /**
     * Registers a fault rule; see backend/src/faults.js for the shape, e.g.
     * `addFault("""{"route":"s3","part":2,"action":{"type":"status","status":500}}""")`
     */
    fun addFault(ruleJson: String) = send("POST", "/__faults", ruleJson)

    fun setUrlTtlSeconds(seconds: Int) = send("PUT", "/__config", """{"urlTtlSeconds":$seconds}""")

    fun upload(id: String): ServerUpload = json.decodeFromString(send("GET", "/uploads/$id"))

    fun uploads(): List<ServerUpload> = json.decodeFromString(send("GET", "/uploads"))

    private fun send(method: String, path: String, body: String? = null): String {
        val request = Request.Builder()
            .url(url + path)
            .method(method, body?.toRequestBody(jsonType))
            .build()
        client.newCall(request).execute().use { response ->
            val text = response.body?.string().orEmpty()
            check(response.isSuccessful) { "$method $path -> ${response.code}: $text" }
            return text
        }
    }

    private fun boot(): String {
        val dir = File(System.getProperty("harness.dir") ?: "../backend")
        check(File(dir, "node_modules").exists()) {
            "Harness dependencies missing. Run `npm install` in ${dir.canonicalPath} first."
        }
        val log = File("build/harness.log").apply { parentFile.mkdirs(); delete() }
        val process = ProcessBuilder("node", "src/server.js")
            .directory(dir)
            .redirectErrorStream(true)
            .redirectOutput(log)
            .apply { environment()["PORT"] = "0" }
            .start()
        Runtime.getRuntime().addShutdownHook(Thread { process.destroy() })

        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10)
        val pattern = Regex("listening on (http://\\S+)")
        while (System.nanoTime() < deadline) {
            pattern.find(log.readText())?.let { return it.groupValues[1] }
            check(process.isAlive) { "Harness exited early:\n${log.readText()}" }
            Thread.sleep(50)
        }
        error("Harness didn't start within 10s:\n${log.readText()}")
    }
}

@Serializable
data class ServerUpload(
    val id: String,
    val key: String,
    val filename: String,
    val entryId: String? = null,
    val size: Long,
    val parts: Int,
    val multipart: Boolean,
    /** "pending" | "complete" | "failed" */
    val status: String,
    val failureReason: String? = null,
    val partsStored: List<Int>,
    val partsReported: List<Int>,
    val assembledSize: Long? = null,
    val sha256: String? = null,
)
