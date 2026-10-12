"""Static checks of the dashboard source and built assets; behaviour is tested by `npm test` (vitest) in frontend/."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = "".join((ROOT / "frontend/src" / name).read_text(encoding="utf-8") for name in ("App.jsx", "ResultInsights.jsx", "SourceHealth.jsx"))


class FrontendContractTests(unittest.TestCase):
    def test_feature_hash_score_is_not_presented_as_semantic_meaning(self) -> None:
        self.assertNotIn("Meaning-level", APP)
        self.assertNotIn('"Semantic drift"', APP)
        self.assertIn("Vector drift (feature-hash)", APP)

    def test_every_answer_discloses_how_it_was_generated(self) -> None:
        self.assertIn('className="generation-method"', APP)
        self.assertIn("not a language-model conclusion", APP)

    def test_unaligned_excerpts_are_not_labelled_as_versions(self) -> None:
        self.assertNotIn('label="Pre-amendment baseline"', APP)
        self.assertIn("Amendment instruction (source excerpt)", APP)
        self.assertIn("source_fidelity_warnings", APP)

    def test_comparison_view_is_safe_honest_and_not_colour_only(self) -> None:
        panel = (ROOT / "frontend/src/ComparisonPanel.jsx").read_text(encoding="utf-8")
        sources = APP + panel + (ROOT / "frontend/src/CaseReviewPanel.jsx").read_text(encoding="utf-8")
        self.assertNotIn("dangerouslySetInnerHTML", sources)
        self.assertIn("<del", panel)
        self.assertIn("<ins", panel)
        self.assertIn("struck through", panel)  # text legend, not colour alone
        self.assertIn("Page-region highlight unavailable", panel)
        self.assertIn("Excerpts only", panel)

    def test_unavailable_scores_are_never_shown_as_zero_or_recomputed_in_the_browser(self) -> None:
        self.assertIn('return value == null ? "Unavailable"', APP)
        self.assertNotIn("legacyCalculationTrace", APP)
        self.assertIn("evidence_alignment_quality_percent", APP)
        self.assertIn("Scheduled ingestion (stored in UTC):", APP)

    def test_built_index_references_existing_assets(self) -> None:
        index = (ROOT / "web/index.html").read_text(encoding="utf-8")
        assets = re.findall(r'(?:src|href)="/?(assets/[^"]+)"', index)
        self.assertTrue(assets)
        for asset in assets:
            self.assertTrue((ROOT / "web" / asset).is_file(), asset)
        bundle = "".join((ROOT / "web" / asset).read_text(encoding="utf-8") for asset in assets if asset.endswith(".js"))
        self.assertIn("Vector drift (feature-hash)", bundle)  # the committed build matches the source


if __name__ == "__main__":
    unittest.main()
