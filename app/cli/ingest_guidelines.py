"""Adds a guideline document (PDF, TXT, MD, DOCX, or XLSX) to the asc_guidelines collection.

Usage:
    uv run ingest_guidelines.py "path\\to\\ASC Guidebook.pdf"            add a PDF
    uv run ingest_guidelines.py "path\\to\\ASC Guidebook.pdf" --replace  replace an earlier copy of the same file

This does the same as the "PDF form -> Qdrant Vector Store" branch of the n8n workflow, and stores
passages in the same format, so passages added here and by n8n can be searched together.
"""

import sys
from pathlib import Path
from app.features.documents.service import ingest_document, read_upload


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    path = Path(args[0])
    try:
        with path.open("rb") as file:
            data = read_upload(file)
        def confirm():
            return input("The collection already has passages. Adding the same content under another filename creates duplicates. Continue? [y/N] ").strip().lower() == "y"
        for item in ingest_document(data, path.name, replace="--replace" in sys.argv, confirm_add=confirm):
            if item["type"] == "duplicate":
                sys.exit(item["message"] + " Add --replace to replace it.")
            print(item)
    except Exception as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
