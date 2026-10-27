"""Builds the PDF report of one check: the ad image, the verdict, the findings and the reviewer's decision."""

import io  # Standard library module for keeping files in memory
from datetime import datetime  # Standard library module for the report date
from pathlib import Path  # Standard library module for working with file paths

from fpdf import FPDF  # Library that creates PDF files
from PIL import Image  # Library that reads and resizes images

FONT_DIR = Path("C:/Windows/Fonts")  # Where Windows keeps its fonts
FONTS = {"": "arial.ttf", "B": "arialbd.ttf", "I": "ariali.ttf"}  # Regular, bold and italic Arial
COLORS = {  # (background, text) colors for each verdict
    "NON-COMPLIANT": ((254, 243, 242), (180, 35, 24)),  # Red
    "COMPLIANT": ((236, 253, 243), (6, 118, 71)),  # Green
    "ERROR": ((255, 250, 235), (181, 71, 8)),  # Orange
    "NEEDS_REVIEW": ((255, 250, 235), (181, 71, 8)),
}  # End of colors
LABELS = {"NON-COMPLIANT": "NON-COMPLIANT", "COMPLIANT": "COMPLIANT", "ERROR": "COULD NOT CHECK", "NEEDS_REVIEW": "NEEDS REVIEW"}
TEXT, MUTED, BLUE = (16, 24, 40), (102, 112, 133), (24, 73, 169)  # Main text, grey and blue colors
ASCII = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2011": "-", "\u00a0": " "})  # Fancy punctuation -> plain (only used without Arial)


class Report(FPDF):  # A PDF page layout with our footer
    def footer(self):  # Drawn at the bottom of every page
        self.set_y(-12)  # 12 mm from the bottom
        self.set_font(self.body_font, "", 8)  # Small text
        self.set_text_color(*MUTED)  # Grey
        self.cell(0, 5, f"AI pre-screen, not an ASC decision. A person must review it.   Page {self.page_no()} of {{nb}}", align="C")  # Reminder and page number


