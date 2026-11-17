enum UploadResult {
    case success
    /// Try again on a later pass.
    case retry
    /// Give up on this upload.
    case failure
}
