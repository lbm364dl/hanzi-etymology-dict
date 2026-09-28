"""Validate or publish the complete checked-in editorial pilot."""
import argparse
import json
from pipeline.dossiers import PILOT, ROOT
from pipeline.editorial import publish, validate_reviews


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "publish"])
    args = parser.parse_args()
    records = []
    for character in PILOT:
        name = f"{ord(character):04X}.json"
        dossier = json.loads((ROOT / "content/dossiers" / name).read_text())
        article = json.loads((ROOT / "content/drafts" / name).read_text())
        reviews = json.loads((ROOT / "content/reviews" / name).read_text())
        validate_reviews(article, dossier, reviews)
        records.append((article, dossier, reviews))
    # Every receipt has been checked before changing any published entry.
    if args.action == "publish":
        for record in records:
            publish(*record)
    print(f"{len(records)} entries: articles, citations, and both review receipts valid")


if __name__ == "__main__":
    main()
