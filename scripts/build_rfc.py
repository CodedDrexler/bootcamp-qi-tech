"""Generate the submission PDF from docs/rfc.md; pip install -r requirements-docs.txt."""

from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Flowable,
    PageBreak,
    KeepTogether,
)

ROOT = Path(__file__).resolve().parents[1]
NAVY = colors.HexColor("#152C48")
TEAL = colors.HexColor("#087F83")
LIGHT = colors.HexColor("#EDF6F6")
TEXT = colors.HexColor("#253445")
FONT, BOLD = "Helvetica", "Helvetica-Bold"
if Path("C:/Windows/Fonts/arial.ttf").exists():
    pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"))
    FONT, BOLD = "Arial", "Arial-Bold"
    pdfmetrics.registerFontFamily(
        "Arial", normal=FONT, bold=BOLD, italic=FONT, boldItalic=BOLD
    )

STYLES = {
    "body": ParagraphStyle(
        "body",
        fontName=FONT,
        fontSize=9.2,
        leading=12,
        textColor=TEXT,
        spaceAfter=5,
        alignment=TA_LEFT,
    ),
    "title": ParagraphStyle(
        "title",
        fontName=BOLD,
        fontSize=20,
        leading=24,
        textColor=NAVY,
        spaceAfter=10,
        keepWithNext=True,
    ),
    "h2": ParagraphStyle(
        "h2",
        fontName=BOLD,
        fontSize=13,
        leading=16,
        textColor=NAVY,
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True,
    ),
    "h3": ParagraphStyle(
        "h3",
        fontName=BOLD,
        fontSize=10.5,
        leading=14,
        textColor=TEAL,
        spaceBefore=7,
        spaceAfter=5,
        keepWithNext=True,
    ),
    "label": ParagraphStyle(
        "label",
        fontName=BOLD,
        fontSize=9.2,
        leading=12,
        textColor=NAVY,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True,
    ),
    "cell": ParagraphStyle(
        "cell", fontName=FONT, fontSize=7.6, leading=9.5, textColor=TEXT
    ),
    "header": ParagraphStyle(
        "header", fontName=BOLD, fontSize=7.6, leading=9.5, textColor=colors.white
    ),
}


def markup(s):
    s = escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = s.replace("`", "")
    # A typographic arrow is not available in every PDF font.
    return s.replace("→", "&gt;")


class ERDiagram(Flowable):
    def __init__(self):
        super().__init__()
        self.width = 515
        self.height = 337

    def draw(self):
        c = self.canv
        boxes = {
            "CUSTOMER": (
                0,
                237,
                157,
                100,
                [
                    "id PK | customer_key UK",
                    "document_number UK | email UK",
                    "name | birthdate",
                    "created_at TIMESTAMPTZ",
                ],
            ),
            "ACCOUNT": (
                178,
                237,
                157,
                100,
                [
                    "id PK | account_key UK",
                    "customer_id FK + UK",
                    "balance >= 0; <= MAX",
                    "status ACTIVE / CLOSED",
                    "CLOSED => balance = 0",
                    "created_at TIMESTAMPTZ",
                ],
            ),
            "PIGGY_BANK": (
                358,
                237,
                157,
                100,
                [
                    "id PK | piggy_bank_key UK",
                    "account_id FK | name",
                    "UK(account_id, name)",
                    "balance >= 0 | target_amount > 0",
                    "status ACTIVE / CLOSED",
                    "created_at TIMESTAMPTZ",
                ],
            ),
            "BANK_TRANSACTION": (
                0,
                127,
                157,
                87,
                [
                    "id PK | transaction_key UK",
                    "type | amount > 0 | fee >= 0",
                    "created_at TIMESTAMPTZ",
                    "SUM(entries.amount) = 0",
                ],
            ),
            "LEDGER_ENTRY": (
                178,
                65,
                157,
                149,
                [
                    "id PK | entry_key UK",
                    "transaction_id FK",
                    "account_id FK nullable",
                    "piggy_bank_id FK nullable",
                    "pocket CHECKING / PIGGY",
                    "pocket CLEARING / FEES",
                    "type (inclui FEE)",
                    "amount != 0, com sinal",
                    "balance_after (sistema: null)",
                    "created_at TIMESTAMPTZ",
                    "Histórico imutável",
                ],
            ),
            "BANK_STATUS_EVENT": (
                358,
                127,
                157,
                87,
                [
                    "id PK | account_id FK",
                    "piggy_bank_id FK nullable",
                    "status ACTIVE / CLOSED",
                    "created_at TIMESTAMPTZ",
                    "Histórico imutável",
                ],
            ),
            "IDEMPOTENCY_RECORD": (
                0,
                0,
                157,
                105,
                [
                    "id PK | scope | key",
                    "UK(scope, key)",
                    "fingerprint SHA256",
                    "response JSONB",
                    "created_at TIMESTAMPTZ",
                ],
            ),
        }
        c.setStrokeColor(TEAL)
        c.setLineWidth(0.85)
        # Relationship connectors are drawn before the boxes.
        for x1, y1, x2, y2 in [
            (157, 287, 178, 287),
            (335, 287, 358, 287),
            (256, 237, 256, 214),
            (157, 170, 178, 170),
            (437, 237, 437, 214),
        ]:
            c.line(x1, y1, x2, y2)
            c.circle(x2, y2, 2, fill=0, stroke=1)
        # Piggy -> ledger, routed through the gutter.
        c.lines([(365, 237, 347, 227), (347, 227, 347, 90), (347, 90, 335, 90)])
        c.lines([(320, 237, 320, 224), (320, 224, 400, 224), (400, 224, 400, 214)])
        c.setFont(FONT, 6.5)
        c.setFillColor(TEAL)
        c.drawString(161, 294, "0..1")
        c.drawString(338, 294, "0..N")
        c.drawString(158, 179, "2..N")
        for name, (x, y, w, h, fields) in boxes.items():
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.HexColor("#A7C3C5"))
            c.roundRect(x, y, w, h, 4, fill=1, stroke=1)
            c.setFillColor(NAVY)
            c.rect(x, y + h - 21, w, 21, fill=1, stroke=0)
            c.setFillColor(colors.white)
            c.setFont(BOLD, 8)
            c.drawString(x + 7, y + h - 14, name)
            c.setFillColor(TEXT)
            c.setFont(FONT, 7)
            for i, field in enumerate(fields):
                c.drawString(x + 7, y + h - 35 - i * 9.2, field)
        c.setFont(FONT, 7)
        c.setFillColor(TEAL)
        c.drawString(178, 35, "PK = primária | FK = estrangeira | UK = única")
        c.drawString(178, 23, "MAX = 9.000.000.000.000.000 centavos")
        c.drawString(178, 11, "Saldo = soma do bolso; conferência no COMMIT")


