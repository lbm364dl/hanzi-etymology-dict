import unittest

from pipeline.ocr_verification import packet, validate_result


class OCRVerificationTests(unittest.TestCase):
    def setUp(self):
        self.occurrences = packet('甲的乙', [dict(id='p614:1', start=1, end=2, before='的', after='旳')])

    def test_wrong_anchor_rejected(self):
        with self.assertRaises(ValueError):
            packet('甲的乙', [dict(id='x', start=1, end=2, before='昧', after='旳')])

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


if __name__ == '__main__':
    unittest.main()
