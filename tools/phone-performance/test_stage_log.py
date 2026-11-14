#!/usr/bin/env python3
"""Unit tests for the still stage-log parser."""

import unittest

import stage_log


SAMPLE = """\
I/RawrCamNative: AMAZE_STILL_INIT_BEGIN raw=4096x3072
I/RawrCamNative: AMAZE_STILL_INIT_PIPELINE_PASS persistentBytes=61648960
I/RawrCamNative: STILL_RENDER_ENGINE tonemap=rebuilt postDemosaic=rebuilt
I/RawrCamNative: STILL_QUEUE_JOB_STARTED waitMs=144.4
I/RawrCamNative: AMAZE_STILL_PROCESS_PASS totalMs=1683.33
I/RawrCamNative: STILL_READBACK_MEMORY type=3 coherent=0 bytes=50331648
I/RawrCamNative: CAPTURE_SHARPENING iterations=2 wallMs=113.5
I/RawrCamNative: JPEG_UHDR_ENCODE baseMs=43 mapPathMs=259 wallMs=281
I/RawrCamNative: JPEG_UHDR_FIT fit=1 max=1.45 base=0.75/0.40 fitMs=203.9 mapPx=4096x3072 color=1
I/RawrCamNative: JPEG_STRIPS strips=8
I/RawrCamNative: JPEG_CAPTURE_WRITE_PASS encodeMs=309 fsyncMs=6 fileBytes=9600000
I/RawrCamNative: AMAZE_STILL_PROCESS_PASS totalMs=600.0
I/RawrCamNative: STILL_READBACK_MEMORY type=3 coherent=0 bytes=50331648
I/RawrCamNative: CAPTURE_SHARPENING iterations=2 wallMs=120.0
I/RawrCamNative: JPEG_CAPTURE_WRITE_PASS encodeMs=320 fsyncMs=7 fileBytes=9700000
I/RawrCamNative: AMAZE_STILL_PROCESS_PASS totalMs=590.0
I/RawrCamNative: STILL_READBACK_MEMORY type=3 coherent=0 bytes=50331648
I/RawrCamNative: CAPTURE_SHARPENING iterations=2 wallMs=118.0
I/RawrCamNative: JPEG_CAPTURE_WRITE_PASS encodeMs=315 fsyncMs=5 fileBytes=9650000
I/RawrCamNative: 11-12 10:00:00.000  1234  1234 I RawrCam : no stage tag here
"""


class StageLogTest(unittest.TestCase):
    def test_parse_ignores_noise(self):
        records = stage_log.parse_text(SAMPLE)
        self.assertEqual(len(records), 19)
        self.assertEqual(records[0].tag, "AMAZE_STILL_INIT_BEGIN")
        self.assertEqual(records[0].values["raw"], "4096x3072")

    def test_summary_counts(self):
        summary = stage_log.summarize(stage_log.parse_text(SAMPLE))
        self.assertEqual(summary["shots"], 3)
        self.assertEqual(summary["pipeline_builds"], 1)
        self.assertEqual(summary["pipeline_builds_after_first"], 0)
        self.assertEqual(summary["render_rebuilds"], 1)
        self.assertEqual(summary["render_rebuilds_after_first"], 0)
        self.assertEqual(summary["readback_events"], 3)
        self.assertEqual(summary["readback_bytes"], ["50331648"])
        self.assertEqual(summary["demosaic_median_ms"], 600.0)
        self.assertEqual(summary["demosaic_p95_ms"], 1683.33)
        self.assertEqual(summary["sharpening_median_ms"], 118.0)
        self.assertEqual(summary["jpeg_encode_median_ms"], 315.0)
        self.assertEqual(summary["jpeg_wall_median_ms"], 281.0)
        self.assertEqual(summary["jpeg_fit_map_px"], ["4096x3072"])
        self.assertEqual(summary["jpeg_strips"], ["8"])

    def test_rebuilds_after_first(self):
        records = stage_log.parse_text(SAMPLE)
        records.append(stage_log.parse_line("AMAZE_STILL_INIT_PIPELINE_PASS persistentBytes=1"))
        records.append(stage_log.parse_line("STILL_RENDER_ENGINE tonemap=rebuild postDemosaic=rebuilt"))
        summary = stage_log.summarize(records)
        self.assertEqual(summary["pipeline_builds_after_first"], 1)
        self.assertEqual(summary["render_rebuilds_after_first"], 1)

    def test_number_parsing(self):
        record = stage_log.parse_line("RCD_STILL_PROCESS_PASS totalMs=579.35 requestId=2")
        self.assertIsNotNone(record)
        self.assertEqual(record.tag, "RCD_STILL_PROCESS_PASS")
        self.assertEqual(record.number("totalMs"), 579.35)
        self.assertEqual(record.number("missing"), None)

    def test_rcdvng_vng4_pipeline(self):
        records = stage_log.parse_text(
            "RCDVNG_STILL_INIT_BEGIN algorithm=VNG4 raw=4096x3072\n"
            "RCDVNG_STILL_INIT_PIPELINE_PASS algorithm=VNG4 persistentBytes=252641536\n"
            "RCDVNG_STILL_PROCESS_PASS demosaic=VNG4 totalMs=80.5\n"
            "RCDVNG_STILL_PROCESS_PASS demosaic=VNG4 totalMs=90.3\n"
        )
        summary = stage_log.summarize(records)
        self.assertEqual(summary["shots"], 2)
        self.assertEqual(summary["pipeline_builds"], 1)
        self.assertEqual(summary["demosaic_median_ms"], 85.4)


if __name__ == "__main__":
    unittest.main()
