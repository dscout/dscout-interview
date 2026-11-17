package com.dscout.uploader

import com.dscout.uploader.upload.PartPlanner
import kotlin.test.Test
import kotlin.test.assertEquals

class PartPlannerTest {
    private val planner = PartPlanner(partSize = 100, maxParts = 1000)

    @Test
    fun `files smaller than a part are a single part`() {
        assertEquals(1, planner.partCount(99))
    }

    @Test
    fun `parts are fixed size with a short last part`() {
        assertEquals(3, planner.partCount(250))
        assertEquals(0, planner.partOffset(1))
        assertEquals(200, planner.partOffset(3))
        assertEquals(100, planner.partLength(1, 250, 0))
        assertEquals(50, planner.partLength(3, 250, 200))
    }

    @Test
    fun `an exact multiple has no empty trailing part`() {
        assertEquals(2, planner.partCount(200))
        assertEquals(100, planner.partLength(2, 200, 100))
    }
}
