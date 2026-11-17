package com.dscout.uploader.upload

import com.dscout.uploader.api.ApiResult
import com.dscout.uploader.api.PresignRequest
import com.dscout.uploader.api.UploadApi
import com.dscout.uploader.db.UploadPart
import com.dscout.uploader.db.UploadRecord
import com.dscout.uploader.db.UploadStore
import java.io.File

class MediaPresigner(
    private val store: UploadStore,
    private val api: UploadApi,
    private val planner: PartPlanner,
) {
    fun presignIfNeeded(record: UploadRecord): UploadResult {
        // Already presigned on an earlier pass; resume with the stored part URLs.
        if (store.parts(record.id).isNotEmpty()) {
            return UploadResult.SUCCESS
        }

        val file = File(record.filePath)
        if (!file.exists()) {
            return UploadResult.FAILURE
        }

        val partCount = planner.partCount(record.fileSize)
        val request = PresignRequest(
            filename = file.name,
            size = record.fileSize,
            parts = if (partCount > 1) partCount else null,
            entryId = record.entryId,
        )

        return when (val result = api.presign(request)) {
            is ApiResult.Success -> {
                val presign = result.value
                val urls = presign.partUrls ?: listOfNotNull(presign.url)
                store.replaceParts(
                    record.id,
                    urls.mapIndexed { index, url ->
                        UploadPart(uploadId = record.id, partNumber = index + 1, url = url)
                    },
                )
                store.update(
                    record.copy(
                        serverUploadId = presign.id,
                        partsTotal = urls.size,
                        partsUploaded = 0,
                    ),
                )
                UploadResult.SUCCESS
            }

            is ApiResult.HttpError -> {
                if (result.code == 404) {
                    store.markFailed(record.id)
                    UploadResult.FAILURE
                } else {
                    UploadResult.RETRY
                }
            }

            is ApiResult.NetworkError -> UploadResult.RETRY
        }
    }
}
