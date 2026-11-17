package com.dscout.uploader.upload

import com.dscout.uploader.api.UploadApi
import com.dscout.uploader.db.UploadStore
import com.dscout.uploader.s3.S3Client

/** Runs one upload as far as it can go: presign (if needed), then PUT bytes. */
class UploadLogic(
    private val store: UploadStore,
    private val presigner: MediaPresigner,
    private val s3: S3Client,
    private val api: UploadApi,
    private val planner: PartPlanner,
) {
    fun performUpload(id: Long): UploadResult {
        val record = store.get(id) ?: return UploadResult.FAILURE

        val presigned = presigner.presignIfNeeded(record)
        if (presigned != UploadResult.SUCCESS) {
            return presigned
        }

        // Re-read: presigning wrote the server id and part count.
        val current = store.get(id) ?: return UploadResult.FAILURE
        val upload = if (current.partsTotal == 1) {
            SinglePartUpload(store, current, s3)
        } else {
            MultiPartUpload(store, current, s3, api, planner)
        }
        return upload.upload()
    }
}
