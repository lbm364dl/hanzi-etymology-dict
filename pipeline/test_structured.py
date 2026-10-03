"""Scope and unknown-reading regression tests independent of article authoring."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.editorial import validate_article, validate_published
from pipeline.structured import (UNIHAN_HSK1_READINGS, REVIEW_V2_POLICY, V2_POLICY,
                                 default_unihan_readings_path, component_is_current_form,
                                 validate_modern_mandarin_sound)
from pipeline.test_editorial import ARTICLE_V2, DOSSIER, GLYPHS


def fixture():
    article = copy.deepcopy(ARTICLE_V2)
    article['character'] = '爱'
    article.pop('learner', None)
    article['meaning_history']['senses'][0]['id'] = '爱:affection'
    section = {'text': 'Fixture claim.', 'evidence_ids': ['source:1']}
    article['components'] = [{**section, 'form': '心', 'origin_form': '',
        'origin_relation': 'none', 'roles': ['semantic'], 'form_status': 'preserved',
        'scope_character': '愛', 'sound': [], 'sound_limitation': None}]
    article['relationships'] = [
        {**section, 'id': 'sense', 'subject': {'kind': 'character', 'id': '爱'},
         'object': {'kind': 'sense', 'id': '爱:affection'}, 'predicate': 'has_sense',
         'context_character': '爱', 'certainty': 'established'},
        {**section, 'id': 'graphic', 'subject': {'kind': 'character', 'id': '爱'},
         'object': {'kind': 'character', 'id': '愛'}, 'predicate': 'simplified_from',
         'context_character': '爱', 'certainty': 'established'},
        {**section, 'id': 'component', 'subject': {'kind': 'component', 'id': '心'},
         'object': {'kind': 'character', 'id': '愛'}, 'predicate': 'semantic_component_of',
         'context_character': '爱', 'certainty': 'established'}]
    dossier = {**copy.deepcopy(DOSSIER), 'character': '爱',
               'glyph_research': {'historical_glyphs': GLYPHS}}
    return article, dossier


def noncharacter_mark_fixture():
    """A sourced visible mark with disputed historical glyph readings (e.g. 本)."""
    article = copy.deepcopy(ARTICLE_V2)
    dossier = copy.deepcopy(DOSSIER)
    article["character"] = dossier["character"] = "本"
    dossier["evidence"][0].update(record_character="本",
        text="A drawing of 本 shows 木 with a separate short horizontal mark below it, indicating the root.")
    dossier["glyph_research"] = {"historical_glyphs": copy.deepcopy(GLYPHS)}
    article["summary"] = {"text": "本 combines 木 with a lower mark indicating the tree’s root.",
                          "evidence_ids": ["source:1"]}
    article["formation"] = {"type": "indicative",
        "text": "木 depicts a tree and a separate lower mark indicates its root.", "evidence_ids": ["source:1"]}
    article["components"] = [
        {"form": "木", "origin_form": "", "origin_relation": "none", "scope_character": "本",
         "roles": ["pictorial"], "form_status": "preserved", "sound": [], "sound_limitation": None,
         "text": "木 depicts the tree.", "evidence_ids": ["source:1"]},
        {"form": "", "origin_form": "", "origin_relation": "none", "scope_character": "本",
         "element_kind": "noncharacter_mark", "element_id": "本:mark:lower-1",
         "element_label": "short horizontal mark", "roles": ["indicator"], "form_status": "disputed",
         "sound": [], "sound_limitation": None,
         "text": "A separate short horizontal mark below 木 indicates its root; transmitted readings differ on whether it is 一 or 丅.",
         "evidence_ids": ["source:1"]}]
    article["meaning_history"]["senses"][0].update(
        id="本:root", gloss="plant root", status="historical", certainty="probable",
        text="本 refers to the root of a plant.")
    article["relationships"] = [
        {"id": "meaning", "subject": {"kind": "character", "id": "本"},
         "object": {"kind": "sense", "id": "本:root"}, "predicate": "has_sense",
         "context_character": "本", "certainty": "probable", "text": "本 refers to the plant root.",
         "evidence_ids": ["source:1"]},
        {"id": "tree-picture", "subject": {"kind": "component", "id": "木"},
         "object": {"kind": "character", "id": "本"}, "predicate": "pictorial_component_of",
         "context_character": "本", "certainty": "established", "text": "木 depicts the tree.",
         "evidence_ids": ["source:1"]},
        {"id": "root-indicator", "subject": {"kind": "component", "id": "本:mark:lower-1"},
         "object": {"kind": "character", "id": "本"}, "predicate": "indicator_component_of",
         "context_character": "本", "certainty": "established",
         "text": "The lower mark indicates the root.", "evidence_ids": ["source:1"]}]
    article["learner"] = {"overview": {"text": "木 depicts a tree, and the lower mark points to its root.",
                                        "evidence_ids": ["source:1"]},
        "components": [{"component_index": 0, "text": "木 depicts the tree.", "evidence_ids": ["source:1"]},
                       {"component_index": 1, "text": "The lower mark points to the root.", "evidence_ids": ["source:1"]}],
        "takeaway": None}
    return article, dossier


class ComponentScopeTests(unittest.TestCase):
    def test_prompts_keep_visible_identity_separate_from_glyph_interpretation(self):
        policy = " ".join(V2_POLICY.split())
        self.assertIn("visible noncharacter mark", policy)
        self.assertIn("element_kind noncharacter_mark", policy)
        self.assertIn("unread OCR graph", policy)
        self.assertIn('relationship endpoint stays exactly {"kind":"component","id":element_id}', policy)
        self.assertIn("Do not automatically match words", REVIEW_V2_POLICY)
        self.assertIn("Reject invented readings or phonetic roles", REVIEW_V2_POLICY)

    def test_sourced_noncharacter_mark_has_scoped_opaque_identity(self):
        article, dossier = noncharacter_mark_fixture()
        validate_article(article, dossier)
        self.assertEqual(article["components"][0]["form"], "木")
        self.assertEqual(article["relationships"][2]["subject"]["id"], "本:mark:lower-1")

    def test_noncharacter_mark_cannot_claim_a_glyph_or_cross_scope_id(self):
        article, dossier = noncharacter_mark_fixture()
        article["components"][1]["form"] = "一"
        with self.assertRaisesRegex(ValueError, "must not claim a literal glyph"):
            validate_article(article, dossier)
        article, dossier = noncharacter_mark_fixture()
        article["components"][1]["element_id"] = "木:mark:lower-1"
        article["relationships"][2]["subject"]["id"] = "木:mark:lower-1"
        with self.assertRaisesRegex(ValueError, "stable <scope>:mark"):
            validate_article(article, dossier)

    def test_noncharacter_mark_does_not_get_guessed_phonetic_reading(self):
        article, dossier = noncharacter_mark_fixture()
        mark = article["components"][1]
        mark["roles"] = ["phonetic"]
        mark["sound_limitation"] = {"text": "The mark's reading is unavailable.", "evidence_ids": ["source:1"]}
        with self.assertRaisesRegex(ValueError, "cannot carry phonetic roles"):
            validate_article(article, dossier)

    def test_shared_historical_graph_has_distinct_character_endpoints(self):
        article, dossier = fixture()
        edge = article['relationships'][1]
        edge['predicate'] = 'shares_historical_graph_with'
        edge['certainty'] = 'disputed'
        validate_article(article, dossier)
        edge['object']['id'] = edge['subject']['id']
        with self.assertRaises(ValueError):
            validate_article(article, dossier)

    def test_checked_in_unihan_hsk1_extract_is_the_fallback(self):
        with patch('pipeline.structured.UNIHAN_READINGS', Path('/missing/Unihan_Readings.txt')):
            self.assertEqual(default_unihan_readings_path(), UNIHAN_HSK1_READINGS)
            pair = {'component_form': '兂', 'component_reading': 'zān',
                    'character_reading': 'ài', 'system': 'Modern Mandarin',
                    'evidence_ids': ['unihan:pair']}
            dossier = {'evidence': [{'id': 'unihan:pair', 'source': 'Unicode Unihan database'}]}
            validate_modern_mandarin_sound(pair, '㤅', dossier)

    def test_modern_mandarin_readings_are_checked_against_unihan_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Unihan_Readings.txt'
            path.write_text('U+5142\tkMandarin\tzān\nU+3905\tkMandarin\tài\n', encoding='utf-8')
            pair = {'component_form': '兂', 'component_reading': 'zān',
                    'character_reading': 'ài', 'system': 'Modern Mandarin',
                    'evidence_ids': ['unihan:pair']}
            dossier = {'evidence': [{'id': 'unihan:pair', 'source': 'Unicode Unihan database'}]}
            validate_modern_mandarin_sound(pair, '㤅', dossier, path)
            pair['character_reading'] = 'yǒng'
            with self.assertRaisesRegex(ValueError, 'does not match local Unihan'):
                validate_modern_mandarin_sound(pair, '㤅', dossier, path)

    def test_mixed_modern_and_historical_sound_pairs_are_split(self):
        pair = {'component_form': '豭', 'component_reading': 'jiā; MC kae; OC *kˤra',
                'character_reading': 'jiā; MC kae; OC *kˤra',
                'system': 'Modern Mandarin; Middle Chinese and Old Chinese, Baxter–Sagart',
                'evidence_ids': ['unihan:pair']}
        dossier = {'evidence': [{'id': 'unihan:pair', 'source': 'Unicode Unihan database'}]}
        with self.assertRaisesRegex(ValueError, 'mixes Modern Mandarin with historical readings'):
            validate_modern_mandarin_sound(pair, '家', dossier)

    def test_historical_host_can_follow_cited_chain_without_inferred_edges(self):
        article, dossier = fixture()
        article['components'][0]['scope_character'] = '㤅'
        article['relationships'][2]['object']['id'] = '㤅'
        edge = copy.deepcopy(article['relationships'][1])
        edge.update(id='earlier-stage', predicate='derived_from')
        edge['subject']['id'], edge['object']['id'] = '愛', '㤅'
        article['relationships'].append(edge)
        before = copy.deepcopy(article)
        validate_article(article, dossier)
        self.assertEqual(article, before)
        article['relationships'][1]['subject']['id'] = '心'
        with self.assertRaisesRegex(ValueError, 'graphic relationship'):
            validate_article(article, dossier)

    def test_historical_host_is_explicit_without_changing_entry_context(self):
        article, dossier = fixture()
        validate_article(article, dossier)
        article['relationships'][2]['context_character'] = '愛'
        with self.assertRaisesRegex(ValueError, 'context differs'):
            validate_article(article, dossier)

    def test_historical_component_cannot_assert_modern_membership(self):
        article, dossier = fixture()
        article['relationships'][2]['object']['id'] = '爱'
        with self.assertRaisesRegex(ValueError, 'host scope'):
            validate_article(article, dossier)

    def test_historical_scope_needs_cited_connection_to_entry(self):
        article, dossier = fixture()
        article['relationships'].pop(1)
        with self.assertRaisesRegex(ValueError, 'graphic relationship'):
            validate_article(article, dossier)

    def test_phonetic_role_in_another_character_is_not_a_graphic_scope(self):
        article, dossier = fixture()
        edge = {
            'id': 'phonetic-use-in-yin',
            'subject': {'kind': 'character', 'id': '爱'},
            'object': {'kind': 'character', 'id': '吟'},
            'predicate': 'phonetic_element_in',
            'context_character': '爱',
            'certainty': 'probable',
            'text': '爱 is independently identified as a phonetic element in 吟.',
            'evidence_ids': ['source:1']}
        article['relationships'].append(edge)
        validate_article(article, dossier)
        reversed_edge = copy.deepcopy(edge)
        reversed_edge['subject']['id'] = '吟'
        reversed_edge['object']['id'] = '爱'
        article['relationships'][-1] = reversed_edge
        with self.assertRaisesRegex(ValueError, 'phonetic_element_in must link this entry'):
            validate_article(article, dossier)

        article, dossier = fixture()
        article['relationships'].append(edge)
        cross_character = copy.deepcopy(article['components'][0])
        cross_character.update(scope_character='吟', roles=['unknown'])
        article['components'].append(cross_character)
        with self.assertRaisesRegex(ValueError, 'not a graphic scope.*remove the cross-character component'):
            validate_article(article, dossier)

    def test_same_component_in_two_scopes_needs_two_edges(self):
        article, dossier = fixture()
        current = copy.deepcopy(article['components'][0])
        current['scope_character'] = '爱'
        article['components'].append(current)
        with self.assertRaisesRegex(ValueError, 'Every supported component role'):
            validate_article(article, dossier)
        edge = copy.deepcopy(article['relationships'][2])
        edge.update(id='current-component')
        edge['object']['id'] = '爱'
        article['relationships'].append(edge)
        validate_article(article, dossier)

    def test_reviewed_legacy_descriptive_component_forms_remain_valid(self):
        # These are existing approved legacy entries, not synthetic exceptions:
        # 青 groups its lower component descriptively and 武 labels a changed 戈 shape.
        root = Path(__file__).resolve().parents[1]
        for character in ("青", "武"):
            entry = json.loads((root / "content/entries" / f"{ord(character):04X}.json").read_text(encoding="utf-8"))
            with self.subTest(character=character):
                published = validate_published(entry)
                forms = {component["form"] for component in published["components"]}
                if character == "青":
                    self.assertIn("月-shaped lower part", forms)
                else:
                    self.assertIn("戈 (altered)", forms)
                self.assertTrue(all("element_kind" not in component for component in published["components"]))

    def test_legacy_components_keep_entry_scope_and_known_readings(self):
        article = copy.deepcopy(ARTICLE_V2)
        for component in article['components']:
            component.pop('scope_character', None)
            component.pop('sound_limitation', None)
        dossier = {**copy.deepcopy(DOSSIER), 'glyph_research': {'historical_glyphs': GLYPHS}}
        validate_article(article, dossier)

    def test_current_membership_override_is_independent_of_scope(self):
        article, _ = fixture()
        component = article['components'][0]
        self.assertFalse(component_is_current_form(component, article))
        component['current_form_component'] = None
        self.assertFalse(component_is_current_form(component, article))
        component['current_form_component'] = False
        self.assertFalse(component_is_current_form(component, article))
        component['scope_character'] = '爱'
        component['current_form_component'] = True
        self.assertTrue(component_is_current_form(component, article))
        component['current_form_component'] = False
        self.assertFalse(component_is_current_form(component, article))
        component['current_form_component'] = 'yes'
        with self.assertRaisesRegex(ValueError, 'current_form_component'):
            component_is_current_form(component, article)
        component['current_form_component'] = True
        component['scope_character'] = '愛'
        with self.assertRaisesRegex(ValueError, 'scoped to the entry'):
            component_is_current_form(component, article)

    def test_unknown_sound_has_separate_cited_limitation(self):
        article, dossier = fixture()
        article['components'][0].update(roles=['phonetic'], form_status='disputed',
            sound_limitation={'text': 'The proposed phonetic reading is not established.',
                              'evidence_ids': ['source:1']})
        article['relationships'][2].update(predicate='phonetic_component_of', certainty='disputed')
        validate_article(article, dossier)
        article['components'][0]['sound_limitation']['evidence_ids'] = ['missing']
        with self.assertRaises(ValueError):
            validate_article(article, dossier)

    def test_missing_sound_cannot_silently_pass(self):
        article, dossier = fixture()
        article['components'][0]['roles'] = ['phonetic']
        article['relationships'][2].update(predicate='phonetic_component_of', certainty='disputed')
        with self.assertRaisesRegex(ValueError, 'phonetic'):
            validate_article(article, dossier)

    def test_placeholder_is_not_a_reading(self):
        article, dossier = fixture()
        component = article['components'][0]
        component['roles'] = ['phonetic']
        component['sound'] = [{'component_form': '心', 'component_reading': 'not established in this dossier',
            'character_reading': 'ài', 'system': 'Mandarin', 'text': 'Unavailable.',
            'evidence_ids': ['source:1']}]
        article['relationships'][2].update(predicate='phonetic_component_of', certainty='disputed')
        with self.assertRaisesRegex(ValueError, 'placeholders'):
            validate_article(article, dossier)

    def test_sound_comparison_can_coexist_with_distinct_role_limitation(self):
        article, dossier = fixture()
        component = article['components'][0]
        component.update(roles=['phonetic'], sound_limitation={
            'text': 'This comparison alone does not establish that 心 supplies the sound of 爱.',
            'evidence_ids': ['source:1']})
        component['sound'] = [{'component_form': '心', 'component_reading': 'xīn',
            'character_reading': 'ài', 'system': 'Mandarin', 'text': 'Fixture comparison.',
            'evidence_ids': ['source:1']}]
        article['relationships'][2].update(predicate='phonetic_component_of', certainty='disputed')
        validate_article(article, dossier)


if __name__ == '__main__':
    unittest.main()
