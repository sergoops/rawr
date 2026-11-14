# vivo S50 Pro mini (V2527A)

Bring-up notes from 2026-11-11, Android 16, build `PD2527_A_16.0.19.12.W10`.

## Device

| Property | Value |
| --- | --- |
| `ro.product.model` | `V2527A` |
| `ro.vivo.product.model` | `PD2527` |
| `ro.vivo.market.name` | `vivo S50 Pro mini` |
| `ro.vivo.product.release.name` | `PD2527` |
| `ro.product.device` / `ro.product.name` | `PD2527` |
| `ro.board.platform` | `canoe` |
| `ro.soc.model` | `SM8845` (Snapdragon 8 Gen 5) |
| Android | 16 |

## Cameras

Probed with `tools/vivo_fullres_probe` (`mode dump`). Five camera ids exist.

| Camera | Role | Facing | Focal length | RAW16 / RAW10 | Black | White | AF | Profile lens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | main | back | 5.608 mm f/1.57 | 4096x3072, 4096x2304 | 64 | 1023 | yes | `1x` |
| 1 | front | front | 3.09 mm f/2.0 | 4080x3072, 4080x2296 | 64 | 1023 | yes | not offered |
| 2 | logical main | back | 5.608 mm f/1.57 | 4096x3072, 4096x2304 | 64 | 1023 | yes | not used |
| 3 | ultrawide | back | 1.6 mm f/2.2 | 3200x2400 | 64 | 1023 | no | `UW` |
| 4 | telephoto | back | 13.85 mm f/2.65 | 4096x3072 | 64 | 1023 | yes | `3x` |

- Camera 2 repeats camera 0's characteristics and advertises
  `ULTRA_HIGH_RESOLUTION_SENSOR`; opening it without a vivo lease fails with
  `device error 4`, so the profile uses camera 0 for `1x`.
- The binned sizes are 4096x3072 for main/tele and 3200x2400 for ultrawide.
  `SensorModeTable` lists 8192x6144 modes on 0/2 and 4, but the public
  `streamConfigurationMap` does not advertise them; see "50 MP stills" below.
- All rear sensors report dynamic black level 64 and white level 1023 in
  captures, matching the probe dump.

## Built-in profile

`app/src/main/cpp/camera/profiles/vivo_s50_pro_mini.json`:

- id `vivo_s50_pro_mini`, version 1
- matches `ro.product.model` `V2527A` (verified), otherwise
  `ro.vivo.product.model` prefix `PD2527`
- three lenses: `UW` (camera 3), `1x` (camera 0), `3x` (camera 4)
- RAW16 at the largest advertised binned size
- dynamic levels (`static: false`), no vendor keys, no gates, no companion
- the verified model disables the automatic companion stream

## 50 MP stills

The sensor advertises 8192x6144 modes, but the public Camera2 stream map caps
RAW at 4096x3072. The stock camera's "High Resolution" (remosaic) mode produces
an 8192x6144 JPEG, not a RAW/DNG: its Camera3 session contains a 1440x1080 YUV
preview and an 8192x6144 JPEG/HEIC stream, with no full-size RAW output.

The vendor full-size RAW path (`streams.photo` 8192x6144 + `vivoFullSize`
gate, X300-style keys) was tested with prototype `H1x`/`H3x` lenses:

- the still succeeds only when `com.vivo.current_ui_module=74` is applied to
  the decision/still request, not to the session or preview;
- the returned 8192x6144 RAW buffer contains a 4096x3072 image in the top-left
  quadrant and zeros elsewhere (`FULL_SIZE_BINNED_CORNER ... seamlessMode=1`);
- a full-RAW-only session and a full-RAW viewfinder are unsupported
  (`device error 4` / `EX_SERVICE_SPECIFIC`, in-flight buffer failure).

Conclusion: this device does not expose 50 MP RAW; 4096x3072 is the maximum
RAW/DNG size. 50 MP is available only as the stock camera's JPEG remosaic
output. Supporting it in Rawr would require a JPEG/HEIC still path, not a
camera profile.

## Verification

The debug app logs:

