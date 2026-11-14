# vivo S50 probe specification (conditional handoff)

Status: retained for a future decision review. **Decision: A** in
`vivo-s50-60fps-decision.md` means these probes are **not executed** by the
current plan. They are the minimum evidence needed to reopen option B
(ISP/YUV 1080p60).

## Purpose

Determine whether a normal third-party Camera2 session can reproduce any part of
the stock 60 fps/EIS path. The stock camera uses an `AppType=vivo` session,
sensor mode 16, AE `[60,60]`, video stabilization ON, and OIS ON. The public
characteristics advertise only `[30,30]` and no EIS. These probes test whether
vendor keys or the key-40 classification can close that gap.

## Global safety rules

- Debug builds only; never ship probe keys or copied vendor code.
- One variable per run; no other camera client (including the stock camera) while
  a probe holds the device.
- No root and no writes to `/vendor` or `/system`.
- `key40` is system-wide and affects other camera clients. Wrap it in
  `try/finally`; the `finally` block must restore the previous value and close
  the session. The same rule applies to every vendor key whose prior value is
  readable.
- Stop immediately on camera-provider error, repeated open timeout, thermal
  status `>= 2`, or a crash in the vendor provider.
- Record the exact request keys, `CaptureResult` vendor tags, achieved frame
  timestamps, dropped frames, thermal status, and logcat.
- Each run is at most 10 seconds; let the device cool between runs.

## Experiment 1 — `VivoClassProbe` (gate first)

Verify that key 40 (`useVivoCamera`) can be set and restored without breaking
the stock camera.

- Open the hidden `VivoCameraManager` through reflection, read `getInfo(40)`,
  set `setValue(40, 1)`, then open a minimal Camera2 session.
- `finally`: restore the original key-40 value, close the session, and verify the
  stock camera opens normally afterward.
- Pass: key 40 reads back as `1`, the session opens, and the stock camera opens
  after restore.
- Fail: provider error, stock camera fails to open after restore, or the value
  cannot be read.

## Experiment 2 — `Yuv60Probe`

Camera2 `YUV_420_888` 1920x1080 plus a MediaCodec input surface.

- Request: `CONTROL_AE_TARGET_FPS_RANGE=[60,60]`,
  `vivo.control.videoFrameRate=60`, `vivo.control.sensorMode=16`, optional
  `vivo.control.forceSensorMode=16`, and key 40 off/on as the single variable.
  Mode 16 is the mode the stock 1080p60 session used; modes 6 and 9 are the RAW
  branch's modes and may be tested later, not in the same run.
- Read back: `android.control.aeTargetFpsRange`,
  `org.quic.camera2.properties_sensor.SensorCurrentMode`,
  `android.control.videoStabilizationMode`, and the encoder input stream
  dimensions.
- Log: `CaptureResult` timestamps for 10 seconds, encoded frame count, and HAL
  errors.
- Pass: at least 58 fps for 10 seconds with no HAL errors and a valid 1920x1080
  encoder stream.
- Fail: request falls back to 30 fps, no frames, 0-byte output, provider error,
  or thermal status `>= 2`.

## Experiment 3 — `EisProbe`

Only after `Yuv60Probe` passes.

- Request public `CONTROL_VIDEO_STABILIZATION_MODE=1` and
  `LENS_OPTICAL_STABILIZATION_MODE=1`; compare with and without
  `vivo.control.currentModeEx` bit 16384 and the vendor session keys
  `vivo.record.eis`, `vivo.record.eis.mode.enable`,
  `vivo.record.super.eis.enable`, and
  `vcamsdk.repeating.VideoStabilization`.
- Read back the public stabilization modes and the vendor EIS tags.
- Pass: metadata reports stabilization ON and a recorded walking/handheld clip
  shows a measurable reduction in motion versus the EIS-off control.
- Fail: metadata ON but no visual stabilization (the earlier key-only probe
  result), repeated HAL errors, or thermal status `>= 2`.

## Handoff

Under decision A, no probe is needed. The next implementation plan is
`2026-11-14-vivo-s50-raw-60fps-implementation.md`: port the proven RAW 1080p60
branch, add the thermal guard, and keep 4K60/EIS out of scope. If the product
later requires EIS or stock-like ISP output, run `VivoClassProbe` →
`Yuv60Probe` → `EisProbe` in that order; a `Yuv60Probe` pass at `>= 58 fps` plus
an `EisProbe` pass is the gate for a separate ISP/YUV plan.
