package com.dscout.uploader.upload

import kotlin.math.ceil
import kotlin.math.min

/** Splits a file into fixed-size parts for multipart upload. Port of `PresignUtils`. */
class PartPlanner(
    private val partSize: Int,
    private val maxParts: Int,
) {
    fun partCount(fileSize: Long): Int {
        if (fileSize < partSize) {
            return 1
        }
        val count = ceil(fileSize.toFloat() / partSize).toInt()
        return min(count, maxParts)
    }

    fun partOffset(partNumber: Int): Long = ((partNumber - 1) * partSize).toLong()

    fun partLength(partNumber: Int, fileSize: Long, offset: Long): Long =
        if (offset + partSize < fileSize) {
            partSize.toLong()
        } else {
            fileSize - offset
        }
}
