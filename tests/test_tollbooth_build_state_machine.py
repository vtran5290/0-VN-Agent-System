"""VERIFY suite for the tollbooth staged-build contract (SHELL_ONLY -> INJECTED -> atomic
publish), added 2026-08-10 per ChatGPT REDIRECT on
00. Command Center/05_AI_Handoffs/2026-08-10-1251_ReviewPack_ReportSuiteOrchestrator.md
(decision: Chatgpt/responses/2026-08-10_ReportSuiteOrchestrator_Decision.md).

Scope: the staged-build mechanism only (rebuild_laban_html_shell.py's staging write +
build_vn_structural_signals.py's publish_shell()). The La Bàn weight engine itself is
already covered by test_laban_engine.py — not duplicated here.

Two-sided non-vacuity (verification-harness.md): every guard exercised here must both
FIRE on a real defect and stay SILENT on a normal build, including the specific defect
class this replaced a flawed design over — a second consecutive normal build starting
from an already-published (INJECTED) final file. That case is what broke the original
"inspect the current final file" guard proposal: a healthy final file is always left
INJECTED, so a guard reading the final file's own state would trip on every ordinary
second run. This suite proves the replacement does not have that failure mode.

stdlib unittest only (no new pip packages), matching test_laban_engine.py convention.
Operates entirely on a temp directory via monkeypatched module path constants — never
touches the live reports/tollbooth_tracker_latest.html.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "reporting"))

import build_vn_structural_signals as bvs  # noqa: E402
import rebuild_laban_html_shell as shell_mod  # noqa: E402

# Minimal seed HTML satisfying rebuild_laban_html_shell.build()'s extraction contract:
# const GATES/FILTERS/INVAL/EVENTS array literals, plus one occurrence of each required
# LABAN_T{1,2,3,4,6} marker pair (content doesn't matter — the shell always resets it).
SEED_HTML = """<!DOCTYPE html>
<html lang="vi">
<head><style>body{}</style></head>
<body>
<div class="page">
<div class="hdr">seed</div>
<div class="panel" id="p0"><!-- LABAN_T1:BEGIN -->old<!-- LABAN_T1:END --></div>
<div class="panel" id="p1"><!-- LABAN_T2:BEGIN -->old<!-- LABAN_T2:END --></div>
<div class="panel" id="p2">
  <!-- VN_STRUCTURAL_SIGNALS:BEGIN -->old signals<!-- VN_STRUCTURAL_SIGNALS:END -->
  <!-- LABAN_T3:BEGIN -->old<!-- LABAN_T3:END -->