def footer(c, doc):
    c.setStrokeColor(colors.HexColor("#CCE1E2"))
    c.line(40, 35, A4[0] - 40, 35)
    c.setFillColor(NAVY)
    c.setFont(FONT, 7.5)
    c.drawString(
        40, 23, "Porquinho Bank | Vinicius e Wallace | Bootcamp QI Tech 2026 | RFC 1.0"
    )
    c.drawRightString(A4[0] - 40, 23, str(doc.page))


def main():
    lines = (ROOT / "docs/rfc.md").read_text(encoding="utf-8").splitlines()
    story = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("```mermaid"):
            while i < len(lines) and lines[i].strip() != "```":
                i += 1
            story += [ERDiagram(), Spacer(1, 6)]
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                row = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-:]+", cell) for cell in row):
                    style = STYLES["header" if not rows else "cell"]
                    rows.append([Paragraph(markup(cell), style) for cell in row])
                i += 1
            t = Table(rows, colWidths=[43, 110, 160, 202], repeatRows=1, hAlign="LEFT")
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story += [t, Spacer(1, 6)]
            continue
        elif line.startswith("# "):
            story.append(Paragraph(markup(line[2:]), STYLES["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(markup(line[3:]), STYLES["h2"]))
        elif line.startswith("### "):
            if line == "### Fluxos":
                story.append(PageBreak())
            story.append(Paragraph(markup(line[4:]), STYLES["h3"]))
        elif line.startswith("**") and line.endswith("**"):
            story.append(Paragraph(markup(line), STYLES["label"]))
        else:
            text = line
            while (
                i + 1 < len(lines)
                and lines[i + 1].strip()
                and not re.match(r"^(#|\||```|\*\*|\d+\.|- )", lines[i + 1])
            ):
                i += 1
                text += " " + lines[i].strip()
            story.append(Paragraph(markup(text), STYLES["body"]))
        i += 1
    out = ROOT / "output/pdf/RFC-Porquinho-Bank.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=35,
        bottomMargin=45,
        title="RFC - Porquinho Bank",
        author="Vinicius e Wallace",
    )
    grouped = []
    i = 0
    while i < len(story):
        item = story[i]
        if isinstance(item, Paragraph) and item.style.name == "label":
            block = [item]
            i += 1
            while (
                i < len(story)
                and isinstance(story[i], Paragraph)
                and story[i].style.name == "body"
            ):
                block.append(story[i])
                i += 1
            grouped.append(KeepTogether(block))
        else:
            grouped.append(item)
            i += 1
    doc.build(grouped, onFirstPage=footer, onLaterPages=footer)
    print(out)


if __name__ == "__main__":
    main()
