import copy
import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

from pipeline import editorial
from pipeline.review_loop import status_conflicts, consolidated_findings, repeated_fields
from pipeline.test_editorial import ARTICLE_V2, DOSSIER, GLYPHS


class ReviewLoopTests(unittest.TestCase):
    def test_current_form_gap_does_not_rebuild_historical_images(self):
        feedback = {'reuse_existing_glyph_candidates': True}
        self.assertTrue(editorial.reuse_glyphs_for_text_followup(feedback, [{'findings': [
            'The attached images are historical redrawings and cannot establish current layout; add current-form evidence.']}]))
        self.assertFalse(editorial.reuse_glyphs_for_text_followup(feedback, [{'findings': [
            'The glyph caption overstates its provenance.']}]))
        self.assertFalse(editorial.reuse_glyphs_for_text_followup(feedback, [{'findings': [
            'Verify the image identity against its actual source.']}]))

    def test_historical_redraw_attachment_preserves_script_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root/'historical.png'; image.write_bytes(b'fixture-image-bytes')
            script = root/'review.py'
            script.write_text("import sys\nfrom pathlib import Path\nsys.stdin.read()\n"
                              "Path(sys.argv[1]).write_text('{\"verdict\":\"pass\",\"findings\":[]}')\n")
            runner = editorial.Runner([sys.executable, str(script), '{output}'], 'gpt-6-luna', 10, 'low')
            dossier = {'glyph_assets': [{'glyph_id':'early', 'source_url':'https://example.org/early.svg'}],
                       'glyph_research': {'historical_glyphs': {'items': [
                           {'id':'early', 'period':'Shang oracle script', 'tradition':'Modern vector redraw'}]}}}
            with patch('pipeline.glyph_assets.render_glyph_images', return_value={'early': image}):
                runner.run('factual', {'article': {'components': []}, 'dossier': dossier},
                           editorial.REVIEW_SCHEMA, root/'stage')
            prompt = (root/'stage/prompt.txt').read_text()
            inputs, _ = json.JSONDecoder().raw_decode(prompt.split('\nINPUTS:\n', 1)[1])
            attachment = inputs['attached_images'][0]
            self.assertEqual(attachment['attachment_scope'], 'selected_historical_glyph')
            self.assertEqual(attachment['period'], 'Shang oracle script')
            self.assertEqual(attachment['tradition'], 'Modern vector redraw')
            self.assertIn('not the script period', prompt)

    def test_actual_jin_label_reversal_routes_to_adjudication(self):
        previous = {'verdict': 'revise', 'findings': [
            'Change `meaning_history.senses[0].status` from `earliest_attested` to `historical`.']}
        current = {'verdict': 'revise', 'findings': [
            'Set `meaning_history.senses[0].status` to `earliest_attested`.']}
        self.assertEqual(status_conflicts(current, [previous]), ['meaning_history/senses/0/status'])
        self.assertEqual(status_conflicts(current, [current]), [])
        self.assertEqual(status_conflicts({'findings': ['Set `meaning_history.senses[1].status` to `current`.']}, [previous]), [])

    def test_ordinary_revise_is_one_call_and_still_rejected(self):
        class Reviewer:
            model = 'fixture'
            calls = 0
            def run(self, role, inputs, schema, directory):
                self.calls += 1
                return {'verdict': 'revise', 'findings': ['Correct the unsupported source claim.']}
        with tempfile.TemporaryDirectory() as root:
            runner = Reviewer()
            result = editorial.independent_review('factual', ARTICLE_V2, DOSSIER, root, runner)
            self.assertEqual(runner.calls, 1)
            self.assertEqual(result['verdict'], 'revise')
            self.assertEqual(result['article_hash'], editorial.digest(ARTICLE_V2))

    def test_conflict_gets_genuine_second_invocation_receipt(self):
        class Reviewer:
            model = 'fixture'
            calls = []
            def run(self, role, inputs, schema, directory):
                self.calls.append(inputs)
                editorial.write(Path(directory)/'meta.json', {'agent_thread_ids': [f'thread-{len(self.calls)}']})
                return {'verdict': 'revise', 'findings': ['Set `meaning_history.senses[0].status` to `earliest_attested`.']}
        with tempfile.TemporaryDirectory() as root:
            runner = Reviewer()
            result = editorial.independent_review('factual', ARTICLE_V2, DOSSIER, root, runner, {
                'earlier_correction_history': [{'findings': ['Change `meaning_history.senses[0].status` to `historical`.']}]})
            self.assertEqual(len(runner.calls), 2)
            self.assertEqual(runner.calls[1]['disputed_fields'], ['meaning_history/senses/0/status'])
            self.assertIn('thread-2', result['reviewer'])
            self.assertEqual(result['verdict'], 'revise')

    def test_budget_and_hold_preserve_unapproved_candidate(self):
        class Reviewer:
            model = 'fixture'
            def __init__(self, action):
                self.calls = []; self.action = action
            def run(self, role, inputs, schema, directory):
                self.calls.append(role)
                if role in ('editor', 'revision'):
                    return copy.deepcopy(inputs['article'])
                if role in ('factual', 'readability'):
                    return {'verdict': 'revise', 'findings': ['Clarify the supported tree account.']}
                if role == 'revision_plan':
                    assert inputs['consolidated_corrections'] == ['Clarify the supported tree account.']
                    return {'action': self.action, 'reason': 'Unresolved evidence disagreement.'}
                raise AssertionError(role)
        dossier = {**copy.deepcopy(DOSSIER), 'glyph_research': {'historical_glyphs': copy.deepcopy(GLYPHS)}}
        for action in ('edit', 'hold'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as root:
                runner = Reviewer(action)
                state = editorial.refine(ARTICLE_V2, dossier, root, runner, max_revisions=10)
                self.assertEqual(state['status'], 'needs_revision')
                self.assertEqual(state['revision_limit'], 2)
                self.assertEqual(runner.calls.count('revision'), 2 if action == 'edit' else 0)
                self.assertEqual(state['stop_reason'], 'revision_budget_exhausted' if action == 'edit' else 'conflicting_review_instructions')
                self.assertTrue((Path(root)/'article.json').exists())
                self.assertFalse(any(r['verdict'] == 'pass' for r in json.loads((Path(root)/'reviews.json').read_text())))

    def test_consolidation_keeps_receipts_but_removes_exact_duplicates(self):
        self.assertEqual(consolidated_findings([
            {'verdict': 'revise', 'findings': ['A', 'B']},
            {'verdict': 'revise', 'findings': ['A', 'C']}]), ['A', 'B', 'C'])

    def test_repeated_caveat_gets_review_not_automatic_approval(self):
        review = editorial.make_review('readability', 'revise',
            ['Qualify `learner.overview` clearly.'], ARTICLE_V2, DOSSIER, 'fixture-original')
        self.assertEqual(repeated_fields(review, [review, review]), ['learner.overview'])
        class Reviewer:
            model = 'fixture'; reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                self.inputs = inputs
                editorial.write(Path(directory)/'meta.json', {'agent_thread_ids': ['real-fixture-invocation']})
                return {'verdict':'revise', 'findings':['A real remaining unsupported claim.']}
        with tempfile.TemporaryDirectory() as root:
            runner = Reviewer()
            deciding = editorial.adjudicate_review(review, ARTICLE_V2, DOSSIER, root, runner)
            self.assertEqual(deciding['verdict'], 'revise')
            self.assertIn('real-fixture-invocation', deciding['reviewer'])
            self.assertEqual(runner.inputs['proposed_review'], review)
            bad = {**review, 'article_hash':'wrong'}
            with self.assertRaisesRegex(ValueError, 'current pair'):
                editorial.adjudicate_review(bad, ARTICLE_V2, DOSSIER, root, runner)


if __name__ == '__main__':
    unittest.main()
