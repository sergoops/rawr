# Upstream vs optimized Rawr: capture latency

## Versions

| Label | Ref | Description | Benchmark APK SHA-256 |
|---|---|---|---|
| U | `5a51774` | strict upstream `origin/main` | `e448d653618ec4d0ede48822bcf87f762d905d34b770e243e266b0dd904f6c41` |
| B | `579face` | upstream + six vivo S50 Pro mini bring-up commits (no performance work) | `f885ee146586f06a9322a8c3585c7af94feff86bd406a5a3e17a0c68b6b728ca` |
| C | `828f2ea` | `perf/rexture-dng-fastpath` = `aea6422` (all existing optimizations) + Rexture DNG fast-path | `e6f1749fcfbb1f6f96aec5e5c54171e76afdeb6b55958c3da1f084528ea3acba` |

`828f2ea` contains only one production change relative to `aea6422`: `app/src/main/cpp/capture/multiframe/mfsr/MfsrCaptureJob.cpp` (+21/−6), moving the base-DNG journal wait/writer start after the merge begins. The final branch `perf/jpeg-capture-latency-main` is unchanged at `aea6422`.

## Method

- One weak-light scene; camera on the same desk position; 1x lens, RAW 4096×3072.
- Rexture on, 6 frames, Rexture Native RGB off, Chroma Denoise off.
- JPEG quality 98, 4:2:0, UltraHDR on.
- Two output modes: JPEG-only and JPEG+DNG.
- Segmented JPEG path; 2 warmups + 10 measured samples per block.
- Latency is click→JPEG publication, measured from the app's monotonic `requestedNs`/`publishedNs` pair. DNG completion is diagnostic only; the JPEG publish is the primary user-visible event.
- Two rounds were attempted in order U1, B1, C1, C2, B2, U2 with cell order reversed in round 2.

### Exposure / thermal limitation

The first round's first blocks were captured at ISO 146–150, 1/24; later blocks were at ISO 609–694, 1/15. This is a real scene/illumination change (the screen/room light state changed), not an app setting. Those bright-scene blocks are **excluded**; the table below uses the dark-scene blocks only. As a result U has 10 measured samples per cell, while B and C have 20 in most cells. C was measured in both rounds; U's usable block was the last run, so thermal bias is if anything against U.

Battery temperature was ~34–36 °C during the dark-scene blocks; skin temperature was not exposed by `thermalservice`. This is a one-scene comparison, not a thermal-controlled ABBA experiment.

## Results

| Mode | Version | n | Median ms | p95 ms | Min ms | Max ms | vs U | vs B |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Single-frame JPEG-only | U | 10 | 1627.001 | 1676.126 | 1615.121 | 1676.126 | +0.0% | −2.3% |
| Single-frame JPEG-only | B | 10 | 1665.819 | 1712.058 | 1635.708 | 1712.058 | +2.4% | +0.0% |
| Single-frame JPEG-only | C | 20 | 1500.875 | 1584.302 | 1417.330 | 1618.048 | **−7.8%** | **−9.9%** |
| Single-frame JPEG+DNG | U | 10 | 1532.797 | 1585.201 | 1474.664 | 1585.201 | +0.0% | −1.8% |
| Single-frame JPEG+DNG | B | 20 | 1560.749 | 1640.325 | 1492.674 | 1662.566 | +1.8% | +0.0% |
| Single-frame JPEG+DNG | C | 20 | 1450.007 | 1523.360 | 1379.642 | 1531.219 | **−5.4%** | **−7.1%** |
| Rexture JPEG-only | U | 10 | 2469.542 | 2502.055 | 2442.664 | 2502.055 | +0.0% | −0.3% |
| Rexture JPEG-only | B | 20 | 2477.489 | 2522.839 | 2413.533 | 2524.162 | +0.3% | +0.0% |
| Rexture JPEG-only | C | 20 | 2393.277 | 2426.964 | 2321.626 | 2438.658 | **−3.1%** | **−3.4%** |
| Rexture JPEG+DNG | U | 10 | 2822.154 | 2871.357 | 2460.706 | 2871.357 | +0.0% | +0.0% |
| Rexture JPEG+DNG | B | 20 | 2821.084 | 2917.994 | 2766.025 | 2990.080 | −0.0% | +0.0% |
| Rexture JPEG+DNG | C | 20 | 2419.730 | 2464.737 | 2384.538 | 2475.654 | **−14.3%** | **−14.2%** |

## Interpretation

- **Rexture JPEG+DNG is the main result.** C is ~2.82 s → ~2.42 s versus both U and B, a ~14% reduction (~400 ms). The Rexture fast-path moves the pre-merge base-DNG journal wait out of the critical path: accepted→merge_start drops from ~370 ms to ~52 ms, and `BURST_SAVE` runs alongside the merge. The final DNG writers remain largely hidden behind JPEG.
- **Rexture JPEG-only gains less** (~3%) because there is no pre-merge DNG journal to overlap. C is still the fastest, but the gain is in the noise/thermal band.
- **Single-frame gains** are ~5–10% in this dark-scene sample. Earlier, cleaner UW ABBA data measured ~6% median; treat the single-frame numbers here as directionally consistent, not precise, because U has only 10 samples and the thermal/lighting state was not perfectly matched.
- B (upstream + vivo bring-up) is not faster than strict U in these cells; it is a hardware-enablement baseline, not a performance baseline.
- DNG+JPEG being as fast as JPEG-only in single-frame is expected: the DNG writers overlap the JPEG render/encode; the Rexture pre-merge journal was the serialized cost that variant 1 removes.

## Quality / scope

- Variant 1 changes scheduling only: no algorithm, demosaic, tone, sharpening, JPEG, UltraHDR, frame-count, or default-setting changes.
- Existing fixed-input UltraHDR validation reports 0 differing map bytes on four reference images; Rexture output DNG/JPEG smoke checks produced valid 4096×3072 CFA TIFFs and JPEGs.
- No cross-version pixel-identity test is meaningful for live captures because sensor noise changes every frame; the JPEG SHA is not stable even between identical captures.
- This work did not optimize Rexture JPEG-only beyond the existing pipeline and does not address the 1x Rexture soak thermal/memory limits documented in `docs/rexture-latency.md`.

## Artifacts

Raw block outputs are under `tmp/compare/U1`, `U2`, `B1`, `B2`, `C1`, `C2`; the dark-scene aggregate is `tmp/compare/aggregate-dark.json` and `tmp/compare/table-dark.md`.

## Reproduction

1. Install the U, B, or C APK on the benchmark package.
2. Configure 1x, Rexture 6 frames, Native RGB off, Chroma Denoise off, JPEG 98/UltraHDR.
3. Run `tools/phone-performance/app_capture_benchmark.py --variant segmented --warmups 2 --samples 10`.
4. For C, the Rexture DNG fast-path is present; for U/B it is not.
5. Keep screen brightness and room lighting fixed across versions; the first U/B round here was invalidated by an exposure change.
