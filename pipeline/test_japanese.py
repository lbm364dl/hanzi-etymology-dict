"""Japanese adaptation boundaries, with isolated files and no model/network calls."""
import copy
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

from pipeline import editorial, japanese
from pipeline.test_editorial import ARTICLE_V2, DOSSIER, GLYPHS


class JapaneseTests(unittest.TestCase):
    def test_japanese_profile_is_instruction_before_input_packet(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            command = [sys.executable, '-c',
                       "from pathlib import Path; Path('{output}').write_text('{{}}')"]
            schema = {'type':'object', 'properties':{}, 'additionalProperties':False}
            for runner, folder in [(japanese.JapaneseRunner(command), 'ja'),
                                   (editorial.Runner(command), 'zh')]:
                self.assertEqual(runner.run('analysis', {}, schema, root/folder), {})
            jp = (root/'ja/prompt.txt').read_text()
            chinese = (root/'zh/prompt.txt').read_text()
            self.assertIn(japanese.JAPANESE_POLICY, jp.split('\nINPUTS:\n', 1)[0])
            self.assertNotIn(japanese.JAPANESE_POLICY, chinese)

    def test_retired_source_remains_auditable_but_cannot_be_cited(self):
        dossier = self.dossier()
        source_id = dossier['evidence'][0]['id']
        dossier['retired_evidence_ids'] = [source_id]
        editorial.validate_dossier(dossier)
        with self.assertRaisesRegex(ValueError, 'retired source paraphrase'):
            editorial.validate_sections([{'text':'A claim.', 'evidence_ids':[source_id]}], dossier)
        dossier['retired_evidence_ids'] = ['missing-record']
        with self.assertRaisesRegex(ValueError, 'retained dossier records'):
            editorial.validate_dossier(dossier)

    def test_learner_coverage_repair_preserves_expert_article(self):
        article, dossier = self.japanese_article()
        correct = copy.deepcopy(article['learner'])
        article['learner']['components'] = []
        expert_before = {k:v for k,v in article.items() if k != 'learner'}
        class Runner:
            def run(self, role, inputs, schema, directory):
                self.inputs = inputs
                return correct
        runner = Runner()
        repaired = editorial.repair_learner_length(article, dossier, Path('/unused'), runner)
        self.assertEqual(runner.inputs['required_component_indices'], [0])
        self.assertEqual({k:v for k,v in repaired.items() if k != 'learner'}, expert_before)
        editorial.validate_learner(repaired, dossier, editorial.validate_sections)

    def test_retired_citation_ids_and_feedback_use_same_model_aliases(self):
        dossier = self.dossier()
        source_id = dossier['evidence'][0]['id']
        dossier['retired_evidence_ids'] = [source_id]
        inputs, aliases = editorial.citation_transport({'dossier':dossier,
            'feedback':{'findings':['Stop citing '+source_id]}})
        alias = inputs['dossier']['evidence'][0]['id']
        self.assertEqual(inputs['dossier']['retired_evidence_ids'], [alias])
        self.assertEqual(inputs['feedback']['findings'], ['Stop citing '+alias])
        self.assertEqual(aliases[alias], source_id)

    def test_review_packet_keeps_provenance_without_second_article(self):
        article, dossier = self.japanese_article()
        dossier['source_reuse'] = {'article_hash':'parent-hash', 'prior_analysis':{'language':'zh'}}
        with patch.object(editorial.Runner, 'run', return_value={'verdict':'pass','findings':[]}) as run:
            japanese.JapaneseRunner([]).run('factual', {'article':article,'dossier':dossier}, {}, Path('/unused'))
        packet = run.call_args.args[1]
        self.assertNotIn('prior_analysis', packet['dossier']['source_reuse'])
        self.assertEqual(packet['dossier']['source_reuse']['article_hash'], 'parent-hash')
        self.assertEqual(packet['current_article_index']['language'], 'ja')
        self.assertIn('prior_analysis', dossier['source_reuse'])

    def test_targeted_revision_preserves_other_fields_and_restores_citations(self):
        article, dossier = self.japanese_article()
        before = copy.deepcopy(article)
        source_id = dossier['evidence'][0]['id']
        patch_result = {'edits':[
            {'path':'summary/text','value_json':json.dumps('Trees and wood.')},
            {'path':'summary/evidence_ids','value_json':json.dumps(['ref001'])}]}
        with patch.object(editorial.Runner, 'run', return_value=patch_result) as run:
            result = japanese.JapaneseRunner([]).run('revision', {'article':article,'dossier':dossier}, editorial.WRITER_SCHEMA, Path('/unused'))
        self.assertEqual(run.call_args.args[0], 'article_patch')
        self.assertEqual(result['summary']['text'], 'Trees and wood.')
        self.assertEqual(result['summary']['evidence_ids'], [source_id])
        self.assertEqual(result['components'], before['components'])
        self.assertEqual(result['japanese_usage'], before['japanese_usage'])
        self.assertEqual(article, before)

    def test_targeted_revision_rejects_overlapping_edits(self):
        article, dossier = self.japanese_article()
        patch_result = {'edits':[{'path':'summary','value_json':'{}'},
                                 {'path':'summary/text','value_json':'"text"'}]}
        with patch.object(editorial.Runner, 'run', return_value=patch_result):
            with self.assertRaisesRegex(ValueError, 'nonoverlapping'):
                japanese.JapaneseRunner([]).run('revision', {'article':article,'dossier':dossier}, editorial.WRITER_SCHEMA, Path('/unused'))

    def test_invalid_patch_is_repaired_before_any_change_is_applied(self):
        article, dossier = self.japanese_article()
        before = copy.deepcopy(article)
        invalid = {'edits':[{'path':'summary','value_json':'{}'},
                            {'path':'summary/text','value_json':'"overlap"'}]}
        correct = {'edits':[{'path':'summary/text','value_json':'"Repaired wording."'}]}
        with patch.object(editorial.Runner, 'run', side_effect=[invalid, correct]) as run:
            result = japanese.JapaneseRunner([]).run('revision', {'article':article,'dossier':dossier}, editorial.WRITER_SCHEMA, Path('/unused'))
        self.assertEqual(run.call_count, 2)
        self.assertIn('nonoverlapping', run.call_args.args[1]['validation_findings'][0])
        self.assertEqual(result['summary']['text'], 'Repaired wording.')
        self.assertEqual(result['components'], before['components'])
        self.assertEqual(article, before)

    def test_patch_accepts_verbatim_prose_but_rejects_malformed_array(self):
        article, dossier = self.japanese_article()
        with patch.object(editorial.Runner, 'run', return_value={'edits':[
                {'path':'summary/text','value_json':'Verbatim model wording.'}]}):
            result = japanese.JapaneseRunner([]).run('revision', {'article':article,'dossier':dossier}, editorial.WRITER_SCHEMA, Path('/unused'))
        self.assertEqual(result['summary']['text'], 'Verbatim model wording.')
        with patch.object(editorial.Runner, 'run', return_value={'edits':[
                {'path':'components/0/roles','value_json':'not an array'}]}):
            with self.assertRaises(json.JSONDecodeError):
                japanese.JapaneseRunner([]).run('revision', {'article':article,'dossier':dossier}, editorial.WRITER_SCHEMA, Path('/unused'))

    def test_allowed_patch_paths_constrain_model_schema(self):
        article, dossier = self.japanese_article()
        result = {'edits':[{'path':'summary/text','value_json':'A focused edit.'}]}
        with patch.object(editorial.Runner, 'run', return_value=result) as run:
            japanese.JapaneseRunner([]).run('editor', {'article':article,'dossier':dossier,
                'feedback':{'allowed_edit_paths':['summary/text']}}, editorial.WRITER_SCHEMA, Path('/unused'))
        self.assertEqual(run.call_args.args[2]['properties']['edits']['items']['properties']['path']['enum'], ['summary/text'])

    def test_patch_retry_reports_multiple_schema_errors_with_paths(self):
        article, dossier = self.japanese_article()
        invalid = {'edits':[{'path':'summary/text','value_json':'42'},
                            {'path':'components/0/roles','value_json':'[]'}]}
        with patch.object(editorial.Runner, 'run', side_effect=[invalid, {'edits':[
                {'path':'summary/text','value_json':json.dumps(article['summary']['text'])},
                {'path':'components/0/roles','value_json':json.dumps(article['components'][0]['roles'])}]}]) as run:
            japanese.JapaneseRunner([]).run('revision', {'article':article,'dossier':dossier}, editorial.WRITER_SCHEMA, Path('/unused'))
        findings = run.call_args.args[1]['validation_findings'][0]
        self.assertIn('summary.text', findings)
        self.assertIn('roles', findings)

    def dossier(self):
        dossier = copy.deepcopy(DOSSIER)
        dossier["glyph_research"] = {"historical_glyphs":copy.deepcopy(GLYPHS)}
        return dossier

    def reviews(self, article, dossier):
        return [editorial.make_review(role, 'pass', [], article, dossier, 'fixture-'+role)
                for role in ('factual', 'readability')]

    def local(self, root, character='木'):
        editorial.write(root/'output/kanji_etymology.jsonl', None)
        (root/'output/kanji_etymology.jsonl').write_text(
            '{"character":"'+character+'","readings":{"japanese_kun":"き"},"definition":"tree"}\n',
            encoding='utf-8')

    def chinese(self, root, character='木'):
        article, dossier = copy.deepcopy(ARTICLE_V2), self.dossier()
        if character != '木':
            article = json.loads(json.dumps(article, ensure_ascii=False).replace('木', character))
            dossier = json.loads(json.dumps(dossier, ensure_ascii=False).replace('木', character))
        path = editorial.publish(article, dossier, self.reviews(article, dossier), root/'content/entries')
        return path, article, dossier

    def usage(self):
        return {'summary': {'text':'Used for trees and wood.', 'evidence_ids':['source:1']},
                'readings':[{'reading':'き', 'type':'kun', 'example':'木', 'example_reading':'き',
                             'gloss':'tree', 'text':'A native Japanese word written with 木.',
                             'evidence_ids':['source:1']}]}

    def japanese_article(self):
        article = copy.deepcopy(ARTICLE_V2)
        article.update(language='ja', japanese_usage=self.usage())
        dossier = self.dossier()
        dossier['context']['target_language'] = 'ja'
        return article, dossier

    def test_exact_graph_reuse_retains_audited_hashes_without_mutating_chinese(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.local(root)
            path, article, dossier = self.chinese(root)
            before = {p: p.read_bytes() for p in (root/'content').rglob('*.json')}
            packet = japanese.prepare('木', root)
            reuse = packet['source_reuse']
            self.assertTrue(reuse['same_graph'])
            self.assertEqual(reuse['article_hash'], editorial.digest(article))
            self.assertEqual(reuse['dossier_hash'], editorial.digest(dossier))
            self.assertEqual(reuse['prior_analysis'], article)
            self.assertEqual(packet['context']['target_language'], 'ja')
            self.assertEqual(packet['evidence'][-1]['kind'], 'imported_metadata')
            packet['evidence'][0]['text'] = 'Modified only in memory'
            packet['source_reuse']['prior_analysis']['summary']['text'] = 'Modified only in memory'
            self.assertEqual(before, {p: p.read_bytes() for p in (root/'content').rglob('*.json')})

    def test_reuse_rejects_tampered_approved_chinese_article(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.local(root)
            path, _, _ = self.chinese(root)
            entry = editorial.read(path); entry['summary']['text'] = 'Unreviewed change'
            editorial.write(path, entry)
            with self.assertRaisesRegex(ValueError, 'integrity'):
                japanese.prepare('木', root)

    def test_related_graph_never_silently_reuses_counterpart_prose(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.local(root, '気')
            self.chinese(root, '氣')
            # Imported local metadata can identify a relative, but does not approve it.
            (root/'output/kanji_etymology.jsonl').write_text(
                '{"character":"気","var":{"traditional":"U+6C23"},"definition":"spirit"}\n')
            original = {p:p.read_bytes() for p in (root/'content').rglob('*.json')}
            packet = japanese.prepare('気', root)
            self.assertFalse(packet['source_reuse']['same_graph'])
            self.assertNotIn('prior_analysis', packet['source_reuse'])
            self.assertEqual(packet['character'], '気')
            self.assertEqual(original, {p:p.read_bytes() for p in (root/'content').rglob('*.json')})

    def test_preparation_requires_japanese_local_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.local(root)
            with self.assertRaisesRegex(ValueError, 'No Japanese local record'):
                japanese.prepare('気', root)

    def test_japanese_validation_requires_usage_and_correct_language_target(self):
        article, dossier = self.japanese_article()
        editorial.validate_article(article, dossier)
        absent = copy.deepcopy(article); absent.pop('japanese_usage')
        with self.assertRaisesRegex(ValueError, 'requires cited Japanese usage'):
            editorial.validate_article(absent, dossier)
        wrong = copy.deepcopy(dossier); wrong['context'].pop('target_language')
        with self.assertRaisesRegex(ValueError, 'language differs'):
            editorial.validate_article(article, wrong)
        chinese = copy.deepcopy(ARTICLE_V2)
        with self.assertRaisesRegex(ValueError, 'language differs'):
            editorial.validate_article(chinese, dossier)

    def test_character_reading_notes_need_no_word_examples(self):
        article, dossier = self.japanese_article()
        for key in ('example', 'example_reading', 'gloss'):
            article['japanese_usage']['readings'][0].pop(key)
        editorial.validate_article(article, dossier)
        fields = editorial.CHARACTER_JAPANESE_USAGE['properties']['readings']['items']['properties']
        self.assertFalse({'example', 'example_reading', 'gloss'}.intersection(fields))

    def test_reading_examples_are_character_specific_and_cited(self):
        article, dossier = self.japanese_article()
        article['japanese_usage']['readings'][0]['example'] = '山'
        with self.assertRaisesRegex(ValueError, 'must contain'):
            editorial.validate_article(article, dossier)
        article['japanese_usage']['readings'][0]['example'] = '木'
        article['japanese_usage']['readings'][0]['evidence_ids'] = ['nonexistent']
        with self.assertRaisesRegex(ValueError, 'unknown evidence'):
            editorial.validate_article(article, dossier)

    def test_kun_example_must_illustrate_selected_reading(self):
        article, dossier = self.japanese_article()
        selected = article['japanese_usage']['readings'][0]
        selected.update(reading='き', type='kun', example='木目', example_reading='もくめ')
        with self.assertRaisesRegex(ValueError, 'kun reading is not illustrated'):
            editorial.validate_article(article, dossier)
        selected.update(example='木', example_reading='き')
        editorial.validate_article(article, dossier)

    def test_japanese_learner_requires_current_components_but_history_is_optional(self):
        from pipeline.structured import validate_learner
        article, dossier = self.japanese_article()
        old = copy.deepcopy(article['components'][0]); old['scope_character'] = '學'
        article['components'].append(old)
        validate_learner(article, dossier, editorial.validate_sections)
        historic_card = copy.deepcopy(article['learner']['components'][0])
        historic_card['component_index'] = 1
        article['learner']['components'].append(historic_card)
        validate_learner(article, dossier, editorial.validate_sections)
        article['learner']['components'] = [historic_card]
        with self.assertRaisesRegex(ValueError, 'current-form component'):
            validate_learner(article, dossier, editorial.validate_sections)
        article['learner']['components'] = [historic_card, historic_card]
        with self.assertRaisesRegex(ValueError, 'exactly once'):
            validate_learner(article, dossier, editorial.validate_sections)
        article.pop('language')
        article['learner']['components'] = [copy.deepcopy(ARTICLE_V2['learner']['components'][0])]
        validate_learner(article, dossier, editorial.validate_sections)

    def test_independent_japanese_publication_is_separate_and_preserves_chinese(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.chinese(root)
            before = {p:p.read_bytes() for p in (root/'content').rglob('*.json')}
            article, dossier = self.japanese_article()
            job = root/'job'
            for name, value in [('status.json', {'status':'approved'}), ('article.json', article),
                                ('dossier.json', dossier), ('reviews.json', self.reviews(article, dossier))]:
                editorial.write(job/name, value)
            path = japanese.publish_job(job, root)
            self.assertEqual(path, root/'content/ja/entries/6728.json')
            self.assertEqual(editorial.validate_published(editorial.read(path))['language'], 'ja')
            self.assertTrue((root/'content/ja/provenance/6728.json').exists())
            self.assertEqual(before, {p:p.read_bytes() for p in before})

    def test_japanese_publication_does_not_accept_chinese_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); job = root/'job'
            for name, value in [('status.json', {'status':'approved'}), ('article.json', ARTICLE_V2),
                                ('dossier.json', DOSSIER), ('reviews.json', self.reviews(ARTICLE_V2, DOSSIER))]:
                editorial.write(job/name, value)
            with self.assertRaisesRegex(ValueError, 'non-Japanese'):
                japanese.publish_job(job, root)
            self.assertFalse((root/'content/ja').exists())

    def test_ready_checks_reapproved_chinese_parent_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            chinese_path, parent, parent_dossier = self.chinese(root)
            article, dossier = self.japanese_article()
            dossier['source_reuse'] = {'same_graph':True,
                'entry_path':str(chinese_path.relative_to(root)),
                'article_hash':editorial.digest(parent),
                'dossier_hash':editorial.digest(parent_dossier)}
            editorial.publish(article, dossier, self.reviews(article, dossier), root/'content/ja/entries')
            self.assertTrue(japanese.ready('木', root))
            parent['summary']['text'] = 'A reviewed drawing of a tree.'
            editorial.publish(parent, parent_dossier, self.reviews(parent, parent_dossier), root/'content/entries')
            self.assertFalse(japanese.ready('木', root))

    def test_missing_or_corrupt_japanese_publication_is_not_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertFalse(japanese.ready('木', root))
            article, dossier = self.japanese_article()
            path = editorial.publish(article, dossier, self.reviews(article, dossier), root/'content/ja/entries')
            self.assertTrue(japanese.ready('木', root))
            entry = editorial.read(path)
            entry['summary']['text'] = 'Unreviewed corruption'
            editorial.write(path, entry)
            self.assertFalse(japanese.ready('木', root))

    def test_current_publication_prevents_cached_job_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            editorial.write(output/'6728/status.json', {'status':'approved'})
            with patch('pipeline.japanese.ready', return_value=True), \
                    patch('pipeline.japanese.publish_job') as publish, \
                    patch('pipeline.japanese.prepare') as prepare:
                result = japanese.process('木', output)
            self.assertTrue(result['reused_publication'])
            publish.assert_not_called()
            prepare.assert_not_called()


if __name__ == '__main__':
    unittest.main()
