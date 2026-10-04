"""Deterministic pre-review checks never substitute for independent approval."""
import copy
import json
import unittest

from pipeline.pre_review import check_pair
from pipeline.test_editorial import ARTICLE_V2, DOSSIER, GLYPHS


def valid_pair():
    article = copy.deepcopy(ARTICLE_V2)
    dossier = copy.deepcopy(DOSSIER)
    dossier["glyph_research"] = {"historical_glyphs": copy.deepcopy(GLYPHS)}
    return article, dossier


class PreReviewTests(unittest.TestCase):
    def test_valid_pair_reports_hash_bound_structural_pass(self):
        article, dossier = valid_pair()
        report = check_pair(article, dossier)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["checks"]["article_schema"], "pass")
        self.assertEqual(report["checks"]["citation_integrity"], "pass")
        self.assertEqual(report["checks"]["learner_component_coverage"], "pass")
        self.assertEqual(report["checks"]["editorial_contract"], "pass")
        self.assertEqual(report["learner_component_coverage"]["required_indices"], [0])
        json.dumps(report, ensure_ascii=False)

    def test_missing_current_component_card_is_reported_before_review(self):
        article, dossier = valid_pair()
        article["learner"]["components"] = []
        report = check_pair(article, dossier)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["checks"]["learner_component_coverage"], "fail")
        self.assertTrue(any(item["code"] == "learner_component_coverage"
                            and "indices [0]" in item["message"]
                            for item in report["findings"]))

    def test_unknown_citation_id_is_reported_with_article_path(self):
        article, dossier = valid_pair()
        article["summary"]["evidence_ids"] = ["missing-evidence"]
        report = check_pair(article, dossier)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any(item["code"] == "citation_integrity"
                            and item["path"] == "summary"
                            for item in report["findings"]))

    def test_sense_edge_certainty_mismatch_is_blocked_by_editorial_contract(self):
        article, dossier = valid_pair()
        next(edge for edge in article["relationships"]
             if edge["predicate"] == "has_sense")["certainty"] = "disputed"
        report = check_pair(article, dossier)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["checks"]["sense_relationship_consistency"], "fail")
        self.assertTrue(any(item["code"] == "sense_relationship_consistency"
                            for item in report["findings"]))

    def test_checker_does_not_assign_historical_interpretation(self):
        article, dossier = valid_pair()
        article["components"][0]["text"] = "A newly proposed historical analysis."
        report = check_pair(article, dossier)
        self.assertEqual(report["status"], "pass")


if __name__ == "__main__":
    unittest.main()
