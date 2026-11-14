package com.rawr.camera.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.rawr.camera.model.CaptureUiState
import com.rawr.camera.model.formatPerformanceHud

/** Opt-in viewfinder telemetry; hidden state is never composed. */
@Composable
internal fun PerformanceHud(state: CaptureUiState) {
    if (!state.showPerformanceHud) return
    val queued = maxOf(state.pressQueueDepth, state.pendingCaptures.count { !it.terminal })
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(CaptureDimens.PerformanceHudHeight)
            .background(Color.Black.copy(alpha = 0.32f))
            .testTag("capture_performance_hud"),
        contentAlignment = Alignment.CenterStart
    ) {
        Text(
            text = formatPerformanceHud(state.performanceHud, queued),
            color = Color.White.copy(alpha = 0.82f),
            fontFamily = FontFamily.Monospace,
            fontSize = 10.sp,
            maxLines = 1,
            modifier = Modifier.padding(horizontal = 10.dp)
        )
    }
}
