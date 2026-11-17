package com.dscout.uploader.upload

enum class UploadResult {
    SUCCESS,

    /** Try again on a later pass. */
    RETRY,

    /** Give up on this upload. */
    FAILURE,
}
