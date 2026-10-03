"""Independent, occurrence-bound scan checks; never edits OCR or certifies a page."""
from pathlib import Path

from pipeline import editorial


OCCURRENCE = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "raw_text", "printed_text", "verdict", "reason"],
    "properties": {
        "id": {"type": "string"}, "raw_text": {"type": "string"},
        "printed_text": {"type": ["string", "null"]},
        "verdict": {"enum": ["correct_raw", "confirmed_correction", "unresolved_identity"]},
        "reason": {"type": "string", "minLength": 1},
    },
}


def packet(text, proposals):
    """Bind proposed replacements to exact offsets, anchors and visible context."""
    result = []
    seen = set()
    for proposal in proposals:
        identity, start, end = proposal["id"], proposal["start"], proposal["end"]
        if identity in seen or not identity:
            raise ValueError("OCR occurrence IDs must be unique and nonempty")
        seen.add(identity)
        if (type(start) is not int or type(end) is not int
                or not 0 <= start < end <= len(text)):
            raise ValueError("Invalid OCR span")
        before = proposal["before"]
        if text[start:end] != before:
            raise ValueError("OCR proposal does not match its exact raw span")
        result.append({**proposal, "context_before": text[max(0, start - 40):start],
                       "context_after": text[end:end + 40]})
    if not result:
        raise ValueError("OCR verification requires at least one occurrence")
    return result


def validate_result(result, occurrences):
    """Reject missing/duplicate spans and internally inconsistent visual verdicts."""
    expected = {item["id"]: item for item in occurrences}
    records = result.get("occurrences", [])
    identities = [item["id"] for item in records]
    if len(identities) != len(set(identities)) or set(identities) != set(expected):
        raise ValueError("OCR verification must cover each requested occurrence exactly once")
    for item in records:
        proposal = expected[item["id"]]
        if item["raw_text"] != proposal["before"]:
            raise ValueError("OCR verifier mapped the occurrence to different raw text")
        printed, verdict = item["printed_text"], item["verdict"]
        if verdict == "correct_raw" and printed != proposal["before"]:
            raise ValueError("correct_raw verdict contradicts exact raw text")
        if verdict == "confirmed_correction" and (
                not printed or printed != proposal.get("after") or printed == proposal["before"]):
            raise ValueError("Confirmed correction must establish the proposed literal replacement")
        if verdict == "unresolved_identity" and printed is not None:
            raise ValueError("Unresolved printed identity must not guess Unicode text")
    return result


def verify(text, proposals, scans, provenance, runner, output):
    """Run genuine Luna low visual review with bounded transport repair attempts."""
    if runner.model != "gpt-6-luna" or runner.reasoning != "low":
        raise ValueError("OCR verification requires gpt-6-luna with low reasoning")
    if not scans:
        raise ValueError("OCR verification requires original source scan attachments")
    occurrences = packet(text, proposals)
    schema = {"type": "object", "additionalProperties": False, "required": ["occurrences"],
              "properties": {"occurrences": {"type": "array", "items": OCCURRENCE,
                  "minItems": len(occurrences), "maxItems": len(occurrences)}}}
    inputs = {"occurrences": occurrences, "provenance": provenance,
              "feedback": {"source_scan_images": scans},
              "instruction": "Offsets refer to the supplied exact raw text, not visual reading order. Use each ID and its before/after context to find the printed occurrence. Inspect pixels and neighboring controls. Describe the discriminating visible geometry before identifying the character: closed versus open outlines, actual joins, inner bars, and endpoints. Shared upper components or a plausible familiar word do not settle a differing lower component. Check every character in a multi-character span independently; preserve the printed simplified/traditional mixture and do not normalize an otherwise correct adjacent character. A proposed replacement is only a hypothesis; reject it when the original OCR matches the scan. Prior verdicts do not establish what the pixels show. If named controls or proposed Unicode identities bias a conflicting review, use separately prepared source-raster controls in a blind visual comparison before mapping its result to character identities; do not claim a blind comparison occurred unless its actual attachments and genuine review receipt are retained. Return unresolved_identity with null printed_text if the replacement cannot be established."}
    output = Path(output)
    editorial.write(output / "occurrences.json", {"provenance": provenance, "occurrences": occurrences})
    for attempt in range(3):
        directory = output / ("review" if not attempt else f"review-repair-{attempt}")
        result = runner.run("ocr_verification", inputs, schema, directory)
        try:
            validate_result(result, occurrences)
        except ValueError as exc:
            editorial.write(directory / "validation.json", {"valid": False, "error": str(exc)})
            inputs = {**inputs, "transport_error": str(exc), "previous_result": result}
            if attempt == 2:
                raise
        else:
            record = {"provenance": provenance, "occurrences_hash": editorial.digest(occurrences),
                      "result": result, "result_hash": editorial.digest(result),
                      "review_directory": str(directory), "model": runner.model,
                      "reasoning": runner.reasoning, "whole_page_reviewed": False}
            editorial.write(output / "verified-occurrences.json", record)
            return record
