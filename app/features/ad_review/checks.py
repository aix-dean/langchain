"""Step 3: turns the judge's answer into a clean, trustworthy result.

This is the Python version of the n8n "Code in JavaScript" node. It removes "violations" the judge
made up (rules from another product category, "missing" statements that are actually in the ad,
evidence that isn't in the description), routes uncertainty to review, and attaches a
plain-language explanation of every rule.
"""

import json  # Standard library module for reading JSON
import re  # Standard library module for finding patterns in text

from app.core.config import PROMPTS  # Folder with the rule summaries

RULE_INFO = json.loads((PROMPTS / "rules.json").read_text(encoding="utf-8"))  # Rule ID -> [short title, plain-language summary] (ASC Guidebook, March 2019)
MANDATORY_STATEMENTS = {
    code: match.group(1) for code, info in RULE_INFO.items()
    if (match := re.search(r'must (?:carry|say) "([^"]+)"', info[1], re.I))
    and '[' not in match.group(1)  # Variable statements need contextual verification.
}

CATEGORY_KEYWORDS = {  # Words in the description that show the product category
    "R-ALC": r"\b(beer|pilsen|lager|alcohol|liquor|gin|whisky|whiskey|vodka|rum|brandy|wine|tequila|soju|cocktail)\b",  # Alcohol
    "R-TOB": r"\b(cigarette|cigar|tobacco|vape|vaping|e-cig|heated tobacco)\b",  # Tobacco
    "R-GAM": r"\b(casino|betting|bet|gaming|lotto|sabong|slot|poker|jackpot)\b",  # Gambling
    "R-SUPP": r"\b(food supplement|dietary supplement|herbal supplement|supplement)\b",  # Supplements
    "R-VIT": r"\b(vitamin|multivitamin|mineral)\b",  # Vitamins
    "R-OTC": r"\b(medicine|tablet|capsule|syrup|paracetamol|ibuprofen|pain reliever|antacid|decongestant)\b",  # Non-prescription medicine
    "R-MILK": r"\b(infant|baby formula|infant formula|growing-up milk|feeding bottle|teat|complementary food)\b",  # Milk Code products
    "R-COS": r"\b(cosmetic|lotion|soap|shampoo|conditioner|skin care|skincare|serum|cream|makeup|deodorant|toothpaste)\b",  # Cosmetics
    "R-FIN": r"\b(bank|loan|credit card|insurance|investment|pawnshop|remittance|e-wallet|savings)\b",  # Banks and finance
    "R-RE": r"\b(condo|condominium|house and lot|real estate|subdivision|townhouse|lot for sale)\b",  # Real estate
    "R-TEL": r"\b(telecom|broadband|fiber|prepaid|postpaid|mobile data|load promo)\b",  # Telecom
    "R-AIR": r"\b(airline|airfare|seat sale|flight)\b",  # Airlines
}  # End of categories

RULE_TEXT_CATEGORY = [  # Words in a reason that show which category's rule it uses (when it has no R- code)
    ("R-ALC", r"alcohol|drink responsibly"),  # Alcohol
    ("R-MILK", r"milk|infant|breast ?milk|teat|feeding bottle"),  # Milk Code
    ("R-TOB", r"tobacco|cigarette|smok"),  # Tobacco
    ("R-GAM", r"gaming|gambl|game responsibly|pagcor"),  # Gambling
    ("R-FIN", r"bank|financial|bangko sentral|\bbsp\b"),  # Finance
    ("R-SUPP", r"supplement|mahalagang paalala"),  # Supplements
    ("R-VIT", r"vitamin"),  # Vitamins
    ("R-COS", r"cosmetic"),  # Cosmetics
    ("R-OTC", r"non-prescription|over-the-counter|\botc\b|symptoms persist|generic name"),  # OTC medicine
    ("R-RE", r"housing|real estate|hlurb|dhsud|license to sell"),  # Real estate
    ("R-TEL", r"telecom|broadband|\bntc\b"),  # Telecom
    ("R-AIR", r"airline|\bcab\b"),  # Airlines
]  # End of list

