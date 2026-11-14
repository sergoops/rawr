package com.rawr.camera.model

data class PerformanceHudState(
    val totalPssKb: Int = 0,
    val nativePssKb: Int = 0,
)

internal fun formatPerformanceHud(state: PerformanceHudState, queued: Int): String =
    "MEM ${state.totalPssKb / 1024}M  NAT ${state.nativePssKb / 1024}M  " +
        "Q ${queued.coerceAtLeast(0)}"
