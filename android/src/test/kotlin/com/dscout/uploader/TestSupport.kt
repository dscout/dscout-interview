package com.dscout.uploader

import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import kotlin.random.Random

/** A file of random bytes with a media extension the harness accepts. */
fun mediaFile(dir: File, size: Int, name: String = "clip.mp4"): File =
    File(dir, name).apply { writeBytes(Random.nextBytes(size)) }

fun tempDir(): File = Files.createTempDirectory("uploader-test").toFile()

fun File.sha256(): String =
    MessageDigest.getInstance("SHA-256").digest(readBytes()).joinToString("") { "%02x".format(it) }

/** Polls [condition] until it's true or [timeoutMillis] passes. */
fun eventually(timeoutMillis: Long = 5_000, message: () -> String = { "condition not met" }, condition: () -> Boolean) {
    val deadline = System.currentTimeMillis() + timeoutMillis
    while (System.currentTimeMillis() < deadline) {
        if (condition()) return
        Thread.sleep(25)
    }
    throw AssertionError("Timed out after ${timeoutMillis}ms: ${message()}")
}

/** Small parts so multipart paths run on tiny files. */
fun testConfig(
    partSize: Int = 1024,
    maxParts: Int = 1000,
    retryDelayMillis: Long = 100,
) = UploaderConfig(
    baseUrl = Harness.url,
    partSize = partSize,
    maxParts = maxParts,
    retryDelayMillis = retryDelayMillis,
)
