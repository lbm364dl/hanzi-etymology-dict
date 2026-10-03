import unittest
import tempfile
from jsonschema import Draft202012Validator, ValidationError

from pipeline.ocr_verification import packet, validate_result, verify


class OCRVerificationTests(unittest.TestCase):
    def setUp(self):
        self.occurrences = packet('甲的乙', [dict(id='p614:1', start=1, end=2, before='的', after='旳')])

    def test_wrong_anchor_rejected(self):
        with self.assertRaises(ValueError):
            packet('甲的乙', [dict(id='x', start=1, end=2, before='昧', after='旳')])

    def test_agent_schema_binds_raw_tokens_and_occurrence_ids(self):
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(inner, role, inputs, schema, directory):
                good = {'occurrences': [dict(id='target', raw_text='楛', printed_text=None,
                    verdict='unresolved_identity', reason='Test fixture') ]}
                validator = Draft202012Validator(schema)
                validator.validate(good)
                for field, value in [('raw_text', '栢'), ('id', 'invented')]:
                    bad = {'occurrences': [{**good['occurrences'][0], field: value}]}
                    with self.assertRaises(ValidationError):
                        validator.validate(bad)
                return good
        with tempfile.TemporaryDirectory() as directory:
            verify('楛(杯)', [dict(id='target', start=0, end=1, before='楛', after='桮')],
                [{'path':'test-fixture', 'pdf_page':1}], {}, Runner(), directory)

    def test_different_ids_cannot_duplicate_or_overlap_an_occurrence(self):
        first = dict(id='one', start=0, end=2, before='端组', after='端纽')
        for second in (dict(id='two', start=0, end=2, before='端组', after='端纽'),
                       dict(id='two', start=1, end=2, before='组', after='纽')):
            with self.assertRaisesRegex(ValueError, 'distinct and nonoverlapping'):
                packet('端组端组', [first, second])
        separate = dict(id='two', start=2, end=4, before='端组', after='端纽')
        self.assertEqual(len(packet('端组端组', [first, separate])), 2)

    def test_empty_review_does_not_approve(self):
        with self.assertRaises(ValueError):
            validate_result({'occurrences': []}, self.occurrences)

    def test_mislocated_correct_raw_rejected(self):
        with self.assertRaises(ValueError):
            validate_result({'occurrences': [dict(id='p614:1', raw_text='的', printed_text='昧', verdict='correct_raw', reason='Wrong location')]}, self.occurrences)

    def test_rejected_proposal_preserves_raw(self):
        result = {'occurrences': [dict(id='p614:1', raw_text='的', printed_text='的', verdict='correct_raw', reason='Visible 白 matches raw text')]}
        self.assertEqual(validate_result(result, self.occurrences), result)

    def test_unresolved_identity_cannot_guess(self):
        with self.assertRaises(ValueError):
            validate_result({'occurrences': [dict(id='p614:1', raw_text='的', printed_text='旳', verdict='unresolved_identity', reason='Unclear')]}, self.occurrences)

    def test_unsupported_raw_identity_is_distinct_from_unresolved_match_and_has_no_guess(self):
        unsupported = {'occurrences': [dict(id='p614:1', raw_text='的', printed_text=None,
            verdict='unsupported_raw_identity', reason='Visible strokes do not support raw scalar; exact Unicode unresolved')]}
        self.assertEqual(validate_result(unsupported, self.occurrences), unsupported)
        for printed in ('的', '旳'):
            with self.assertRaisesRegex(ValueError, 'must not guess Unicode'):
                validate_result({'occurrences': [{**unsupported['occurrences'][0],
                    'printed_text': printed}]}, self.occurrences)


if __name__ == '__main__':
    unittest.main()
