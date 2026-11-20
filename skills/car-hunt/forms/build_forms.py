#!/usr/bin/env python3
"""Standard, vehicle-agnostic car-hunt forms — fraud/paperwork checklist + a
fillable Alabama motor-vehicle bill of sale.

These are the REUSABLE documents (they don't change per car), so they live in
the skill. Per-car test-drive checklists are generated on demand and are NOT
kept with the skill (see references/test-drive.md, Step 5.5).

JURISDICTION EXAMPLE: Alabama is one state's worked example. The only
state-specific parts are the fraud checklist's "TITLE TRANSFER" section and the
bill of sale's state line, footer, filename and title. Edit those (search for
"Alabama") to match your state's motor-vehicle agency before relying on them.

Run:  python3 build_forms.py            # writes both PDFs next to this script
Outputs:
    fraud-paperwork-checklist.pdf
    bill-of-sale-alabama.pdf
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak)
from reportlab.platypus.flowables import HRFlowable

DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
pdfmetrics.registerFont(TTFont("DejaVu", DEJAVU))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", DEJAVU_BOLD))

OUTDIR = os.path.dirname(os.path.abspath(__file__))
RED = HexColor("#a83232")
BLUE = HexColor("#2a4d8f")
GREY = HexColor("#555555")
BOX = "☐"


def _styles(accent):
    return {
        "h1": ParagraphStyle("h1", fontName="DejaVu-Bold", fontSize=15,
                             textColor=accent, spaceAfter=2, leading=18),
        "sub": ParagraphStyle("sub", fontName="DejaVu", fontSize=8.5,
                              textColor=GREY, leading=11),
        "section": ParagraphStyle("section", fontName="DejaVu-Bold", fontSize=10.5,
                                 textColor=accent, spaceBefore=8, spaceAfter=3,
                                 leading=13),
        "item": ParagraphStyle("item", fontName="DejaVu", fontSize=9, leading=12.5,
                              leftIndent=2, spaceAfter=1.5),
        "foot": ParagraphStyle("foot", fontName="DejaVu", fontSize=7.5,
                              textColor=GREY, leading=10, spaceBefore=6),
        "field": ParagraphStyle("field", fontName="DejaVu", fontSize=9.5,
                               leading=20, spaceAfter=2),
        "fine": ParagraphStyle("fine", fontName="DejaVu", fontSize=7.5,
                              leading=10, textColor=GREY, spaceBefore=2),
        "center": ParagraphStyle("center", fontName="DejaVu-Bold", fontSize=13,
                                textColor=BLUE, alignment=TA_CENTER, spaceAfter=2),
    }


def _chk(text, st):
    return Paragraph(f"{BOX}&nbsp; {text}", st["item"])


# ----------------------------------------------------------------------------
# 1) Fraud / paperwork checklist (vehicle-agnostic, reusable across all cars)
# ----------------------------------------------------------------------------
def build_fraud():
    st = _styles(RED)
    out = os.path.join(OUTDIR, "fraud-paperwork-checklist.pdf")
    doc = SimpleDocTemplate(
        out, pagesize=letter, leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.4*inch, bottomMargin=0.4*inch,
        title="Car-Hunt Fraud / Paperwork Checklist (reusable)",
        author="car-hunt skill")
    s = [Paragraph("FRAUD / PAPERWORK CHECKLIST", st["h1"]),
         Paragraph("Vehicle-agnostic — use for every car. Most useful in the driveway "
                   "with the title in your hand.", st["sub"]),
         HRFlowable(width="100%", thickness=1.1, color=RED, spaceBefore=4, spaceAfter=4)]
    secs = [
        ("⚠ WALK-AWAY TRIGGERS (single fail → leave)", [
            "Seller refuses to share the VIN beforehand",
            "No title at the meeting, or only a photocopy",
            "VIN on title ≠ dashboard ≠ door-jamb sticker",
            'Title brand reads "Salvage" / "Rebuilt" / "Junk" / "Flood"',
            "Lien listed with no release letter",
            "Seller's name is NOT on the title as owner (title-jumping)",
            "Demand for crypto, wire, gift cards, or a deposit to hold",
            "Pressure to sign blank or incomplete forms",
            "Seller's ID name doesn't match the title",
            "Seller keeps changing the meeting place or rushing you",
        ]),
        ("TITLE DOCUMENT — visual inspection", [
            "Original document, not a photocopy",
            "Watermarks / security features present",
            "No erasures, white-out, or overwriting",
            "Filled out in a single ink color, consistent handwriting",
            "Brand-history field clean (no salvage/flood/junk notations)",
            "Owner name printed, matches seller ID",
            "Odometer field filled in and legible",
            "Issue date plausible vs. how long seller says they've owned it",
        ]),
        ("VIN VERIFICATION — three locations must match", [
            "Dashboard VIN (base of windshield): _________________",
            "Door-jamb sticker VIN: _________________",
            "Title VIN: _________________",
            "All 17 chars match digit-by-digit (watch 0/O, 1/I/L, 5/S, 2/Z, 8/B)",
            "Dash VIN plate intact, no fresh adhesive or scratches",
            "Cross-check at nhtsa.gov/recalls and nicb.org/vincheck (free)",
        ]),
        ("CURBSTONING / FAKE-PRIVATE-SELLER DETECTION", [
            "Title has been in seller's name 30+ days",
            "ID matches the name AND address on the title",
            "Ownership story is plausible and consistent",
            "Insurance card present in seller's name",
            "Listing photos are personal (home/driveway), not a lot or curbside",
            "Seller isn't juggling several cars on one profile",
            "Phone area code is local; meeting at their home",
        ]),
        ("ODOMETER-FRAUD DETECTION", [
            'Title odometer matches the dash within ~1,000 mi; no "Not Actual Mileage"',
            "Wear is consistent with the miles: seat bolster, steering wheel, pedals, "
            "carpet, door handles, shift knob",
            "Service / oil-change stickers line up with the reading",
            "Instrument-cluster screws look factory (not recently removed)",
            "If you have a capable scanner, compare ECU mileage to the dash",
        ]),
        ("BILL OF SALE", [
            "Two identical copies (use the bill-of-sale form — seller + buyer copy)",
            "Today's date",
            "Both names + addresses",
            "Full 17-char VIN and the odometer reading",
            "Actual sale price",
            "AS-IS / WHERE-IS language",
            "Both parties sign AND date both copies",
            "Photo of seller's ID alongside the bill of sale + VIN",
        ]),
        # Jurisdiction example (Alabama) — replace with your state's rules.
        ("TITLE TRANSFER — Alabama mechanics (example state)", [
            "Seller signs the SELLER section only, in your presence",
            "Seller fills in odometer + sale price",
            "Buyer does NOT sign yet — Alabama needs a courthouse witness",
            "Register within 20 days at the probate/license office",
            "Bring: signed title + bill of sale + your ID + insurance + payment (~2% sales tax)",
        ]),
        ("PAYMENT PROTECTION", [
            "Pay only after the title + keys are in your hand",
            "Counterfeit-detector pen if paying cash",
            "Prefer a bank-to-bank meet at a teller window",
            "Never crypto / gift cards / wire to a remote bank; no deposits",
            "Get a written, signed receipt (the bill of sale covers this)",
        ]),
        ("STOLEN-VEHICLE / TITLE-JUMPING DETECTION", [
            "NICB VINCheck came back clean",
            "Ignition and locks intact (no punched/replaced lock)",
            "Service records show a consistent owner",
            "Insurance and registration match the title name",
            "Seller is the registered owner — NOT 'I haven't transferred it yet'",
            "Offer to meet at a police station — honest sellers say yes",
        ]),
        ("AFTER PURCHASE (within 7 days)", [
            "Register at the probate office; get a new plate",
            "Update your insurance to the new car",
            "Independent mechanic post-purchase inspection ($75–100)",
            "Save all documents for 3+ years",
        ]),
    ]
    for i, (title, items) in enumerate(secs):
        s.append(Paragraph(title, st["section"]))
        for it in items:
            s.append(_chk(it, st))
        if i == 3:
            s.append(PageBreak())
    s.append(HRFlowable(width="100%", thickness=0.6, color=GREY,
                        spaceBefore=8, spaceAfter=3))
    s.append(Paragraph(
        "<i>This checklist exists because used-car fraud is a multi-billion-dollar industry. "
        "Most sellers are honest; the protective habit is simple — walk away if anything "
        "feels off. There will be another car.</i>", st["foot"]))
    doc.build(s)
    return out


# ----------------------------------------------------------------------------
# 2) Motor-vehicle bill of sale — Alabama as the jurisdiction example
#    (fillable; prints a seller + buyer copy). Adapt the state lines for yours.
# ----------------------------------------------------------------------------
def _bos_pages(st, copy_label):
    """One bill-of-sale page (copy_label = 'SELLER'S COPY' / 'BUYER'S COPY')."""
    U = "________________________"          # short underline
    UL = "______________________________________________"  # long underline
    s = [
        Paragraph("MOTOR VEHICLE BILL OF SALE", st["center"]),
        Paragraph("State of Alabama", ParagraphStyle(
            "stt", fontName="DejaVu", fontSize=9, alignment=TA_CENTER,
            textColor=GREY, spaceAfter=2)),
        Paragraph(f"<b>{copy_label}</b>", ParagraphStyle(
            "cl", fontName="DejaVu-Bold", fontSize=8.5, alignment=TA_CENTER,
            textColor=RED, spaceAfter=4)),
        HRFlowable(width="100%", thickness=1.0, color=BLUE, spaceAfter=6),
        Paragraph(f"Date of sale:&nbsp; {U}", st["field"]),
        Paragraph("<b>SELLER</b>", st["section"]),
        Paragraph(f"Name:&nbsp; {UL}", st["field"]),
        Paragraph(f"Address:&nbsp; {UL}", st["field"]),
        Paragraph(f"City / State / ZIP:&nbsp; {U}{U}", st["field"]),
        Paragraph(f"Phone:&nbsp; {U}&nbsp;&nbsp; Driver's license #:&nbsp; {U}", st["field"]),
        Paragraph("<b>BUYER</b>", st["section"]),
        Paragraph(f"Name:&nbsp; {UL}", st["field"]),
        Paragraph(f"Address:&nbsp; {UL}", st["field"]),
        Paragraph(f"City / State / ZIP:&nbsp; {U}{U}", st["field"]),
        Paragraph(f"Phone:&nbsp; {U}&nbsp;&nbsp; Driver's license #:&nbsp; {U}", st["field"]),
        Paragraph("<b>VEHICLE</b>", st["section"]),
    ]
    veh = [
        ["Year:", "____________", "Make:", "________________"],
        ["Model:", "____________", "Body type:", "________________"],
        ["Color:", "____________", "Title no.:", "________________"],
    ]
    t = Table(veh, colWidths=[0.8*inch, 1.7*inch, 1.0*inch, 3.0*inch])
    t.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), "DejaVu", 9.5),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LINEBELOW", (1,0), (1,-1), 0.5, GREY),
        ("LINEBELOW", (3,0), (3,-1), 0.5, GREY),
    ]))
    s.append(t)
    s.append(Paragraph(f"Vehicle Identification Number (VIN):&nbsp; {UL}", st["field"]))
    s.append(Paragraph("<b>ODOMETER DISCLOSURE</b> (federal law requires the odometer "
                       "reading at the time of transfer)", st["section"]))
    s.append(Paragraph(
        f"Odometer reads&nbsp; {U}&nbsp; miles. The seller certifies this reading is "
        "(check one):", st["field"]))
    s.append(_chk("the ACTUAL mileage.", st))
    s.append(_chk("NOT the actual mileage (odometer discrepancy — WARNING).", st))
    s.append(_chk("in EXCESS of its mechanical limits.", st))
    s.append(Paragraph("<b>SALE PRICE &amp; TERMS</b>", st["section"]))
    s.append(Paragraph(f"Sale price:&nbsp; $ {U}&nbsp;&nbsp; "
                       f"Amount in words:&nbsp; {U}{U} dollars", st["field"]))
    s.append(Paragraph(
        "This vehicle is sold <b>AS-IS, WHERE-IS</b>, with no warranties expressed or "
        "implied. The seller certifies they are the legal owner with the right to sell, "
        "and that the vehicle is free of all liens except as noted above.", st["fine"]))
    s.append(Spacer(1, 8))
    sign = [
        ["Seller signature:", "_________________________", "Date:", "____________"],
        ["Buyer signature:", "_________________________", "Date:", "____________"],
    ]
    ts = Table(sign, colWidths=[1.4*inch, 2.7*inch, 0.6*inch, 1.3*inch])
    ts.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), "DejaVu", 9.5),
        ("TOPPADDING", (0,0), (-1,-1), 12), ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    s.append(ts)
    s.append(Paragraph(
        "<i>Make two copies — one for the seller, one for the buyer; both parties sign both. "
        "In Alabama, sign the title's SELLER section now but wait to sign as BUYER until the "
        "courthouse (a witness is required). Register within 20 days.</i>", st["foot"]))
    return s


def build_bill_of_sale():
    st = _styles(BLUE)
    out = os.path.join(OUTDIR, "bill-of-sale-alabama.pdf")
    doc = SimpleDocTemplate(
        out, pagesize=letter, leftMargin=0.6*inch, rightMargin=0.6*inch,
        topMargin=0.45*inch, bottomMargin=0.4*inch,
        title="Alabama Motor Vehicle Bill of Sale (fillable)",
        author="car-hunt skill")
    story = _bos_pages(st, "SELLER'S COPY")
    story.append(PageBreak())
    story += _bos_pages(st, "BUYER'S COPY")
    doc.build(story)
    return out


if __name__ == "__main__":
    for f in (build_fraud(), build_bill_of_sale()):
        print("wrote", f)
