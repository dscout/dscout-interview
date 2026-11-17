package com.dscout.uploader

import com.dscout.uploader.db.FileUploadStore
import com.dscout.uploader.db.UploadPart
import com.dscout.uploader.db.UploadRecord
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class FileUploadStoreTest {

    @Test
    fun `state survives a new store instance on the same file`() {
        val file = File(tempDir(), "uploads.json")
        val store = FileUploadStore(file)
        val id = store.insert(UploadRecord(filePath = "/tmp/a.mp4", fileSize = 10))
        store.startUpload(id)
        store.replaceParts(id, listOf(UploadPart(id, 1, "http://a"), UploadPart(id, 2, "http://b")))
        store.markPartUploaded(id, 1, "\"etag-1\"")
        store.markEtagReported(id, 1)

        val reopened = FileUploadStore(file)

        assertEquals(true, reopened.get(id)?.started)
        assertEquals(2, reopened.nextPartToUpload(id)?.partNumber)
        assertEquals(id + 1, reopened.insert(UploadRecord(filePath = "/tmp/b.mp4", fileSize = 1)))
    }

    @Test
    fun `nextPending skips stopped and finished uploads`() {
        val store = FileUploadStore(File(tempDir(), "uploads.json"))
        val stopped = store.insert(UploadRecord(filePath = "a", fileSize = 1))
        val done = store.insert(UploadRecord(filePath = "b", fileSize = 1))
        val pending = store.insert(UploadRecord(filePath = "c", fileSize = 1))
        listOf(stopped, done, pending).forEach(store::startUpload)
        store.stopUpload(stopped)
        store.update(store.get(done)!!.copy(onS3 = true))

        assertEquals(pending, store.nextPending(afterId = 0)?.id)
        assertNull(store.nextPending(afterId = pending))
        assertEquals(1, store.pendingCount())
    }
}