```text
CAMERA_PROFILE_BUILTIN profile=vivo_s50_pro_mini model=V2527A rule=model verified=true
CAMERA_PROFILE_APPLIED profile=vivo_s50_pro_mini lenses=3
CAMERA_NDK_SELECTION ... lensId=UW cameraId=3 ... raw=3200x2400 rawFormat=RAW16 ... companion=0
CAMERA_NDK_SELECTION ... lensId=1x cameraId=0 ... raw=4096x3072 rawFormat=RAW16 ... companion=0
CAMERA_NDK_SELECTION ... lensId=3x cameraId=4 ... raw=4096x3072 rawFormat=RAW16 ... companion=0
```

DNG + JPEG captures succeeded on all three lenses, with the expected
dimensions:

| Lens | DNG | JPEG |
| --- | --- | --- |
| UW | 3200x2400 | 3200x2400 |
| 1x | 4096x3072 | 4096x3072 |
| 3x | 4096x3072 | 4096x3072 |

Tests:

- `camera_profile_test` and `builtin_route_golden_test` pass.
- `./gradlew :app:testDebugUnitTest :app:testReleaseUnitTest` passes.
- Full host `ctest` is 66/70. The four failures (`rawr_auto_exposure_test`,
  `camera_focus_controls_test`, `capture_job_test`, `raw_remosaic_vulkan_test`)
  are unrelated to this profile: libstdc++ 16 assertion behavior and a host
  Vulkan `VK_ERROR_DEVICE_LOST`.

## Video

Recorded through the debug app with HEVC and AAC 48 kHz stereo. All expected
lens/resolution combinations produced playable files:

| Lens | 1080p | 4K | Open Gate |
| --- | --- | --- | --- |
| 1x | 24/30 fps | 24/30 fps | 24/30 fps, 4096x3072 |
| 3x | 30 fps | 30 fps | 30 fps, 4096x3072 |
| UW | 30 fps | not supported | 30 fps, 3200x2400 |

- A 4K30 recording reported `DROP 0` after four seconds.
- While recording, resolution/FPS selectors, lens buttons, and the Photo/Video
  switch are disabled, so mode and lens changes cannot happen mid-clip.
- UW cannot record 4K: its RAW stream is 3200x2400, below the 3840x2160 that
  `VideoResolutionMode.resolve` requires. Selecting 4K is allowed in the top
  bar, but tapping record produces no file, no crash, and a toast; the preview
  remains alive. There is no persistent error message.

## 60 fps video

The sensor exposes 60 fps only through private sensor modes, not through the
public AE ranges (`android.control.aeAvailableTargetFpsRanges` stops at
`[30,30]`). A standalone probe (`tools/vivo_fullres_probe` `FpsActivity`)
forced the mode with `vivo.control.forceSensorMode` and measured real 60 fps
RAW output:

| Lens | Sensor mode | RAW | Measured |
| --- | --- | --- | --- |
| 1x (camera 0) | 6 or 17 | 4096x3072 | 59.4–59.5 fps |
| 1x (camera 0) | 16 | 4096x2304 | 59.4 fps |
| 3x (camera 4) | 9 | 4096x3072 | 59.2 fps |
| UW (camera 3) | — | 3200x2400 | 29.9 fps (no 60 mode) |

The research prototype added `session.videoSensorModes` (`{"60": 6}` for `1x`,
`{"60": 9}` for `3x`), native `fpsChoices`, and recorder-side injection of
`vivo.control.forceSensorMode` only while recording. That prototype is **not**
part of the current main profile (version 1); the numbers below are from the
research branch. The viewfinder kept its normal mode.

The first app implementation still averaged ~30 fps because the 1080p path
demosaiced the full 3840x2160 crop (`demosaic` ≈16.5 ms, total ≈21 ms). Two
changes make 1080p60 viable for short clips:

- At 60 fps the recorder selects the fused 2x2 area downscale
  (`tiled_mhc_fused_2x_area`), which halves demosaic cost. The normal
  anti-alias filter remains the default for 24/30 fps.
- At 60 fps the recorder forces encoder B-frames to 0. With B-frames on Auto
  the encoder capped the recording near 44 fps even after the GPU was fast
  enough; with 0 the same scene reaches 60 fps.

