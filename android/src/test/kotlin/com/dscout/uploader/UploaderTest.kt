package com.dscout.uploader

import com.dscout.uploader.db.FileUploadStore
import java.io.File
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull

class UploaderTest {
    private lateinit var dir: File
    private lateinit var uploader: Uploader

    @BeforeTest
    fun setUp() {
        Harness.reset()
        dir = tempDir()
        uploader = Uploader(testConfig(), FileUploadStore(File(dir, "uploads.json")))
    }

    @AfterTest
    fun tearDown() {
        uploader.close()
        dir.deleteRecursively()
    }

    @Test
    fun `single-part upload reaches the server intact`() {
        val file = mediaFile(dir, size = 500, name = "photo.jpg")

        val id = uploader.enqueue(file, entryId = "entry-1")

        eventually { uploader.status(id) == UploadStatus.DONE }
        val server = Harness.upload(assertNotNull(uploader.record(id)?.serverUploadId))
        assertEquals("complete", server.status)
        assertEquals(file.sha256(), server.sha256)
        assertEquals("entry-1", server.entryId)
    }

    @Test
    fun `multipart upload reaches the server intact`() {
        val file = mediaFile(dir, size = 5_000)

        val id = uploader.enqueue(file)

        eventually { uploader.status(id) == UploadStatus.DONE }
        val server = Harness.upload(assertNotNull(uploader.record(id)?.serverUploadId))
        assertEquals(5, server.parts)
        assertEquals("complete", server.status)
        assertEquals(file.sha256(), server.sha256)
    }

    @Test
    fun `uploads run in the order they were enqueued`() {
        val ids = (1..3).map { uploader.enqueue(mediaFile(dir, size = 2_000, name = "clip$it.mp4")) }

        eventually { ids.all { uploader.status(it) == UploadStatus.DONE } }
        val serverOrder = Harness.uploads().map { it.id }
        assertEquals(ids.map { uploader.record(it)?.serverUploadId }, serverOrder)
    }

    @Test
    fun `retries a part after a transient S3 error`() {
        Harness.addFault("""{"route":"s3","part":2,"action":{"type":"status","status":503}}""")
        val file = mediaFile(dir, size = 3_000)

        val id = uploader.enqueue(file)

        eventually { uploader.status(id) == UploadStatus.DONE }
        val server = Harness.upload(assertNotNull(uploader.record(id)?.serverUploadId))
        assertEquals("complete", server.status)
        assertEquals(file.sha256(), server.sha256)
    }
}
