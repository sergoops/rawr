package com.rawr.camera.model

import org.junit.Assert.assertEquals
import org.junit.Test

class PerformanceHudTest {
    @Test
    fun formatsMemoryAndQueue() {
        val state = PerformanceHudState(
            totalPssKb = 290_816,
            nativePssKb = 65_536,
        )

        assertEquals("MEM 284M  NAT 64M  Q 2", formatPerformanceHud(state, queued = 2))
    }

    @Test
    fun zeroSampleStillFormats() {
        assertEquals(
            "MEM 0M  NAT 0M  Q 0",
            formatPerformanceHud(PerformanceHudState(), queued = 0),
        )
    }
}