def build_report(result, image_bytes, file_name="", decision="", notes=""):  # Returns the PDF report as bytes
    pdf = Report(format="A4")  # A4 paper
    pdf.set_margins(16, 16, 16)  # 16 mm margins
    pdf.set_auto_page_break(True, margin=18)  # Start a new page before the footer
    if all((FONT_DIR / f).exists() for f in FONTS.values()):  # Arial is available (Windows)
        for style, f in FONTS.items():  # Regular, bold, italic
            pdf.add_font("Arial", style, str(FONT_DIR / f))  # Use it, so quotes, dashes and accents print correctly
        pdf.body_font, clean = "Arial", (lambda s: str(s or ""))  # Text can be used as it is
    else:  # Another system: use the built-in font, which only knows basic Western characters
        pdf.body_font = "helvetica"  # Built-in font
        clean = lambda s: str(s or "").translate(ASCII).encode("latin-1", "replace").decode("latin-1")  # Replace characters it can't show
    pdf.add_page()  # First page

    def text(size, style="", color=TEXT):  # Sets the font for the next text
        pdf.set_font(pdf.body_font, style, size)  # Size and style
        pdf.set_text_color(*color)  # Color

    def paragraph(value, size=10, style="", color=TEXT, fill=None, padding=0, gap=1.5):  # Writes wrapped text, optionally on a colored background
        text(size, style, color)  # Font
        if fill:  # A colored box
            pdf.set_fill_color(*fill)  # Its color
        pdf.multi_cell(0, size * 0.5, clean(value), fill=bool(fill), padding=padding, align="L", new_x="LMARGIN", new_y="NEXT")  # The text, wrapped to the page width
        pdf.ln(gap)  # A little space after it

    def label(value):  # A small grey uppercase heading
        paragraph(value.upper(), size=7.5, style="B", color=MUTED, gap=0.5)  # e.g. "EVIDENCE FROM THE AD"

    # ---------- Title ----------
    text(16, "B")  # Big bold
    pdf.cell(0, 8, "ASC Ad Pre-screen Report", new_x="LMARGIN", new_y="NEXT")  # Title
    details = [file_name or "Uploaded image", f"Checked {result.get('checked_at') or datetime.now().strftime('%B %d, %Y %I:%M %p')}"]  # File and date
    paragraph("  ·  ".join(details), size=8.5, color=MUTED, gap=4)  # Under the title

    # ---------- Verdict ----------
    verdict = result.get("result", "ERROR")  # COMPLIANT, NON-COMPLIANT or ERROR
    bg, fg = COLORS.get(verdict, COLORS["ERROR"])  # Its colors
    reasons = result.get("reasons") or []  # The violations
    if verdict == "NON-COMPLIANT":  # Failed
        summary = f"{len(reasons)} issue{'s' if len(reasons) != 1 else ''} must be fixed before this ad can run."  # How many problems
    elif verdict == "COMPLIANT":  # Passed
        summary = result.get("approval_summary") or "No ASC violations were found."  # Why it passed
    else:  # Could not check
        summary = str(result.get("message") or "The image could not be checked.").split("\n")[0]  # Why
    pdf.set_fill_color(*bg)  # Verdict box color
    text(14, "B", fg)  # Verdict title font
    pdf.multi_cell(0, 7, LABELS.get(verdict, verdict), fill=True, padding=(3, 4, 0, 4), align="L", new_x="LMARGIN", new_y="NEXT")  # Title line of the box
    paragraph(summary, size=10, fill=bg, padding=(1, 4, 3, 4), gap=5)  # Summary line of the box

    # ---------- Image ----------
    try:  # The image might be unreadable
        img = Image.open(io.BytesIO(image_bytes))  # Open it
        img = img.convert("RGB")  # Remove transparency (PDF images are simpler without it)
        img.thumbnail((1600, 1600))  # Shrink very large images so the PDF stays small
        buffer = io.BytesIO()  # In-memory file
        img.save(buffer, format="JPEG", quality=88)  # Save as JPEG
        width = min(pdf.epw, 130)  # At most 130 mm wide
        height = width * img.height / img.width  # Keep the shape
        if height > 105:  # Too tall
            height, width = 105, 105 * img.width / img.height  # Limit the height instead
        if pdf.get_y() + height > pdf.page_break_trigger:  # Doesn't fit on this page
            pdf.add_page()  # Start a new one
        x, y = (pdf.w - width) / 2, pdf.get_y()  # Centered
        pdf.image(buffer, x=x, y=y, w=width, h=height)  # Draw it
        pdf.set_draw_color(228, 231, 236)  # Light grey
        pdf.rect(x, y, width, height)  # Thin border around it
        pdf.set_y(y + height + 6)  # Continue below the image
    except Exception:  # Not a readable image
        paragraph("(The image could not be added to this report.)", size=9, color=MUTED, gap=4)  # Say so

    # ---------- Findings ----------
    text(12, "B")  # Section heading font
    pdf.cell(0, 7, "Findings", new_x="LMARGIN", new_y="NEXT")  # Heading
    pdf.ln(1)  # Small gap
    if verdict == "NON-COMPLIANT":  # List each violation
        for i, r in enumerate(reasons, start=1):  # Each one
            info = r.get("info") or {}  # The rule explanation
            title = f"{i}. {r.get('problem', '')}"  # Number and problem
            if r.get("added_by_code"):  # Found by the decency check, not the AI
                title += "  (added by decency check)"  # Mark it
            paragraph(title, size=10.5, style="B", gap=1)  # The problem
            if info.get("title") or info.get("summary"):  # A rule explanation exists
                label("What the ASC rule says")  # Heading
                rule_title = f"{info['id']} · {info.get('title', '')}" if info.get("id") else info.get("title", "")  # e.g. "R-ALC · Alcohol beverage rules"
                pdf.set_fill_color(239, 248, 255)  # Light blue box
                text(9.5, "B", BLUE)  # Bold blue
                pdf.multi_cell(0, 4.8, clean(rule_title), fill=True, padding=(2, 3, 0.5, 3), align="L", new_x="LMARGIN", new_y="NEXT")  # Rule name
                body = info.get("summary", "")  # What the rule says
                if info.get("why"):  # Why it applies to this ad
                    body += f"\n\nWhy it applies: {info['why']}"  # Add it
                paragraph(body, size=9.5, color=BLUE, fill=(239, 248, 255), padding=(0.5, 3, 2, 3), gap=1)  # Rule text
            label("Evidence from the ad")  # Heading
            paragraph(r.get("evidence", ""), size=9.5, style="I", fill=(249, 250, 251), padding=(1.5, 3, 1.5, 3), gap=1)  # Quoted evidence
            label("How to fix")  # Heading
            paragraph(r.get("suggestion", ""), size=9.5, color=(6, 118, 71), gap=0.5)  # The fix
            paragraph(f"ASC reference: {r.get('rule', '')}", size=8, color=MUTED, gap=5)  # Rule reference
    elif verdict == "COMPLIANT":  # List the checks made
        checks = result.get("checks_passed") or []  # What was checked
        for c in checks:  # Each check
            paragraph(f"OK  {c.get('check', '')}", size=10, style="B", color=(6, 118, 71), gap=0.5)  # What was checked
            paragraph(c.get("finding", ""), size=9.5, gap=0.5)  # What was found
            if c.get("guideline"):  # Which rule
                paragraph(f"ASC guideline: {c['guideline']}", size=8, color=MUTED, gap=3)  # Rule reference
        if not checks:  # Nothing listed
            paragraph("No individual checks were listed.", size=9.5, color=MUTED, gap=3)  # Say so
    else:  # Could not check
        paragraph(result.get("message", ""), size=9.5, gap=3)  # The full reason

    removed = result.get("removed_reasons") or []  # Violations removed as not backed by the image
    if removed:  # There were some
        label("Removed by verification (not backed by the image)")  # Heading
        paragraph("\n".join(f"- {x}" for x in removed), size=8.5, color=MUTED, gap=4)  # List them

    # ---------- Reviewer decision ----------
    if pdf.get_y() + 62 > pdf.page_break_trigger:  # Keep the whole decision block together
        pdf.add_page()  # Start a new page
    pdf.ln(2)  # Space before
    text(12, "B")  # Section heading font
    pdf.cell(0, 7, "Reviewer decision", new_x="LMARGIN", new_y="NEXT")  # Heading
    pdf.ln(1)  # Small gap
    text(10.5)  # Option font
    pdf.set_draw_color(*TEXT)  # Dark lines
    x = pdf.l_margin  # Start at the left margin
    for option in ("Approve", "Revise", "Reject"):  # The three choices
        y = pdf.get_y()  # Current line
        pdf.rect(x, y + 0.8, 4, 4)  # Checkbox
        if option == decision:  # The chosen one
            pdf.line(x + 0.7, y + 1.5, x + 3.3, y + 4.1)  # Draw an X
            pdf.line(x + 3.3, y + 1.5, x + 0.7, y + 4.1)  # ...second stroke
        pdf.set_xy(x + 6, y)  # Text next to the box
        pdf.cell(28, 5.6, option)  # Option name
        x += 36  # Move right for the next option
    pdf.set_xy(pdf.l_margin, pdf.get_y() + 9)  # Next line
    label("Notes")  # Heading
    if notes.strip():  # Notes were written
        paragraph(notes, size=10, fill=(249, 250, 251), padding=(2, 3, 2, 3), gap=6)  # Show them
    else:  # No notes
        y = pdf.get_y()  # Current line
        pdf.set_draw_color(208, 213, 221)  # Light grey
        pdf.rect(pdf.l_margin, y, pdf.epw, 22)  # Empty box for handwritten notes
        pdf.set_y(y + 28)  # Below it
    text(10)  # Signature font
    pdf.cell(pdf.epw * 0.6, 6, "Reviewed by: ______________________________")  # Signature line
    pdf.cell(0, 6, "Date: ________________", new_x="LMARGIN", new_y="NEXT")  # Date line

    # ---------- Appendix: what the AI saw ----------
    if result.get("description"):  # The vision model's description
        pdf.add_page()  # On its own page
        text(12, "B")  # Section heading font
        pdf.cell(0, 7, "Appendix: what the AI saw in the image", new_x="LMARGIN", new_y="NEXT")  # Heading
        paragraph("The vision model's description. The findings above are based only on this text, so check it if a finding looks wrong.", size=8.5, color=MUTED, gap=3)  # Why it's included
        paragraph(result["description"].strip(), size=8.5, gap=0)  # The description

    return bytes(pdf.output())  # The finished PDF
