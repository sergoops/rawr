# vivo stock camera research

Read-only tooling for the Vivo S50 Pro mini (`V2527A`,
`PD2527_A_16.0.19.12.W10`). The goal is evidence, not device modification.

## Safety

- adb runs as UID 2000 (shell), never root.
- Only pull from `/vendor`, `/system`, `/system_ext`, `/product`, `/odm`,
  `/apex`, `/data/anr`, and `/data/tombstones`.
- Never pull `/data/data`, `/data/vendor`, `/data/misc`, or `/data/system`.
- Never run `pm clear`, `am force-stop`, `settings put`, or any write command.
- Keep outputs in `./tmp/vivo-stock/<build>/`; they are ignored and may
  contain device-specific or personal data. Do not commit them.

## Tests

The repository has no Python project, so tests run in an ephemeral uv
environment with the repository root on `PYTHONPATH`:

```sh
PYTHONPATH=. uv run --no-project --with pytest pytest \
  tools/vivo_stock_research/tests -q
```

## Output layout

```text
tmp/vivo-stock/<build>/
  manifest.json          # every target, status, hash, ls -lZ metadata
  vendor/...             # pulled vendor files
  system/...             # pulled system files
  apk-assets.json        # stock APK asset inventory
  sensor-modes.json      # parsed >=60 fps modes and AppType gates
  permissions.json       # parsed permission XML
  binary-index.json      # strings/nm/readelf evidence
  framework-index.json   # jadx/jar/vdex hidden-API evidence
  runtime/               # dumpsys, watch, logcat, timeline
```

## Commands

```sh
# dry run: no device writes
PYTHONPATH=. uv run --no-project python -m tools.vivo_stock_research.extract \
  --build PD2527_A_16.0.19.12.W10 \
  --out tmp/vivo-stock/PD2527_A_16.0.19.12.W10 \
  --dry-run
```

Do not connect to the phone until the operator releases it.
