"""Deterministic prompt compaction; source text and observations stay verbatim."""
import json
import re


def compact_instructions(text):
    """Remove decorative banners and empty lines, retaining every instruction line."""
    return "\n".join(line.rstrip() for line in text.splitlines()
                     if line.strip() and not re.fullmatch(r"[=]{3,}", line.strip()))


def unique_references(sources):
    """Remove only byte-identical reference blocks (authority/location included)."""
    return list(dict.fromkeys(sources))


def audit_payload(result, description, sources, rules):
    proposed = dict(result)
    for key in ('description', 'description_en'):
        if proposed.get(key) == description:
            del proposed[key]
    return {'observations': description, 'proposed_result': proposed,
            'applicable_rule_summaries': rules, 'retrieved_passages': unique_references(sources)}


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
