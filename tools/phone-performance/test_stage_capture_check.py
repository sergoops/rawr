#!/usr/bin/env python3
"""Unit tests for the device acceptance check (no phone needed)."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import stage_capture_check


def _log(pipeline_builds: int, render_rebuilds: int, shots: int = 3) -> str:
    lines = [
        "AMAZE_STILL_INIT_BEGIN raw=4096x3072",
        "AMAZE_STILL_INIT_PIPELINE_PASS persistentBytes=61648960",
    ]
    for i in range(pipeline_builds):
        if i:
            lines.append("AMAZE_STILL_INIT_PIPELINE_PASS persistentBytes=61648960")
    for i in range(render_rebuilds):
        lines.append("STILL_RENDER_ENGINE tonemap=rebuilt postDemosaic=rebuilt")
    for i in range(shots):
        lines.append(f"AMAZE_STILL_PROCESS_PASS totalMs={600.0 + i}")
        lines.append("CAPTURE_SHARPENING iterations=2 wallMs=120")
        lines.append("STILL_READBACK_MEMORY type=3 coherent=0 bytes=50331648")
        lines.append("JPEG_CAPTURE_WRITE_PASS encodeMs=320 fsyncMs=7 fileBytes=9700000")
    return "\n".join(lines) + "\n"


class AcceptanceCheckTest(unittest.TestCase):
    def run_check(self, text: str, min_shots: int = 3) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "validation.txt"
            path.write_text(text)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = stage_capture_check.main(["--validation", str(path), "--min-shots", str(min_shots)])
        return code, out.getvalue()

    def test_reused_engines_pass(self):
        code, out = self.run_check(_log(pipeline_builds=1, render_rebuilds=1))
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)

    def test_rebuild_after_first_fails(self):
        code, out = self.run_check(_log(pipeline_builds=3, render_rebuilds=3))
        self.assertEqual(code, 1, out)
        self.assertIn("demosaic pipeline built 3 times", out)
        self.assertIn("render engine rebuilt 3 times", out)

    def test_too_few_shots_fails(self):
        code, out = self.run_check(_log(pipeline_builds=1, render_rebuilds=1, shots=1), min_shots=3)
        self.assertEqual(code, 1, out)
        self.assertIn("only 1 demosaic shots", out)


if __name__ == "__main__":
    unittest.main()
