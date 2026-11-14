package com.rawr.camera.integration

import android.os.Debug

data class ProcessMemorySample(
    val totalPssKb: Int = 0,
    val nativePssKb: Int = 0,
)

/** Reads this process's PSS without waking any native capture state. */
internal class ProcessMemoryReader {
    private val info = Debug.MemoryInfo()

    fun read(): ProcessMemorySample {
        Debug.getMemoryInfo(info)
        return ProcessMemorySample(
            totalPssKb = info.totalPss,
            nativePssKb = info.nativePss,
        )
    }
}
