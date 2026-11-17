package com.dscout.uploader.db

import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File

/**
 * [UploadStore] backed by a JSON file, rewritten on every change. Survives
 * process death the same way the Room database does: construct a new store
 * on the same file and everything is still there.
 */
class FileUploadStore(private val file: File) : UploadStore {

    @Serializable
    private data class Snapshot(
        val nextId: Long = 1,
        val uploads: List<UploadRecord> = emptyList(),
        val parts: List<UploadPart> = emptyList(),
    )

    private val json = Json { ignoreUnknownKeys = true; prettyPrint = true }
    private val uploads = linkedMapOf<Long, UploadRecord>()
    private val parts = mutableListOf<UploadPart>()
    private var nextId = 1L

    init {
        if (file.exists() && file.length() > 0) {
            val snapshot = json.decodeFromString<Snapshot>(file.readText())
            nextId = snapshot.nextId
            snapshot.uploads.forEach { uploads[it.id] = it }
            parts += snapshot.parts
        }
    }

    @Synchronized
    override fun insert(record: UploadRecord): Long {
        val id = nextId++
        uploads[id] = record.copy(id = id)
        persist()
        return id
    }

    @Synchronized
    override fun get(id: Long): UploadRecord? = uploads[id]

    @Synchronized
    override fun all(): List<UploadRecord> = uploads.values.toList()

    @Synchronized
    override fun update(record: UploadRecord) {
        if (record.id !in uploads) return
        uploads[record.id] = record
        persist()
    }

    override fun startUpload(id: Long) = modify(id) { it.copy(started = true, stopped = false) }

    override fun stopUpload(id: Long) = modify(id) { it.copy(stopped = true) }

    override fun markFailed(id: Long) = modify(id) { it.copy(failed = true) }

    override fun resetUpload(id: Long) = modify(id) {
        it.copy(
            started = false,
            stopped = false,
            failed = false,
            onS3 = false,
            serverUploadId = null,
            partsTotal = 0,
            partsUploaded = 0,
        )
    }

    @Synchronized
    override fun nextPending(afterId: Long): UploadRecord? =
        uploads.values
            .filter { it.id > afterId && it.isPending() }
            .minByOrNull { it.id }

    @Synchronized
    override fun pendingCount(): Int = uploads.values.count { it.isPending() }

    @Synchronized
    override fun parts(uploadId: Long): List<UploadPart> =
        parts.filter { it.uploadId == uploadId }.sortedBy { it.partNumber }

    @Synchronized
    override fun replaceParts(uploadId: Long, parts: List<UploadPart>) {
        this.parts.removeAll { it.uploadId == uploadId }
        this.parts += parts
        persist()
    }

    @Synchronized
    override fun nextPartToUpload(uploadId: Long): UploadPart? =
        parts.filter { it.uploadId == uploadId && !it.uploaded }.minByOrNull { it.partNumber }

    override fun markPartUploaded(uploadId: Long, partNumber: Int, etag: String) =
        modifyPart(uploadId, partNumber) { it.copy(uploaded = true, etag = etag) }

    override fun markEtagReported(uploadId: Long, partNumber: Int) =
        modifyPart(uploadId, partNumber) { it.copy(etagReported = true) }

    @Synchronized
    override fun deleteParts(uploadId: Long) {
        parts.removeAll { it.uploadId == uploadId }
        persist()
    }

    private fun UploadRecord.isPending() = started && !stopped && !failed && !onS3

    @Synchronized
    private fun modify(id: Long, change: (UploadRecord) -> UploadRecord) {
        val current = uploads[id] ?: return
        uploads[id] = change(current)
        persist()
    }

    @Synchronized
    private fun modifyPart(uploadId: Long, partNumber: Int, change: (UploadPart) -> UploadPart) {
        val index = parts.indexOfFirst { it.uploadId == uploadId && it.partNumber == partNumber }
        if (index == -1) return
        parts[index] = change(parts[index])
        persist()
    }

    private fun persist() {
        file.parentFile?.mkdirs()
        val tmp = File(file.path + ".tmp")
        tmp.writeText(json.encodeToString(Snapshot(nextId, uploads.values.toList(), parts.toList())))
        tmp.renameTo(file)
    }
}
