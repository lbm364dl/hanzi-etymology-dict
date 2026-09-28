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


if __name__ == '__main__':
    unittest.main()
