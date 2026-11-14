# Rawr research toolkit

This branch is a reference archive for the research and measurement work that
was intentionally kept out of the production branches. It is based on `main`
and is expected to be used as a source of tools, reports and instrumentation,
not merged as a product change.

## What is here

### Capture and device reports

- `docs/device-notes/vivo-s50-pro-mini.md` — vivo S50 Pro mini bring-up,
  camera layout, 50 MP and video findings, 60 fps research, EIS findings and
  known limitations.
- `docs/device-notes/vivo-s50-probe-spec.md` — probe experiment specification.
- `docs/device-notes/vivo-s50-stock-features.md` — stock-camera feature map.
- `docs/device-notes/vivo-s50-60fps-decision.md` — 60 fps/stabilization
  decision record.
- `docs/rexture-latency.md` — Rexture latency report, including the DNG
  fast-path variant.
- `docs/upstream-vs-current.md` — upstream/baseline/optimized comparison.

### Device research tools

- `tools/vivo_stock_research/` — read-only extraction and indexing of vivo
  stock camera APKs, framework APIs, binaries, sensor modes and runtime
  evidence. See its README and tests.
- `tools/vivo_fullres_probe/` — existing full-resolution/60 fps probe app.

### Capture benchmarks and checks

- `tools/phone-performance/app_capture_benchmark.py` — main device capture
  benchmark. The version here includes deterministic app startup, global
  logcat, retries and `--no-restart`.
- `tools/phone-performance/install_benchmark_apk.sh` — unattended benchmark
  install helper.
- `tools/phone-performance/install_benchmark_apk_autotap.sh` — install helper
  that acknowledges the vivo Security Care confirmation screen.
- `tools/phone-performance/compare_versions.py` — aggregate comparison runs.
- `tools/phone-performance/rexture_order_check.py` — verify that Rexture merge
  starts before the DNG journal durability wait.
- `tools/phone-performance/stage_log.py` and `stage_capture_check.py` — parse
  capture stage logs and enforce persistence/acceptance checks.
- `tools/phone-performance/tests/` and the adjacent `test_*.py` files contain
  the corresponding unit tests.

### Debug instrumentation

- `app/src/main/cpp/capture/multiframe/mfsr/RextureTiming.h` plus markers in
  `MfsrCaptureJob.cpp` and `StillCaptureCoordinator.kt` emit `REXTURE_TIMING`
  records. They are logging-only and do not alter the capture pipeline.
- `app/src/main/cpp/develop/demosaic/AmazeStillProcessor.cpp` and the AMaZE
  pipeline contain optional pass timing diagnostics. They are enabled by
  `debug.rawr.amaze_pass_timing=1` and are off by default.

## Commands

Build and unit test the Android side:

```sh
JAVA_HOME=/usr/lib/jvm/java-17-openjdk ./gradlew --no-daemon \
  :app:testDebugUnitTest :app:assembleBenchmark
```

Run the Python checks:

```sh
uv run --no-project --with pytest pytest -q \
  tools/phone-performance/tests \
  tools/phone-performance/test_stage_log.py \
  tools/phone-performance/test_stage_capture_check.py
PYTHONPATH=. uv run --no-project --with pytest pytest -q tools/vivo_stock_research/tests
```

Typical device benchmarks:

```sh
UI_PKG=com.rawr.camera.benchmark scripts/ui app
uv run --no-project tools/phone-performance/app_capture_benchmark.py \
  --variant segmented --warmups 3 --samples 20 --output tmp/bench
```

Rexture order check:

```sh
uv run --no-project tools/phone-performance/rexture_order_check.py \
  --logcat tmp/logcat.txt --max-ms 120
```

## Source branches

- `feat/vivo-s50-pro-mini-bringup` — clean device profile and host tests.
- `feat/jpeg-capture-latency` — production capture optimizations.
- `feat/rexture-dng-fastpath` — Rexture DNG scheduling change.
- `feat/performance-hud` — memory/queue HUD.
- `perf/rexture-latency-report` and `perf/rexture-dng-fastpath-validation` —
  original Rexture measurement branch and report history.
- `perf/upstream-vs-current-comparison` — comparison harness and report.
- `perf-stage2`, `vivo-stock-research`, `vivo-s50-60fps-probe`,
  `vivo-s50-eis-probe` — research source branches.

This branch deliberately does not include production optimization commits,
APKs, raw captures or local `tmp/` artifacts. Do not merge it into `main` as a
product change; cherry-pick individual production changes from their source
branches instead.
