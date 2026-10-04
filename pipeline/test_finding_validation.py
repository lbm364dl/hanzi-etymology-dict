import json
from pathlib import Path
import tempfile
import unittest

from pipeline import editorial, finding_validation


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


class FixtureRunner:
    model = 'gpt-6-luna'
    reasoning = 'low'

    def __init__(self, build):
        self.build = build
        self.role = None
        self.inputs = None
        self.schema = None
        self.directory = None

    def run(self, role, inputs, schema, directory):
        self.role, self.inputs, self.schema, self.directory = role, inputs, schema, Path(directory)
        result = self.build(inputs, schema)
        self.directory.mkdir(parents=True, exist_ok=True)
        _write(self.directory / 'result.json', result)
        _write(self.directory / 'schema.json', schema)
        _write(self.directory / 'meta.json', {
            'status': 'complete', 'role': role, 'model': self.model, 'reasoning': self.reasoning,
            'fingerprint': 'fixture-fingerprint', 'agent_thread_ids': ['fixture-thread'],
            'result_hash': editorial.digest(result),
        })
        return result


class FindingValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.job = Path(self.temp.name) / 'job'
        self.article = {'character': '木', 'summary': {'text': 'A tree.', 'evidence_ids': ['source:1']},
            'history': [], 'uncertainties': [],
            'formation': {'type': 'pictographic', 'text': 'A drawing of a tree.', 'evidence_ids': ['source:1']},
            'components': [{'form': '木', 'origin_form': '', 'roles': ['pictorial'],
                'form_status': 'stylized', 'text': 'The whole graph depicts a tree.',
                'evidence_ids': ['source:1']}]}
        self.dossier = {'character': '木', 'context': {}, 'evidence': [{
            'id': 'source:1', 'source': 'test', 'field': 'etymology', 'text': 'A tree.',
            'kind': 'source', 'record_character': '木', 'url': 'https://example.org/tree',
            'title': 'Tree form', 'accessed_at': '2026-09-26'}],
            'external_research': {'search_audit': [{'query': '木 form',
                'urls': ['https://example.org/tree'], 'outcome': 'Inspected tree form explanation.'}], 'gaps': []}}
        self.reviews = [
            editorial.make_review('factual', 'pass', [], self.article, self.dossier, 'factual-thread'),
            editorial.make_review('readability', 'pass', [], self.article, self.dossier, 'readability-thread'),
        ]
        _write(self.job / 'article.json', self.article)
        _write(self.job / 'dossier.json', self.dossier)
        _write(self.job / 'reviews.json', self.reviews)
        self.proposals = [
            {'topic': 'wrong-definition', 'details': 'The current definition is incorrect.'},
            {'topic': 'style-preference', 'details': 'Prefer a different wording.'},
        ]

    def build(self, confirmations):
        def result(inputs, schema):
            return {'article_hash': inputs['article_hash'], 'dossier_hash': inputs['dossier_hash'],
                    'findings': [{'topic': topic, 'confirmed': verdict, 'reason': reason}
                                 for topic, verdict, reason in confirmations]}
        return result

    def test_confirmed_defect_survives_and_unconfirmed_proposal_is_removed(self):
        runner = FixtureRunner(self.build([
            ('wrong-definition', True, 'The cited dossier directly contradicts the current definition.'),
            ('style-preference', False, 'This is only a wording preference, with no material readability issue.'),
        ]))
        confirmed = finding_validation.validate_proposals(
            self.job, self.proposals, self.article, self.dossier, runner)
        self.assertEqual(confirmed, [self.proposals[0]])
        self.assertEqual(runner.role, 'finding_validation')
        receipt = editorial.read(self.job / 'finding-validation/decision.json')
        self.assertEqual(receipt['article_hash'], editorial.digest(self.article))
        self.assertEqual(receipt['dossier_hash'], editorial.digest(self.dossier))
        self.assertIs(receipt['authorship_changed'], False)
        self.assertIs(receipt['review_approval_created'], False)

    def test_rejects_result_with_wrong_pair_hash(self):
        runner = FixtureRunner(lambda inputs, schema: {
            'article_hash': 'wrong', 'dossier_hash': inputs['dossier_hash'],
            'findings': [{'topic': p['topic'], 'confirmed': False, 'reason': 'Rejected.'}
                         for p in self.proposals],
        })
        with self.assertRaises(ValueError):
            finding_validation.validate_proposals(self.job, self.proposals, self.article, self.dossier, runner)
        self.assertFalse((self.job / 'finding-validation/decision.json').exists())

    def test_rejects_duplicate_decision_topics_fail_closed(self):
        runner = FixtureRunner(lambda inputs, schema: {
            'article_hash': inputs['article_hash'], 'dossier_hash': inputs['dossier_hash'],
            'findings': [
                {'topic': 'wrong-definition', 'confirmed': True, 'reason': 'Confirmed.'},
                {'topic': 'wrong-definition', 'confirmed': False, 'reason': 'Duplicate.'},
            ],
        })
        with self.assertRaises(ValueError):
            finding_validation.validate_proposals(self.job, self.proposals, self.article, self.dossier, runner)
        self.assertFalse((self.job / 'finding-validation/decision.json').exists())

    def test_rejects_schema_invalid_decision_and_keeps_agent_receipt(self):
        runner = FixtureRunner(lambda inputs, schema: {
            'article_hash': inputs['article_hash'], 'dossier_hash': inputs['dossier_hash'],
            'findings': [
                {'topic': 'wrong-definition', 'confirmed': 'yes', 'reason': 'Bad boolean type.'},
                {'topic': 'style-preference', 'confirmed': False, 'reason': 'Preference only.'},
            ],
        })
        with self.assertRaisesRegex(ValueError, 'schema'):
            finding_validation.validate_proposals(self.job, self.proposals, self.article, self.dossier, runner)
        self.assertTrue((self.job / 'finding-validation/result.json').is_file())
        self.assertTrue((self.job / 'finding-validation/meta.json').is_file())
        self.assertFalse((self.job / 'finding-validation/decision.json').exists())

    def test_rejects_missing_and_duplicate_proposal_topics_before_agent_call(self):
        runner = FixtureRunner(self.build([]))
        with self.assertRaisesRegex(ValueError, 'duplicate topics'):
            finding_validation.validate_proposals(
                self.job, [self.proposals[0], self.proposals[0]], self.article, self.dossier, runner)
        self.assertIsNone(runner.role)

    def test_requires_exact_passed_pair_and_low_model(self):
        changed = {**self.article, 'summary': {'text': 'changed', 'evidence_ids': ['E1']}}
        runner = FixtureRunner(self.build([
            ('wrong-definition', False, 'No current defect.'),
            ('style-preference', False, 'No material readability issue.'),
        ]))
        with self.assertRaisesRegex(ValueError, 'differ from the job'):
            finding_validation.validate_proposals(self.job, self.proposals, changed, self.dossier, runner)
        self.assertIsNone(runner.role)
        runner.reasoning = 'high'
        with self.assertRaisesRegex(ValueError, 'low reasoning'):
            finding_validation.validate_proposals(self.job, self.proposals, self.article, self.dossier, runner)

    def test_rejects_pair_changes_while_agent_is_running(self):
        class MutatingRunner(FixtureRunner):
            def run(inner_self, role, inputs, schema, directory):
                result = super(MutatingRunner, inner_self).run(role, inputs, schema, directory)
                changed = {**self.article, 'summary': {
                    'text': 'concurrently edited', 'evidence_ids': ['source:1']}}
                _write(self.job / 'article.json', changed)
                return result

        runner = MutatingRunner(self.build([
            ('wrong-definition', True, 'A concrete current defect.'),
            ('style-preference', False, 'Only a style preference.'),
        ]))
        with self.assertRaisesRegex(ValueError, 'changed during finding validation'):
            finding_validation.validate_proposals(self.job, self.proposals, self.article, self.dossier, runner)
        self.assertTrue((self.job / 'finding-validation/result.json').is_file())
        self.assertFalse((self.job / 'finding-validation/decision.json').exists())


if __name__ == '__main__':
    unittest.main()
