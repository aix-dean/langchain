import sys  # Standard library module for reading command-line arguments
from pathlib import Path  # Standard library module for working with file paths

from app.core.config import IMAGE_TYPES  # Accepted image types
from app.features.ad_review.service import check_image  # The whole check


def main():  # Checks one image from the command line: uv run check.py path\to\ad.jpg
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # The Windows console can't show some characters the AI writes (e.g. special dashes); don't crash on them
    if len(sys.argv) != 2:  # Wrong usage
        sys.exit("Usage: uv run check.py <image.jpg | image.png>")  # Explain
    path = Path(sys.argv[1])  # The image file
    if path.suffix.lower() not in IMAGE_TYPES:  # Not a supported image
        sys.exit(f"Unsupported file type '{path.suffix}'. Use {', '.join(IMAGE_TYPES)}.")  # Explain
    if not path.is_file():  # The file doesn't exist
        sys.exit(f"File not found: {path}")  # Explain

    peak = 0  # Most of the judge's memory used (in tokens)
    for kind, data in check_image(path.read_bytes()):  # Run the check
        if kind == "tokens":  # How full the judge's memory is
            peak = max(peak, data)  # Keep the highest
        elif kind == "stage":  # A new step
            print({"describe": "\n== Step 1: describing the image ==", "judge": "\n\n== Step 2: checking against the ASC rules ==", "verify": "\n== Step 3: verifying the findings =="}[data])  # Step title
        elif kind == "describe":  # Part of the description
            print(data, end="", flush=True)  # Show it as it arrives
        elif kind == "search":  # A guideline search
            print(f"  searched guidelines: \"{data['query']}\"")  # Show the query
        elif kind == "result":  # The final result
            show(data)  # Print it
    print(f"(Judge memory used: {peak:,} tokens)")  # Should stay below JUDGE_NUM_CTX


def show(r):  # Prints the final result
    print(f"\nRESULT: {r['result']}  ({r.get('seconds', '?')} s)")  # The verdict
    if r["result"] in {"ERROR", "NEEDS_REVIEW"}:
        print(r["message"])  # Why
    for i, reason in enumerate(r.get("reasons", []), start=1):  # Each violation
        info = reason.get("info", {})  # The rule explanation
        print(f"\n{i}. {reason.get('problem')}")  # What's wrong
        if info.get("title"):  # A known rule
            print(f"   ASC rule: {info['id']} · {info['title']} – {info['summary']}")  # What the rule says
        if info.get("why"):  # Why it applies here
            print(f"   Why it applies: {info['why']}")  # The AI's explanation
        print(f"   Evidence: {reason.get('evidence')}")  # Proof from the ad
        print(f"   How to fix: {reason.get('suggestion')}")  # The fix
    if r["result"] == "COMPLIANT":  # Passed
        print(r.get("approval_summary", ""))  # Why
        for c in r.get("checks_passed", []):  # Each check made
            print(f"  ✓ {c['check']}: {c['finding']}")  # What was found
    if r.get("removed_reasons"):  # Made-up violations that were removed
        print("\nRemoved as not backed by the image:", "; ".join(r["removed_reasons"]))  # List them
    print("\nThis is an AI pre-screen, not an ASC decision. A person must review it.")  # Reminder


if __name__ == "__main__":  # Only run when this file is executed directly
    main()  # Start