Measured with the debug app (HEVC, AAC 48 kHz stereo):

| Test | Output | Average | Drops | GPU total |
| --- | --- | --- | --- | --- |
| 1x 1080p60 | 1920x1080 | 59.94 fps | 0 | 11.64 ms |
| 3x 1080p60 | 1920x1080 | 59.89 fps | 0 | ~12 ms |
| 1x 1080p30 | 1920x1080 | ~29.5 fps | 0 | — |
| 1x 4K30 | 3840x2160 | ~29.9 fps | 0 | — |
| 1x 1080p60, 60 s, cool start | 1920x1080 | 55.25 fps | 209 | 11.6–12.1 ms |

A 60 s recording that starts cool holds 60 fps with zero drops for roughly
45 s. The HEVC encoder then throttles: its latency jumps from ~67 ms to
~400 ms as the skin temperature crosses the 42 °C thermal threshold
(status 1 → 2). The full 60 s averaged 55.25 fps with 209 `encoderBusy`
drops, while GPU stages stayed flat at 11.6–12.1 ms. The limit is encoder
thermals, not the demosaic path, so 60 fps is best treated as a short-clip
mode. 1080p30 and 4K30 are unaffected.

60 fps is offered only for 1080p. At 4K and Open Gate the GPU pipeline is
still above the 16.7 ms frame budget, so those modes stay at 24/30 fps and
the FPS selector does not offer 60 there. The 60 fps path uses the area
downscale filter, so it is slightly softer than the default anti-aliased
1080p output; a detailed-scene A/B remains to be checked.

## Electronic stabilization

Standard Camera2 video stabilization is not available to third-party apps:
`android.control.availableVideoStabilizationModes` is `[0]` (OFF) on all
back cameras. OIS is available (`android.lens.info.availableOpticalStabilization`
is `[0, 1]` on cameras 0 and 4) and the stock camera's OIS behaviour is already
present in Rawr.

The stock app's stronger electronic stabilization is a private Qualcomm/vivo
path. Its APK references `org.codeaurora.qcamera3.sessionParameters.EISMode`,
`vcamsdk.session.parameter.video_super_eis`, `vcamsdk.repeating.VideoStabilization`,
`vivo.control.eis.config.enable`, `vivo.control.EISsolution`, and a native
`SessionParam.eis` / `SessionParam.qcomEis` path. Injecting the Camera2-visible
subset through a debug profile was accepted by the HAL:

```text
org.codeaurora.qcamera3.sessionParameters.EISMode = 1 or 2   (session)
vivo.control.eis.config.enable          = 14   (request)
vivo.control.EISsolution                = 2    (request)
vivo.control.currentModeEx              = 16384 (request, int64)
vivo.control.superEis                   = 1    (request)
```

The keys were carried in the repeating request and the session configured, but
they did not stabilize the preview or the recorded video. The apparent
`BST x1.26` crop on logical camera 2 is digital zoom, not stabilization. Logical
camera 2 can be opened with `camera.id=2` and `camera.physical=0` under the
`vivoFullSize` gate; opening it without the physical id crashed the vendor
camera provider in `ChiMcxResultManager::ProcessResult`.

Observed exposure difference: with the same scene, the physical 1x camera 0
video is noticeably darker than the logical camera 2 (`L1x`) video. The cause
has not been investigated.

Conclusion: there is no profile-level switch that turns on the stock EIS.
True electronic stabilization would require a separate software stabilization
stage; it is not a vendor-key change.

## Archive

Raw probe dumps, test captures, and JPEG samples are kept outside the
checkout at:

```text
/home/sergoops/dev/rawr-archive/vivo-s50-pro-mini/
  probe/chars_0.txt ... chars_4.txt
  captures/cam{0,2,3,4}/
  shots/
  fullres/                 prototype profiles, probe logs, 50 MP samples
  final-base/              final base checks, DNG/JPEG, lint reports
  video/                   video matrix, MP4 samples, ffprobe CSV
```

The directory is not versioned; this note is the durable summary.

## Not done yet

- DCP colour profiles for this sensor stack.
- Lens distortion calibration.
- Ultrawide focus: camera 3 reports no AF regions.
