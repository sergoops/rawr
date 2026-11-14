package com.rawr.camera.integration

import com.rawr.camera.model.CaptureOutputFormat
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Serializes provider preparation and completion publication away from the shutter caller. */
internal class StillCaptureDispatchQueue(
    scope: CoroutineScope,
    private val onQueued: (CaptureOutputFormat) -> Unit,
    private val capture: (CaptureOutputFormat) -> Unit,
    private val onRejected: (CaptureOutputFormat, RuntimeException?) -> Unit
) {
    private val requests = Channel<CaptureOutputFormat>(Channel.UNLIMITED)
    private val mutex = Mutex()
    private val pending = AtomicInteger(0)

    init {
        scope.launch {
            for (format in requests) {
                try {
                    mutex.withLock { capture(format) }
                } finally {
                    pending.decrementAndGet()
                }
            }
        }
    }

    fun depth(): Int = pending.get()

    /** Admits synchronously in press order when [owned] still holds; returns whether the request was queued. */
    @Synchronized
    fun enqueue(format: CaptureOutputFormat, owned: () -> Boolean = { true }): Boolean {
        try {
            if (!owned()) {
                onRejected(format, null)
                return false
            }
            onQueued(format)
            pending.incrementAndGet()
            if (requests.trySend(format).isFailure) {
                pending.decrementAndGet()
                error("capture request queue rejected an admitted request")
            }
            return true
        } catch (error: RuntimeException) {
            onRejected(format, error)
            return false
        }
    }

    suspend fun poll(completion: () -> Unit) {
        // A fast native completion must not overtake output registration or UI enqueue.
        mutex.withLock { completion() }
    }
}