DECENCY_RULE = (  # The rule reference used for decency problems added by this code
    "Article I, Section 4 (Sex, Profanity, Obscenity & Vulgarity) and Manual of Procedures Annex 3 "  # Code of Ethics section
    "(Exposure of Human Body / Sexy Tones)"  # Manual annex
)  # End of reference
DECENCY_CHECKS = [  # Decency backup (ASC Code Art. I Sec. 4; Manual Annex 3): borderline decency is NON-COMPLIANT
    {  # Intimate contact
        "re": r"\b(kiss(es|ing)?|about to kiss|embrac\w*|caress\w*|cuddl\w*|intimate|sensual|seductive|straddl\w*|foreheads? (are )?touching|bodies (are )?pressed|(hands?|arms?) (\w+ ){0,3}(around|on) (\w+ ){0,3}(waist|hips?|thighs?))\b",  # Words that show it
        "problem": "Intimate or suggestive physical contact between models is not allowed in OOH ads, which must be wholesome for all ages.",  # What's wrong
        "suggestion": "Use a less intimate pose, e.g. the models standing side by side, holding hands, or laughing together, with no kissing or embracing.",  # How to fix
    },  # End of check
    {  # Revealing clothing
        "re": r"\b(shirtless|topless|bare[- ]chested|bikini|swimsuit|swimwear|swim ?(trunks|briefs)|briefs|thong|lingerie|underwear|bra|cleavage|see-through|sheer|nude|naked|nudity|revealing)\b",  # Words that show it
        "problem": "Skimpy or revealing clothing / body exposure is not allowed in OOH ads seen by the general public.",  # What's wrong
        "suggestion": "Dress the models in fuller clothing (e.g. rash guard, board shorts, a cover-up or shirt) or crop the image to faces and shoulders.",  # How to fix
    },  # End of check
]  # End of decency checks


def words(text):  # Splits text into lowercase words longer than 2 letters
    return [w for w in re.sub(r"[^\w\s]|_", " ", str(text or "").lower()).split() if len(w) > 2]  # Punctuation removed


def not_english(text):  # True if the text is mostly Chinese, Japanese or Korean (vision models sometimes switch language)
    cjk = len(re.findall(r"[぀-ヿ㐀-鿿가-힯]", str(text)))  # Count of those characters
    letters = len(re.sub(r"\s", "", str(text))) or 1  # All non-space characters
    return cjk > 20 and cjk / letters > 0.1  # Many of them, and a real share of the text


def parse_answer(raw):  # Pulls the JSON object out of the judge's answer
    text = raw.replace("```json", "").replace("```", "")  # Remove Markdown code fences
    match = re.search(r"\{[\s\S]*\}", text)  # From the first "{" to the last "}"
    return json.loads(match.group(0)) if match else None  # The parsed answer, or None


def rule_id(reason):  # Finds the rule ID in a reason, e.g. "C-07 (Art. V Sec. 6)" -> "C-07"
    text = str(reason.get("rule", ""))  # The rule reference
    found = re.search(r"\b([GCP]-\d{2}|R-[A-Z]+)\b", text.upper())  # An ID like G-04, C-07 or R-ALC
    if found and found.group(1) in RULE_INFO:  # A known rule
        return found.group(1)  # Use it
    if re.search(r"\bD[1-6]\b|annex 3|section 4|decency|sexy tones|obscen", text, re.I):  # Decency wording
        return "G-04"  # The decency rule
    return found.group(1) if found else ""  # Unknown ID, or none


def rule_info(reason):  # Plain-language explanation of a reason's rule
    rid = rule_id(reason)  # Its rule ID
    known = RULE_INFO.get(rid)  # The built-in summary (always accurate), if any
    return {  # Title, summary and why it applies
        "id": rid,  # e.g. "C-07"
        "title": known[0] if known else str(reason.get("rule_title", "")).strip(),  # Built-in title first; the AI's as backup
        "summary": known[1] if known else str(reason.get("rule_summary", "")).strip(),  # Built-in summary first; the AI's as backup
        "why": str(reason.get("why_it_applies", "")).strip(),  # The AI's sentence linking the rule to this ad
    }  # End of info


