# vivo S50 60 fps / stabilization decision

Status: accepted for the research phase, 2026-11-14.

## Context

The stock camera records 1080p60 with sensor mode 16, AE target range
`[60,60]`, video stabilization ON, and OIS ON. The public Camera2
characteristics on the same device advertise only `[30,30]` AE ranges and no EIS
mode. The stock session is a vendor `AppType=vivo` session; the sensor-mode
selector has separate `vivo`, `!vivo`, and `ENGINEER` branches
(`tmp/vivo-stock/PD2527_A_16.0.19.12.W10/vendor/etc/camera/sensormode-selector/PD2527.json`).

The proven Rawr path is the `vivo-s50-60fps-probe` branch (7505a14): 1080p only,
1x/3x, sensor modes 6/9, fused 2x demosaic, B-frames 0, and roughly 45 seconds
before the HEVC encoder throttles. It does not use the stock ISP, does not
provide EIS, and cannot do 4K60/Open Gate 60.

## Options

- **A — port the proven RAW 60 branch.** Keep the RAW look, use 1080p at 1x/3x,
  add the thermal guard and short-clip UX. Accept no EIS and no 4K60.
- **B — build a separate ISP/YUV 1080p60 path.** Requires evidence that a
  third-party YUV session can get `[60,60]`, the correct sensor mode, and the
  vendor EIS combination. Would add a second recorder, 8-bit 4:2:0 output, and
  unproven stabilization.
- **C — no-go for 60/EIS now.** Keep 24/30 and document what would change the
  decision.

## Decision: A

Port the proven RAW 60 branch, with a thermal guard and explicit short-clip
limits. Reasons:

1. RAW 60 is the only path with measured, reproducible evidence on this device:
   59.94 fps, zero drops in a 15 s clip, and a known thermal knee at about 45 s.
2. The stock 60 path depends on a vendor `AppType=vivo` session and private
   sensor-mode/EIS state. The public API advertises `[30,30]`; no third-party
   YUV 60 experiment has hit the acceptance bar.
3. The stock runtime evidence is strong, but it does not prove that a YUV
   session can reproduce it. Decision rule B was `>=58 fps for 10 s with no HAL
   errors and EIS metadata ON`; that probe has not run, so B is not justified.
4. 4K60/Open Gate 60 and stock EIS remain out of scope. The RAW GPU pipeline is
   already above the 16.7 ms budget at 4K, and the stock EIS keys previously
   failed to stabilize a third-party session.

## Consequences

- Ship 1080p60 for 1x and 3x only; UW stays at 30 fps.
- Add a thermal guard: stop or downgrade before the encoder latency knee, and
  show the short-clip limitation in the UI.
- Keep B-frames disabled at 60 fps; the encoder otherwise caps near 44 fps.
- Do not claim 4K60, Open Gate 60, EIS, stock HDR/LOG, or 8K.
- Preserve 24/30 and 4K30 behavior; run the existing video matrix as a
  regression gate.

## What would reopen the decision

- A `Yuv60Probe` reaching at least 58 fps for 10 s with no HAL errors, plus
  `EisProbe` showing real stabilization and no thermal regression, would move
  the decision to B for a separate ISP/YUV implementation.
- Evidence that key 40 or the `!vivo` selector branch reliably unlocks 1080p60
  in a normal third-party YUV session would lower the cost of B.
- A product requirement for 4K60 or EIS would make A insufficient; that requires
  a separate hardware-ISP plan, not a port of the RAW branch.

The probe specification in `vivo-s50-probe-spec.md` is retained for that future
reopening; under decision A it is a handoff note, not an execution step for this
plan.