</div>
<div class="panel" id="p3"><!-- LABAN_T4:BEGIN -->old<!-- LABAN_T4:END --></div>
<div class="panel" id="p5"><!-- LABAN_T6:BEGIN -->old<!-- LABAN_T6:END --></div>
<!-- LABAN_ENGINE:BEGIN -->old engine<!-- LABAN_ENGINE:END -->
<script>
const EVENTS = [
["seed event","2026-12-31",true],
];
const GATES = [
{id:"g1",ma:"AAA",da:"seed",gate:"1",ly:"x",ti:"y",st:"OK",note:""},
];
const FILTERS = [
["AAA","CORE","1","2","3","4","5","6","7"],
];
const INVAL = [
{id:"i1",o:"AAA",n:"x",f:"y",st:"OK",v:"z",log:""},
];
</script>
</div>
</body>
</html>
"""

FRAGMENT = "<!-- VN_STRUCTURAL_SIGNALS:BEGIN -->fresh signals<!-- VN_STRUCTURAL_SIGNALS:END -->"
LABAN_TABS = {
    "T1": "<p>fresh T1</p>",
    "T2": "<p>fresh T2</p>",
    "T3": "<p>fresh T3</p>",
    "T4": "<p>fresh T4</p>",
    "T6": "<p>fresh T6</p>",
}


class TestStagedBuildContract(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp_dir = Path(self._tmp.name)
        self.final_path = tmp_dir / "tollbooth_tracker_latest.html"
        self.staging_path = tmp_dir / ".build" / "tollbooth_tracker.shell_only.html"
        self.final_path.write_text(SEED_HTML, encoding="utf-8")

        self._patches = [
            mock.patch.object(shell_mod, "PATH", self.final_path),
            mock.patch.object(shell_mod, "STAGING_PATH", self.staging_path),
            mock.patch.object(bvs, "TOLLBOOTH_PATH", self.final_path),
            mock.patch.object(bvs, "STAGING_PATH", self.staging_path),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def _run_shell(self):
        return shell_mod.main()

    def _run_publish(self):
        return bvs.publish_shell(FRAGMENT, LABAN_TABS)

    # ---- SILENT-on-correct cases ------------------------------------------------

    def test_01_shell_rebuild_never_touches_final(self):
        before = self.final_path.read_bytes()
        rc = self._run_shell()
        self.assertEqual(rc, 0)
        after = self.final_path.read_bytes()
        self.assertEqual(before, after, "shell rebuild must never write the final file directly")
        self.assertTrue(self.staging_path.is_file())
        sentinel = re.search(bvs.STATE_SENTINEL_RE, self.staging_path.read_text(encoding="utf-8"))
        self.assertIsNotNone(sentinel)
        self.assertEqual(sentinel.group(1), "SHELL_ONLY")

    def test_02_normal_publish_succeeds_and_cleans_up_staging(self):
        self._run_shell()
        self._run_publish()
        final_html = self.final_path.read_text(encoding="utf-8")
        for tab, body in LABAN_TABS.items():
            self.assertIn(body, final_html, f"tab {tab} content missing from published final")
        self.assertIn("fresh signals", final_html)
        sentinel = bvs.STATE_SENTINEL_RE.search(final_html)
        self.assertEqual(sentinel.group(1), "INJECTED")
        self.assertFalse(self.staging_path.is_file(), "staging file must be consumed after publish")

    def test_03_second_consecutive_normal_build_succeeds_no_force_flag(self):
        """The case that broke the original 'inspect current final' guard design.

        After a successful publish the final file is left INJECTED — a guard that reads
        the final file's own state to decide whether a shell rebuild is safe would treat
        this healthy, ordinary starting point as evidence of danger. This asserts the
        replacement design has no such coupling: round 2 must succeed exactly like round 1.
        """
        self._run_shell()
        self._run_publish()
        self.assertEqual(
            bvs.STATE_SENTINEL_RE.search(self.final_path.read_text(encoding="utf-8")).group(1),
            "INJECTED",
        )
        # Round 2, starting from an INJECTED final — no force flag exists or is needed.
        rc = self._run_shell()
        self.assertEqual(rc, 0)
        self._run_publish()  # must not raise
        final_html = self.final_path.read_text(encoding="utf-8")
        for tab, body in LABAN_TABS.items():
            self.assertIn(body, final_html, f"round 2: tab {tab} content missing")
        self.assertEqual(
            bvs.STATE_SENTINEL_RE.search(final_html).group(1), "INJECTED",
            "round 2 must leave the final file INJECTED, same as round 1",
        )

    # ---- FIRES-on-defect cases ---------------------------------------------------

    def test_04_fires_when_no_staging_file(self):
        before = self.final_path.read_bytes()
        with self.assertRaises(SystemExit):
            self._run_publish()
        self.assertEqual(self.final_path.read_bytes(), before, "final must be untouched on refusal")

    def test_05_fires_when_staging_sentinel_is_not_shell_only(self):
        self._run_shell()
        # Corrupt the sentinel to simulate a stale/already-published staging file.
        bad = self.staging_path.read_text(encoding="utf-8").replace(
            "LABAN_BUILD_STATE:SHELL_ONLY", "LABAN_BUILD_STATE:INJECTED"
        )
        self.staging_path.write_text(bad, encoding="utf-8")
        before = self.final_path.read_bytes()
        with self.assertRaises(SystemExit):
            self._run_publish()
        self.assertEqual(self.final_path.read_bytes(), before, "final must be untouched on refusal")
        self.assertTrue(self.staging_path.is_file(), "refused staging file must not be silently consumed")

    def test_06_fires_when_required_tab_marker_missing(self):
        """Reproduces the exact 2026-08-09 incident: T6 marker pair absent from the
        template output even though the sentinel correctly says SHELL_ONLY."""
        self._run_shell()
        stripped = self.staging_path.read_text(encoding="utf-8")
        stripped = stripped.replace("<!-- LABAN_T6:BEGIN -->", "").replace("<!-- LABAN_T6:END -->", "")
        self.staging_path.write_text(stripped, encoding="utf-8")
        before = self.final_path.read_bytes()
        with self.assertRaises(SystemExit) as ctx:
            self._run_publish()
        self.assertIn("T6", str(ctx.exception))
        self.assertEqual(self.final_path.read_bytes(), before, "final must be untouched on refusal")

    def test_07_atomic_publish_leaves_no_tmp_file_behind(self):
        self._run_shell()
        self._run_publish()
        leftovers = list(self.final_path.parent.glob("*.tmp-*"))
        self.assertEqual(leftovers, [], f"atomic publish left temp file(s): {leftovers}")


if __name__ == "__main__":
    unittest.main()
