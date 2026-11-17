package com.dscout.uploader.upload

import com.dscout.uploader.db.UploadRecord
import com.dscout.uploader.db.UploadStore

/** Shared bookkeeping for [SinglePartUpload] and [MultiPartUpload]. Port of `AbsUpload`. */
abstract class BaseUpload(
    protected val store: UploadStore,
    protected var record: UploadRecord,
) {
    abstract fun upload(): UploadResult

    protected fun onUploadComplete() {
        record = record.copy(onS3 = true, partsUploaded = record.partsTotal)
        store.update(record)
        store.deleteParts(record.id)
    }

    /** Throw away presign state (e.g. after URLs expire) so the next pass presigns again. */
    protected fun resetUploadState() {
        store.deleteParts(record.id)
        store.resetUpload(record.id)
        store.startUpload(record.id)
    }
}