def rule_category(reason):  # Which product category a reason's rule belongs to (None for general rules)
    code = re.search(r"\bR-[A-Z]+", str(reason.get("rule", "")).upper())  # An explicit category code
    if code:  # Found one
        return code.group(0)  # Use it
    for text in (reason.get("rule"), f"{reason.get('evidence')} {reason.get('problem')}"):  # Then the rule name, then the reason's own words
        for category, pattern in RULE_TEXT_CATEGORY:  # Each category
            if re.search(pattern, str(text or ""), re.I):  # Its words appear
                return category  # That's the category
    return None  # A general rule


def error_result(message):  # A result for when the image could not be checked
    return {"result": "ERROR", "message": message, "reasons": [], "checks_passed": []}  # Shown as "Could not check"


def normalized(text):
    return ' '.join(re.sub(r'[^\w\s]', ' ', str(text).casefold()).split())


def image_sections(description):
    return {m[1]: m[2].strip() for m in re.finditer(
        r'(?ms)^\s*([1-7])\.\s*[^:\n]+:\s*(.*?)(?=^\s*[1-7]\.\s|\Z)', description)}


def quoted_evidence(evidence, description):
    text = normalized(evidence)
    return len(text) >= 8 and text in normalized(description)


def positive_decency_hits(description, pattern):
    hits = []
    for sentence in re.split(r'(?<=[.!?;])\s+|\n+', description):
        for match in re.finditer(pattern, sentence, re.I):
            before = sentence[max(0, match.start()-65):match.start()]
            # Negated observations and explicit absence are not positive evidence.
            if re.search(r'\b(no|not|never|without|none|neither|nor)\b[^.!?;]*$', before, re.I):
                continue
            after = sentence[match.end():match.end()+45]
            if re.match(r'\s+(?:is|are|was|were)?\s*(?:not\s+(?:shown|present|visible)|absent|noted as absent)\b', after, re.I):
                continue
            hits.append(sentence.strip())
    return list(dict.fromkeys(hits))[:2]


