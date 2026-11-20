"""Build docs/deck/FinShield-deck.pptx (8 slides). Run: python build_deck.py <repo_root>"""
import sys
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

ROOT = Path(sys.argv[1])
OUT = ROOT / "docs/deck/FinShield-deck.pptx"
NAVY, INK, MUTED, RED, ORANGE, AMBER, TEAL, BG = (
    RGBColor(0x12, 0x23, 0x3D), RGBColor(0x1F, 0x29, 0x33), RGBColor(0x5B, 0x6B, 0x7A),
    RGBColor(0xC6, 0x28, 0x28), RGBColor(0xEF, 0x6C, 0x00), RGBColor(0xF9, 0xA8, 0x25),
    RGBColor(0x00, 0x79, 0x6B), RGBColor(0xF5, 0xF7, 0xFA))
TODO = RGBColor(0xB0, 0x00, 0x20)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


def text(slide, x, y, w, h, runs, size=18, color=INK, bold=False, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    items = runs if isinstance(runs, list) else [runs]
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        s, c, b, sz = item if isinstance(item, tuple) else (item, color, bold, size)
        r = p.add_run(); r.text = s
        r.font.size = Pt(sz); r.font.color.rgb = c; r.font.bold = b; r.font.name = "Calibri"
        p.space_after = Pt(6)
    return tb


def card(slide, x, y, w, h, fill=BG):
    s = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = fill; s.line.color.rgb = RGBColor(0xDD, 0xE3, 0xEA)
    s.shadow.inherit = False
    return s


def slide(title, kicker, notes):
    s = prs.slides.add_slide(BLANK)
    bar = s.shapes.add_shape(1, 0, 0, prs.slide_width, Inches(0.12))
    bar.fill.solid(); bar.fill.fore_color.rgb = NAVY; bar.line.fill.background()
    text(s, 0.6, 0.35, 12, 0.4, kicker.upper(), size=12, color=TEAL, bold=True)
    text(s, 0.6, 0.7, 12, 0.9, title, size=32, color=NAVY, bold=True)
    text(s, 0.6, 7.0, 12, 0.35, "FinShield AI · DPDP-aligned readiness and controls · all data synthetic (SAMPLE)",
         size=10, color=MUTED)
    s.notes_slide.notes_text_frame.text = notes
    return s


# 1 Problem and the 3 deadlines
s = slide("One insider leak starts three clocks", "Problem",
          "A digital lender holds KYC for every borrower. When a privileged insider exports it, three reporting clocks start. "
          "RBI and CERT-In are 6 hours; the Data Protection Board detailed report is 72 hours (DPDP Rules in force about May 2027). "
          "Today most lenders discover the leak days later. Penalties under the DPDP Act Schedule go up to Rs 250 crore for failing security safeguards.")
for i, (body, hrs, src, col) in enumerate([
        ("RBI", "6 h", "from detection\nNBFC Cybersecurity Directions 2026, para 141", RED),
        ("CERT-In", "6 h", "from noticing\nCERT-In Directions 2022, Direction (ii)", RED),
        ("Data Protection Board", "72 h", "detailed report, from becoming aware\nDPDP Rules 2025, r.7(2)(b)", ORANGE)]):
    x = 0.6 + i * 4.1
    card(s, x, 2.0, 3.8, 3.2)
    text(s, x + 0.3, 2.2, 3.3, 0.5, body, size=18, color=MUTED, bold=True)
    text(s, x + 0.3, 2.7, 3.3, 1.2, hrs, size=60, color=col, bold=True)
    text(s, x + 0.3, 4.1, 3.3, 1.0, src, size=12, color=MUTED)
text(s, 0.6, 5.5, 12, 1.2, [
    ("FinShield shows these as readiness timers from the moment it detects the incident.", INK, False, 16),
    ("DPDP Act penalties: up to Rs 250 crore (security safeguards), up to Rs 200 crore (breach notice).", MUTED, False, 14)])

# 2 Who we protect
s = slide("Who we protect", "Customers",
          "Buyers are NBFCs and digital lenders running on AWS, and the lending service providers who work for them. "
          "RBI makes the lender fully liable for its LSP's acts (NBFC Credit Facilities Directions 2025, para 6(7)).")
for i, (h, b) in enumerate([
        ("NBFCs and digital lenders", "Hold Aadhaar, PAN and bank KYC for every borrower, on AWS, in India."),
        ("Lending service partners", "Collections agents and partner staff touch borrower data. The lender stays fully liable (RBI para 6(7))."),
        ("Their borrowers", "Whose KYC, consent and money are at stake when an insider or stolen account goes rogue.")]):
    x = 0.6 + i * 4.1
    card(s, x, 2.0, 3.8, 3.6)
    text(s, x + 0.3, 2.2, 3.3, 0.8, h, size=20, color=NAVY, bold=True)
    text(s, x + 0.3, 3.1, 3.3, 2.4, b, size=15, color=INK)

# 3 Product
s = slide("Monitor to Respond, in one minute", "Product",
          "Eight modules. Code computes every number; Bedrock only writes the words.")
mods = [("Monitor", "CloudTrail, Config, GuardDuty"), ("Detect", "11 signals, scored in code"),
        ("Correlate", "one incident per user per hour"), ("Alert", "CRITICAL in under 60 s"),
        ("Investigate", "score bar, timeline, AI card"), ("Align with compliance", "clauses, report drafts"),
        ("Respond", "revoke, deactivate, deny, approve, release"), ("Visualize", "posture, privacy, accuracy")]
for i, (h, b) in enumerate(mods):
    x, y = 0.6 + (i % 4) * 3.1, 1.9 + (i // 4) * 2.4
    card(s, x, y, 2.9, 2.1)
    text(s, x + 0.2, y + 0.2, 2.6, 0.6, h, size=19, color=TEAL, bold=True)
    text(s, x + 0.2, y + 0.9, 2.6, 1.1, b, size=14, color=INK)
text(s, 0.6, 6.4, 12, 0.5, "Code computed every number; AI only wrote the words.", size=16, color=NAVY, bold=True)

# 4 Architecture
s = slide("Serverless on AWS, in Mumbai", "Architecture",
          "Everything in ap-south-1, so data stays in India (RBI para 14(4)). Events go through EventBridge; detection and "
          "containment are Lambda; Step Functions runs the incident; Bedrock with a Guardrail writes text only; evidence is "
          "hash-chained into S3 Object Lock.")
s.shapes.add_picture(str(ROOT / "docs/architecture.png"), Inches(1.4), Inches(1.6), height=Inches(5.3))

# 5 Live demo
s = slide("Live demo: SC-01", "Demo",
          "Switch to the browser. Follow docs/demo-script.md steps 2 to 5.")
steps = [("Attack", "Ops admin: emergency role, 23:40, new device, 212 KYC files, external upload"),
         ("Detect", "Score 96 CRITICAL in < 60 s; three timers start"),
         ("Investigate", "106x normal volume · role without approval · new device · off-hours · upload"),
         ("Respond", "Sessions revoked, keys off, bucket deny → Approve → LOCKED → Release"),
         ("Evidence", "Chain verifies green; tamper demo breaks red; CERT-In draft ready")]
for i, (h, b) in enumerate(steps):
    y = 1.8 + i * 1.0
    card(s, 0.6, y, 12.1, 0.85)
    text(s, 0.8, y + 0.18, 2.4, 0.6, h, size=18, color=RED if i < 2 else NAVY, bold=True)
    text(s, 3.2, y + 0.2, 9.4, 0.6, b, size=16)

# 6 Rules, edge cases, accuracy
s = slide("Loud when it should be, quiet when it should be", "Rules and accuracy",
          "11 of 11 scenarios plus 7 normal days, 0 false alerts (numbers from the Accuracy panel; re-check at CP5).")
rows = [("SC-01", "Insider bulk KYC export + upload", "96 CRITICAL"), ("SC-04", "Agent opens 120 unassigned customers", "70 HIGH"),
        ("SC-06", "MFA fatigue + StopLogging", "100 CRITICAL"), ("SC-07", "Marketing reads KYC without consent", "70 HIGH"),
        ("SC-08", "Bank account changed, Rs 4.8 lakh disbursed", "65 HIGH"), ("SC-09", "KYC bucket made public", "45 MEDIUM"),
        ("SC-02", "Nightly registry job in its window", "30 quiet"), ("SC-03", "Auditor within approved ticket", "30 quiet")]
for i, (a, b, c) in enumerate(rows):
    y = 1.8 + i * 0.55
    text(s, 0.6, y, 1.2, 0.5, a, size=15, color=NAVY, bold=True)
    text(s, 1.8, y, 5.8, 0.5, b, size=15)
    col = RED if "CRITICAL" in c else ORANGE if "HIGH" in c else AMBER if "MEDIUM" in c else TEAL
    text(s, 7.4, y, 2.0, 0.5, c, size=15, color=col, bold=True)
card(s, 9.6, 1.8, 3.1, 4.4)
text(s, 9.8, 2.0, 2.8, 4.0, [("11 / 11", NAVY, True, 44), ("scenarios correct", MUTED, False, 14),
                              ("0", TEAL, True, 44), ("false alerts on 7 normal days", MUTED, False, 14)])

# 7 Compliance map
s = slide("DPDP-aligned readiness and controls", "Compliance map",
          "Every clause on this slide was checked against the official text on 20 Nov 2026 (docs/regulations/). "
          "We never claim DPDP compliance. The consent component is a consent ledger.")
cm = [("DPDP Act s.8(5)", "Security safeguards", "Detection, containment, sealed evidence"),
      ("DPDP Rules r.6(1)(c),(e)", "Logs, monitoring, 1-year retention", "CloudTrail, Object Lock evidence"),
      ("DPDP Rules r.7(2)(b)", "Board detailed report, 72 h", "Timer + DPB draft"),
      ("DPDP Act s.6(1)", "Purpose-specific consent", "Consent ledger, signal S9"),
      ("RBI NBFC Credit Facilities Ch. III, 13(1), 14(4)", "Consent with audit trail; data in India", "Consent ledger; ap-south-1"),
      ("RBI NBFC Cybersecurity Dir. para 141", "RBI report within 6 h of detection", "Timer + RBI draft"),
      ("CERT-In Direction (ii), (iv)", "6 h report; 180-day logs in India", "Timer + CERT-In draft; logs in Mumbai")]
for i, (a, b, c) in enumerate(cm):
    y = 1.75 + i * 0.6
    text(s, 0.6, y, 4.4, 0.55, a, size=13, color=NAVY, bold=True)
    text(s, 5.0, y, 3.8, 0.55, b, size=13)
    text(s, 8.8, y, 4.0, 0.55, c, size=13, color=TEAL)
text(s, 0.6, 6.0, 12, 0.6, "TODO Roopak: SOC 2 and ISO 27001-aligned control rows", size=14, color=TODO, bold=True)

# 8 Business case and roadmap
s = slide("Business case and roadmap", "Business",
          "Buyers: NBFCs, digital lenders and their lending service partners. Price tiers are a DRAFT for team review. "
          "AWS cost per million events comes from Ajay.")
tiers = [("Starter", "TODO price", "1 AWS account · up to N M events/month · email alerts"),
         ("Growth", "TODO price", "Multi-account · containment LIVE · report drafts"),
         ("Enterprise", "TODO price", "LSP monitoring · custom rules · audit exports")]
for i, (h, p, b) in enumerate(tiers):
    x = 0.6 + i * 4.1
    card(s, x, 1.8, 3.8, 2.6)
    text(s, x + 0.3, 1.95, 3.3, 0.5, h, size=20, color=NAVY, bold=True)
    text(s, x + 0.3, 2.5, 3.3, 0.5, p, size=18, color=TODO, bold=True)
    text(s, x + 0.3, 3.1, 3.3, 1.2, b, size=13)
text(s, 0.6, 4.6, 12, 0.5, "AWS cost to run: TODO Ajay, Rs/$ per million events", size=18, color=TODO, bold=True)
text(s, 0.6, 5.2, 12, 1.4, [
    ("Roadmap", NAVY, True, 16),
    ("Erasure tracking (DPDP s.8(7)) · more lender types (banks, co-op banks) · multi-account org rollout · real DAKSH / CERT-In form export", INK, False, 14)])

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print("wrote", OUT)
