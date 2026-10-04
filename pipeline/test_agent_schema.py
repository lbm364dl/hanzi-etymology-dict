import unittest
from jsonschema import Draft202012Validator, ValidationError
from pipeline.editorial import (agent_schema, ARTICLE_V2_SCHEMA, WRITER_SCHEMA, LEARNER, FORM_ANNOTATION_SCHEMA, REVISION_PLAN_SCHEMA, RESEARCH_SCHEMA,
    GLYPH_RESEARCH_SCHEMA, GLYPH_VISUAL_SCHEMA, ANALYSIS_SCHEMA, REVIEW_SCHEMA,
    DEFAULT_COMMAND, citation_transport, restore_citations)


class AgentSchemaTests(unittest.TestCase):
    def test_citation_aliases_round_trip_without_guessing(self):
        inputs = {"dossier": {"evidence": [{"id": "X-long-stable-id", "text": "A claim", "source": "fixture", "record_character": "木"}]},
                  "analysis": {"evidence_ids": ["X-long-stable-id"]}}
        aliased, reverse = citation_transport(inputs)
        self.assertEqual(aliased["dossier"]["evidence"][0]["id"], "ref001")
        self.assertEqual(restore_citations({"evidence_ids": ["ref001", "invented"]}, reverse),
                         {"evidence_ids": ["X-long-stable-id", "invented"]})
        self.assertEqual(inputs["analysis"]["evidence_ids"], ["X-long-stable-id"])

    def test_transport_omits_unsupported_keyword_but_local_schema_keeps_it(self):
        source = {'type': 'array', 'uniqueItems': True, 'items': {'type': 'string'}}
        wire = agent_schema(source)
        self.assertNotIn('uniqueItems', wire)
        Draft202012Validator(wire).validate(['same', 'same'])
        with self.assertRaises(ValidationError):
            Draft202012Validator(source).validate(['same', 'same'])

    def test_internal_article_schema_preserves_optional_learner_compatibility(self):
        self.assertIn("learner", ARTICLE_V2_SCHEMA["properties"])
        self.assertNotIn("learner", ARTICLE_V2_SCHEMA["required"])
        self.assertIn("learner", WRITER_SCHEMA["required"])

    def test_current_membership_is_optional_in_storage_and_nullable_in_strict_writer(self):
        component = ARTICLE_V2_SCHEMA['properties']['components']['items']
        self.assertNotIn('current_form_component', component['required'])
        self.assertIn('current_form_component', component['properties'])
        wire = agent_schema(WRITER_SCHEMA)['properties']['components']['items']
        self.assertIn('current_form_component', wire['required'])
        Draft202012Validator(wire).validate({
            'form': '木', 'origin_form': '', 'roles': ['pictorial'], 'form_status': 'preserved',
            'text': 'Whole graph.', 'evidence_ids': ['ref001'], 'origin_relation': 'none',
            'scope_character': '木', 'sound_limitation': None, 'sound': [],
            'element_kind': 'glyph', 'element_id': '', 'element_label': '',
            'current_form_component': None})

    def test_writer_schema_accepts_typed_noncharacter_mark_contract(self):
        wire = agent_schema(WRITER_SCHEMA)['properties']['components']['items']
        Draft202012Validator(wire).validate({
            'form': '', 'origin_form': '', 'roles': ['indicator'], 'form_status': 'disputed',
            'text': 'A short horizontal mark below 木 indicates the root.',
            'evidence_ids': ['ref001'], 'origin_relation': 'none', 'scope_character': '本',
            'sound_limitation': None, 'sound': [], 'current_form_component': True,
            'element_kind': 'noncharacter_mark', 'element_id': '本:mark:lower-1',
            'element_label': 'short horizontal mark'})

    def test_generated_schemas_have_required_properties_and_no_unsupported_uniqueness(self):
        def inspect(schema):
            if isinstance(schema, dict):
                self.assertNotIn('uniqueItems', schema)
                if schema.get('type') == 'object':
                    self.assertEqual(set(schema['required']), set(schema['properties']))
                    self.assertFalse(schema['additionalProperties'])
                for value in schema.values():
                    inspect(value)
            elif isinstance(schema, list):
                for value in schema:
                    inspect(value)
        for schema in (WRITER_SCHEMA, LEARNER, FORM_ANNOTATION_SCHEMA, REVISION_PLAN_SCHEMA, RESEARCH_SCHEMA, GLYPH_RESEARCH_SCHEMA,
                       GLYPH_VISUAL_SCHEMA, ANALYSIS_SCHEMA, REVIEW_SCHEMA):
            inspect(agent_schema(schema))
        self.assertIn('model_reasoning_effort="{reasoning}"', DEFAULT_COMMAND)
        self.assertIn('--search', DEFAULT_COMMAND)
        self.assertEqual(DEFAULT_COMMAND[DEFAULT_COMMAND.index('-s') + 1], 'danger-full-access')
        self.assertIn('approval_policy="never"', DEFAULT_COMMAND)
        self.assertNotIn('--ignore-user-config', DEFAULT_COMMAND)


if __name__ == '__main__':
    unittest.main()