def finalize(raw, description):  # Step 3: turns the judge's raw answer into the final, checked result
    try:  # The answer may not be valid JSON
        data = parse_answer(raw)  # The judge's JSON
    except json.JSONDecodeError:  # Broken JSON
        data = None  # Treat as missing
    if not isinstance(data, dict):  # Nothing usable
        detail = f"The AI did not return valid JSON:\n\n{raw}" if raw.strip() else "The AI returned an EMPTY answer."  # What happened
        return error_result(detail)  # Could not check

    verdict = str(data.get("verdict") or data.get("result") or "").upper()
    if "error" in verdict.lower():  # The judge said it got no description
        return error_result("The AI did not receive the ad description.")  # Could not check
    if verdict not in {'COMPLIANT', 'NON-COMPLIANT', 'NEEDS_REVIEW'}:
        return error_result('The AI returned an unrecognized verdict; no approval was issued.')
    if not isinstance(data.get('reasons'), list) or any(not isinstance(r, dict) for r in data['reasons']):
        return error_result('The AI returned invalid findings; no approval was issued.')
    if 'review_issues' in data and not isinstance(data['review_issues'], list):
        return error_result('The AI returned invalid review issues; no approval was issued.')
    if not description.strip():
        return error_result('No image evidence was available; no approval was issued.')

    description_from = "vision model"  # Where the description we check against came from
    translated = str(data.get("description_en") or "").strip()  # The judge's English translation, if any
    if not_english(description) and translated and not not_english(translated):  # The vision model answered in another language
        description, description_from = translated, "vision model (translated by the judge)"  # Use the translation
    if not_english(description):  # Still not English
        return error_result("The image description came back in another language, so it could not be checked reliably. Please submit the image again.")  # Stop

    sections = image_sections(description)
    product_evidence = sections.get('2', description)
    detected = {c for c, pattern in CATEGORY_KEYWORDS.items() if re.search(pattern, product_evidence, re.I)}
    review_issues = []
    if set(sections) != set('1234567'):
        review_issues.append('The image description is incomplete; all seven observation sections are required.')
    unreadable = sections.get('7', '').strip()
    if unreadable and normalized(unreadable) not in {'none', 'none found', 'no unreadable text', 'no unreadable text found'}:
        review_issues.append('Some image text could not be read reliably. Confirm it from a clearer image before approval.')
    if data.get('review_issues'):
        issues = data['review_issues']
        if isinstance(issues, list):
            review_issues.extend(str(issue) for issue in issues if str(issue).strip())

    def check(reason):  # Keeps a reason only if the description backs it up; returns "ok" or why it was removed
        if not description:  # Nothing to compare with
            return "ok"  # Keep it
        evidence = str(reason.get("evidence", "")).strip()  # The quoted evidence
        problem = str(reason.get("problem", "")).strip()  # The problem statement
        if not rule_id(reason) or rule_id(reason) not in RULE_INFO:
            return 'rule is not in the verified ASC checklist'
        if rule_id(reason) == 'G-04':
            for definition in DECENCY_CHECKS:
                if re.search(definition['re'], evidence + ' ' + problem, re.I) and not positive_decency_hits(
                        sections.get('5', '') + '\n' + sections.get('6', ''), definition['re']):
                    return 'decency finding is not supported by a positive visual observation'
        if not problem or not str(reason.get('suggestion', '')).strip():
            return 'finding is incomplete'
        missing = evidence if re.match(r"missing\b", evidence, re.I) else (problem if re.match(r"missing\b", problem, re.I) else None)  # A "MISSING: ..." claim
        category = rule_category(reason)  # The rule's product category
        if category and category not in detected and (detected or missing):  # A rule from a category this ad isn't in
            return "product category not in ad"  # Made up
        if missing:  # "This required statement is missing"
            statement = missing.split(":", 1)[1] if ":" in missing else ""  # The statement it says is missing
            if not statement.strip():
                return 'missing-statement claim does not identify the statement'
            expected = MANDATORY_STATEMENTS.get(rule_id(reason))
            if not expected or normalized(statement) != normalized(expected):
                return 'mandatory wording could not be verified against the rule'
            if not sections.get('1') or normalized(sections.get('7', '')) not in {'none', 'none found', 'no unreadable text', 'no unreadable text found'}:
                return 'absence cannot be verified from incomplete or unreadable image text'
            if normalized(statement) in normalized(sections['1']):
                return "statement is actually present"  # Made up
            if normalized(statement) in normalized(sections.get('4', '')):
                return 'statement appears in warning observations but was not transcribed consistently'
            return "ok"  # Really missing
        if not words(evidence):  # No evidence at all
            return "no evidence"  # Can't be trusted
        return 'ok' if quoted_evidence(evidence, description) else 'evidence is not an exact image-observation quote'

    all_reasons = data.get("reasons") if isinstance(data.get("reasons"), list) else []  # The judge's violations
    checked = [(r, check(r)) for r in all_reasons if isinstance(r, dict)]  # Each with its check result
    reasons = [r for r, why in checked if why == "ok"]  # The ones that hold up
    removed = [f"{r.get('rule')}: {why}" for r, why in checked if why != "ok"]  # The ones removed, with why

    decency_added = []  # Keyword signals request review, never manufacture violations.
    for check_definition in DECENCY_CHECKS:
        hits = positive_decency_hits(sections.get('5', '') + '\n' + sections.get('6', ''), check_definition['re'])
        already = any(rule_id(r) == 'G-04' and re.search(check_definition['re'], str(r.get('evidence', '')), re.I) for r in reasons)
        if hits and not already:
            review_issues.append('Possible decency concern needs contextual review: ' + ' / '.join(hits))
    if removed:
        review_issues.append('Some proposed findings could not be verified. Removing them does not establish compliance.')
    if verdict == 'NON-COMPLIANT' and not reasons:
        review_issues.append('The judge rejected the ad, but no supported violation remained after verification.')
    if verdict == 'NEEDS_REVIEW':
        review_issues.append(str(data.get('message') or 'The judge could not establish a reliable verdict.'))
    if not sections.get('2') or re.search(r'\b(unknown|uncertain|unidentified|unreadable)\b', sections.get('2', ''), re.I):
        review_issues.append('The product category could not be established reliably.')
    selected_category = str(data.get('category_rule') or '').upper()
    if not selected_category or (selected_category != 'NONE' and selected_category not in detected) or (selected_category == 'NONE' and detected):
        review_issues.append('The selected category does not match the observed product.')
    required_statement = MANDATORY_STATEMENTS.get(selected_category)
    if required_statement and normalized(required_statement) not in normalized(sections.get('1', '')):
        review_issues.append('The mandatory statement for the selected category was not verified in the transcribed ad text.')

    approval_summary, checks_passed = '', []
    if verdict == 'COMPLIANT' and not reasons:
        candidate_checks = data.get('checks_passed')
        if not isinstance(candidate_checks, list):
            candidate_checks = []
        for item in candidate_checks:
            if not isinstance(item, dict):
                continue
            if (all(str(item.get(field) or '').strip() for field in ('check', 'guideline', 'finding', 'evidence'))
                    and quoted_evidence(item['evidence'], description)
                    and rule_id({'rule': item['guideline']}) in RULE_INFO):
                checks_passed.append({field: str(item[field]) for field in ('check','guideline','finding','evidence')})
        ids = {rule_id({'rule': item['guideline']}) for item in checks_passed}
        claim_text = sections.get('3', '')
        if normalized(claim_text) not in {'', 'none', 'none found', 'no claims', 'no claims found'}:
            claim_quotes = re.findall(r'["“]([^"”]+)["”]', claim_text)
            claims = claim_quotes or [line.strip() for line in claim_text.splitlines() if line.strip()]
            if any(not any(normalized(claim) in normalized(item['evidence']) for item in checks_passed) for claim in claims):
                review_issues.append('One or more observed claims lack an evidence-backed passing check.')
        if (len({normalized(item['check']) for item in checks_passed}) < 4
                or len(checks_passed) != len(candidate_checks)
                or 'G-04' not in ids
                or not any(code.startswith('G-') and code != 'G-04' for code in ids)
                or (selected_category in detected and selected_category not in ids)):
            review_issues.append('Approval lacks complete evidence-backed category, general-standard, and decency checks.')
        approval_summary = str(data.get('approval_summary') or '').strip()
        if not approval_summary:
            review_issues.append('The judge did not provide a supported approval summary.')
    result = 'NON-COMPLIANT' if reasons else ('NEEDS_REVIEW' if review_issues else 'COMPLIANT')
    if result != 'COMPLIANT':
        approval_summary = ''
        checks_passed = []

    for r in reasons:  # Attach the plain-language rule explanation to every violation
        r["info"] = rule_info(r)  # id, title, summary, why it applies

    return {  # The final result
        "result": result,
        "message": " ".join(dict.fromkeys(review_issues)) if result == "NEEDS_REVIEW" else "",
        "review_issues": list(dict.fromkeys(review_issues)),
        "reasons": reasons,  # The violations that hold up
        "approval_summary": approval_summary,  # Why it passed (compliant only)
        "checks_passed": checks_passed,  # What was checked (compliant only)
        "detected_category": sorted(detected),  # Product categories found in the description
        "removed_reasons": removed,  # Violations removed as made up, with why
        "decency_added_by_code": decency_added,  # Decency problems this code added
        "description_from": description_from,  # Which description was used
        "category_rule": data.get("category_rule"),  # The judge's own category choice
    }  # End of result
