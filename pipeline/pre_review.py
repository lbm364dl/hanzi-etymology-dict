"""Deterministic article checks to run before spending an independent review call.

This module deliberately delegates the substantive article contract to the existing
editorial validators. It checks only schema, citation references, learner-card index
coverage and consistency already encoded in that contract; it does not infer glyph
identity, decomposition, sound roles, historical meaning or prose quality.
"""
from __future__ import annotations

from jsonschema import Draft202012Validator

from pipeline import editorial


def _path(parts):
    return "/".join(str(part) for part in parts)


def _article_sections(value, path=()):
    """Yield cited article sections with their JSON paths, including glyph captions."""
    if isinstance(value, dict):
        evidence_ids = value.get("evidence_ids")
        text = value.get("text", value.get("caption"))
        if isinstance(text, str) and isinstance(evidence_ids, list):
            yield _path(path), {"text": text, "evidence_ids": evidence_ids}
        for key, child in value.items():
            if key != "evidence_ids":
                yield from _article_sections(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _article_sections(child, (*path, index))


def _learner_coverage(article):
    learner = article.get("learner")
    if learner is None:
        return None
    components = article.get("components", [])
    cards = learner.get("components", [])
    indices = [card.get("component_index") for card in cards if isinstance(card, dict)]
    required = {
        index for index, component in enumerate(components)
        if editorial.component_is_current_form(component, article)
    }
    errors = []
    if len(indices) != len(set(indices)):
        errors.append("Learner component_index values must be unique")
    valid_indices = {index for index in indices if isinstance(index, int) and not isinstance(index, bool)}
    if valid_indices - set(range(len(components))):
        errors.append("Learner component_index must refer to an existing component")
    missing = sorted(required - valid_indices)
    if missing:
        errors.append(f"Learner cards are missing current-form component indices {missing}")
    return {"required_indices": sorted(required), "card_indices": indices, "errors": errors}


def _derived_relationship_mismatches(article, dossier):
    """Compare stored sense edges with the canonical view of authored sense records."""
    predicates = {"has_sense", "sense_developed_into", "phonetic_loan_for"}
    expected_article = editorial.assemble_article(article, dossier)
    actual = {edge["id"]: edge for edge in article.get("relationships", [])
              if edge.get("predicate") in predicates}
    expected = {edge["id"]: edge for edge in expected_article.get("relationships", [])
                if edge.get("predicate") in predicates}
    return sorted(edge_id for edge_id in actual.keys() | expected.keys()
                  if actual.get(edge_id) != expected.get(edge_id))


def check_pair(article, dossier):
    """Return a JSON-serializable pre-review report for one exact article/dossier pair.

    ``status`` is ``pass`` only when the same full validation used by editorial review
    and publication succeeds. The report hashes bind the returned result to this pair.
    """
    findings = []
    report = {
        "status": "blocked",
        "article_hash": editorial.digest(article),
        "dossier_hash": editorial.digest(dossier),
        "checks": {},
        "findings": findings,
    }

    try:
        schema = editorial.article_schema(article)
        schema_errors = sorted(
            Draft202012Validator(schema).iter_errors(article),
            key=lambda error: (tuple(str(item) for item in error.absolute_path), error.message),
        )
    except (TypeError, KeyError, ValueError) as exc:
        report["checks"]["article_schema"] = "fail"
        findings.append({"code": "article_schema", "path": "", "message": str(exc)})
        return report
    if schema_errors:
        report["checks"]["article_schema"] = "fail"
        findings.extend({"code": "article_schema", "path": _path(error.absolute_path),
                         "message": error.message} for error in schema_errors)
        return report
    report["checks"]["article_schema"] = "pass"

    try:
        editorial.validate_dossier(dossier)
    except Exception as exc:
        report["checks"]["dossier"] = "fail"
        findings.append({"code": "dossier", "path": "", "message": str(exc)})
        return report
    report["checks"]["dossier"] = "pass"

    try:
        editorial.validate_external_evidence(dossier)
    except Exception as exc:
        report["checks"]["external_evidence"] = "fail"
        findings.append({"code": "external_evidence", "path": "dossier.external_research",
                         "message": str(exc)})
        return report
    report["checks"]["external_evidence"] = "pass"

    citation_errors = []
    for path, section in _article_sections(article):
        try:
            editorial.validate_sections([section], dossier)
        except (ValueError, KeyError, TypeError) as exc:
            citation_errors.append({"code": "citation_integrity", "path": path,
                                    "message": str(exc)})
    report["checks"]["citation_integrity"] = "fail" if citation_errors else "pass"
    findings.extend(citation_errors)

    try:
        coverage = _learner_coverage(article)
    except (KeyError, TypeError, ValueError) as exc:
        coverage = {"errors": [str(exc)]}
    report["checks"]["learner_component_coverage"] = (
        "pass" if coverage is None or not coverage["errors"] else "fail")
    report["learner_component_coverage"] = coverage
    if coverage:
        findings.extend({"code": "learner_component_coverage", "path": "learner/components",
                         "message": message} for message in coverage["errors"])

    if article.get("schema_version") == 2:
        try:
            mismatches = _derived_relationship_mismatches(article, dossier)
        except (KeyError, TypeError, ValueError) as exc:
            mismatches = None
            findings.append({"code": "sense_relationship_consistency", "path": "relationships",
                             "message": f"Could not verify generated sense relationships: {exc}"})
        if mismatches:
            findings.append({"code": "sense_relationship_consistency", "path": "relationships",
                             "message": "Generated meaning relationships do not exactly match "
                                        "meaning_history senses/developments: " + ", ".join(mismatches)})
        report["checks"]["sense_relationship_consistency"] = (
            "fail" if mismatches or mismatches is None else "pass")

    if findings:
        return report

    try:
        editorial.validate_article(article, dossier)
    except Exception as exc:
        message = str(exc)
        code = ("sense_relationship_consistency" if
                any(term in message.casefold() for term in ("sense", "meaning edge", "has_sense"))
                else "article_contract")
        report["checks"]["editorial_contract"] = "fail"
        findings.append({"code": code, "path": "", "message": message})
        return report

    report["checks"]["editorial_contract"] = "pass"
    report["status"] = "pass"
    return report
