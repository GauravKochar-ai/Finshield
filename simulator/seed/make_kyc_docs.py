#!/usr/bin/env python3
"""Make synthetic KYC document images for the FinShield demo (owner: Roopak).

Every image is clearly fake:
  * diagonal watermark "SAMPLE - NOT A VALID DOCUMENT" plus "SAMPLE" in a corner
  * plain header ("SAMPLE IDENTITY CARD - PAN (synthetic)"); no State Emblem, no UIDAI or
    Income Tax Department logos, no holograms, no QR codes
  * grey silhouette instead of a photo (no real people)
  * names, dates of birth and father's names from Faker (en_IN); PAN values SAMPL0001A ...

Document set (default, 200 files):
  C-10001..C-10080  PAN                                  80
  C-10081..C-10160  AADHAAR, masked (XXXX XXXX 1234)     80
  C-10161..C-10170  AADHAAR, FULL 12-digit number         10  <- deliberate: FinShield must flag these.
                    Numbers start with 0; real Aadhaar numbers never start with 0 or 1.
  C-10171..C-10200  SELFIE                               30

--bulk adds small copies up to C-11200 (1,200 files total) with the same naming.
The 10 full-number Aadhaar cards stay the only unmasked ones.

Output (sync this folder to s3://finshield-dev-kyc-docs/kyc/):
  simulator/seed/kyc-docs/<customer_id>/KYC-<DOC>-<customer_id>.png
  simulator/seed/kyc-docs/manifest.csv
S3 key the backend parses:  kyc/<customer_id>/KYC-<DOC>-<customer_id>.png   (DOC = PAN | AADHAAR | SELFIE)

Reruns are identical: fixed seeds, and Pillow's built-in font (no system fonts).
If manifest.csv already exists, its names, PANs and Aadhaar last-4 are reused, so the
images always match the manifest the seed data was loaded from. Use --fresh to start over.

Usage:
  python3 simulator/seed/make_kyc_docs.py            # 200 files + manifest
  python3 simulator/seed/make_kyc_docs.py --bulk     # 1,200 files (P1, volume)
  python3 simulator/seed/make_kyc_docs.py --fresh    # ignore the existing manifest
Requires: pip install pillow faker
"""
import argparse
import csv
import io
import math
import random
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SEED = 20261120
HERE = Path(__file__).resolve().parent
OUT = HERE / "kyc-docs"
MANIFEST = OUT / "manifest.csv"
COLUMNS = ["file_id", "customer_id", "doc_type", "s3_key", "size_kb",
           "aadhaar_last4", "pan_fake", "unmasked_aadhaar", "synthetic_name"]

FIRST_ID = 10001
STANDARD = 200
BULK = 1200
W, H = 1000, 630              # standard size
BULK_W, BULK_H = 500, 315     # small copies for volume

WATERMARK = "SAMPLE - NOT A VALID DOCUMENT"
HEADERS = {
    "PAN": "SAMPLE IDENTITY CARD - PAN (synthetic)",
    "AADHAAR": "SAMPLE IDENTITY CARD - AADHAAR (synthetic)",
    "SELFIE": "SAMPLE SELFIE - NOT A REAL PERSON (synthetic)",
}
COLOURS = {  # header colour, background
    "PAN": ((54, 69, 99), (238, 241, 247)),
    "AADHAAR": ((70, 90, 70), (240, 245, 238)),
    "SELFIE": ((90, 90, 100), (236, 236, 240)),
}


# --------------------------------------------------------------- doc plan
def doc_for(n):
    """n = 1-based position. Returns (doc_type, unmasked)."""
    if n <= 80:
        return "PAN", False
    if n <= 160:
        return "AADHAAR", False
    if n <= 170:
        return "AADHAAR", True
    if n <= 200:
        return "SELFIE", False
    return ("PAN", "AADHAAR", "SELFIE")[(n - 201) % 3], False      # bulk: masked only


def customer_id(n):
    return f"C-{FIRST_ID + n - 1}"


def s3_key(cid, doc):
    return f"kyc/{cid}/KYC-{doc}-{cid}.png"


# --------------------------------------------------------------- people
def make_people(count, previous):
    """Names / DOB / father / address per customer. Names, PAN and last-4 come from the
    existing manifest when present, so images and seed data stay in step."""
    try:
        from faker import Faker
    except ImportError:
        sys.exit("Faker is missing: pip install faker")
    people = []
    for n in range(1, count + 1):
        cid = customer_id(n)
        doc, unmasked = doc_for(n)
        rnd = random.Random(f"{SEED}-{cid}")          # stable per customer
        fake = Faker("en_IN")
        fake.seed_instance(f"{SEED}-{cid}")
        gender = rnd.choice(["Male", "Female"])
        first = fake.first_name_male() if gender == "Male" else fake.first_name_female()
        name = f"{first} {fake.last_name()}"
        father = f"{fake.first_name_male()} {fake.last_name()}"
        dob = fake.date_of_birth(minimum_age=21, maximum_age=65).strftime("%d/%m/%Y")
        address = f"{rnd.randint(1, 250)}, {fake.street_name()}, {fake.city()}, {fake.state()} {fake.postcode()}"
        last4 = f"{rnd.randint(0, 9999):04d}"
        pan = f"SAMPL{n:04d}A"

        old = previous.get(cid)
        if old:
            name = old["synthetic_name"] or name
            pan = old["pan_fake"] or pan
            last4 = old["aadhaar_last4"] or last4

        full_aadhaar = None
        if doc == "AADHAAR" and unmasked:
            middle = "".join(str(rnd.randint(0, 9)) for _ in range(7))
            digits = "0" + middle + last4                      # 12 digits, starts with 0
            full_aadhaar = f"{digits[:4]} {digits[4:8]} {digits[8:]}"

        people.append({
            "n": n, "customer_id": cid, "doc": doc, "unmasked": unmasked, "name": name,
            "father": father, "dob": dob, "gender": gender, "address": address,
            "pan": pan, "last4": last4 if doc == "AADHAAR" else "", "full_aadhaar": full_aadhaar,
        })
    return people


# --------------------------------------------------------------- drawing
def font(size):
    return ImageFont.load_default(size=size)       # Pillow's bundled font: same output on every OS


def wrap(draw, text, fnt, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=fnt) <= width:
            line = test
        else:
            lines.append(line)
            line = w
    lines.append(line)
    return lines


def silhouette(img, box, s):
    """Grey head-and-shoulders placeholder, clipped to its frame. No real person."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    tile = Image.new("RGBA", (w, h), (200, 200, 205, 255))
    d = ImageDraw.Draw(tile)
    cx, r = w // 2, int(w * 0.20)
    head_cy = int(h * 0.36)
    d.ellipse([cx - r, head_cy - r, cx + r, head_cy + r], fill=(150, 150, 158))
    d.chord([int(w * 0.12), int(h * 0.62), w - int(w * 0.12), h + int(h * 0.45)], 180, 360, fill=(150, 150, 158))
    img.paste(tile, (x0, y0))
    ImageDraw.Draw(img).rectangle(box, outline=(120, 120, 128), width=max(1, int(3 * s)))


def watermark(img, s):
    w, h = img.size
    layer = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    fnt = font(int(58 * s))
    tw = d.textlength(WATERMARK, font=fnt)
    for i, dy in enumerate(range(-int(h * 0.5), int(h * 1.5), int(190 * s))):
        d.text(((w * 2 - tw) / 2, h / 2 + dy), WATERMARK, font=fnt, fill=(200, 30, 30, 70))
    layer = layer.rotate(25, resample=Image.BICUBIC)
    layer = layer.crop((w // 2, h // 2, w // 2 + w, h // 2 + h))
    img.alpha_composite(layer)
    # corner badge
    d = ImageDraw.Draw(img)
    bf = font(int(30 * s))
    pad = int(10 * s)
    bw = d.textlength("SAMPLE", font=bf) + 2 * pad
    bx, by = w - bw - int(14 * s), h - int(58 * s)
    d.rectangle([bx, by, bx + bw, by + int(44 * s)], fill=(200, 30, 30, 255))
    d.text((bx + pad, by + int(6 * s)), "SAMPLE", font=bf, fill=(255, 255, 255, 255))


def render(p, size):
    w, h = size
    s = w / W
    head, bg = COLOURS[p["doc"]]
    img = Image.new("RGBA", (w, h), bg + (255,))
    d = ImageDraw.Draw(img)

    # header bar (plain text only - no emblem, no logos)
    d.rectangle([0, 0, w, int(78 * s)], fill=head)
    d.text((int(28 * s), int(22 * s)), HEADERS[p["doc"]], font=font(int(32 * s)), fill=(255, 255, 255))
    d.text((int(28 * s), int(92 * s)), f"Customer {p['customer_id']}  |  synthetic test data for FinShield",
           font=font(int(20 * s)), fill=(90, 90, 90))

    label, value = font(int(20 * s)), font(int(30 * s))
    x, y = int(300 * s), int(140 * s)

    def field(lab, val, big=False):
        nonlocal y, x
        d.text((x, y), lab, font=label, fill=(100, 100, 100))
        y += int(24 * s)
        fv = font(int(44 * s)) if big else value
        right = int(530 * s) if p["doc"] == "SELFIE" else w - int(40 * s)
        for line in wrap(d, val, fv, right - x):
            d.text((x, y), line, font=fv, fill=(20, 20, 20))
            y += int((52 if big else 36) * s)
        y += int(12 * s)

    if p["doc"] == "SELFIE":
        silhouette(img, (int(560 * s), int(130 * s), int(900 * s), int(560 * s)), s)
        x = int(40 * s)
        field("Name on file", p["name"])
        field("Photo", "Placeholder silhouette - no real person")
    else:
        silhouette(img, (int(40 * s), int(140 * s), int(260 * s), int(420 * s)), s)
        field("Name", p["name"])
        if p["doc"] == "PAN":
            field("Father's name", p["father"])
            field("Date of birth", p["dob"])
            field("PAN (fake format)", p["pan"], big=True)
        else:
            field("Date of birth / Gender", f"{p['dob']}  /  {p['gender']}")
            field("Address", p["address"])
            number = p["full_aadhaar"] if p["unmasked"] else f"XXXX XXXX {p['last4']}"
            field("Aadhaar number (synthetic)", number, big=True)

    watermark(img, s)
    return img.convert("RGB").quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


# --------------------------------------------------------------- main
def load_previous():
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(newline="", encoding="utf-8") as f:
        return {r["customer_id"]: r for r in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bulk", action="store_true", help="1,200 files up to C-11200 (extra files are small copies)")
    ap.add_argument("--fresh", action="store_true", help="ignore the existing manifest.csv")
    a = ap.parse_args()

    count = BULK if a.bulk else STANDARD
    previous = {} if a.fresh else load_previous()
    people = make_people(count, previous)

    for old in OUT.glob("C-*"):                 # remove images from earlier runs
        if old.is_dir():
            shutil.rmtree(old)

    rows, biggest = [], 0
    for p in people:
        size = (W, H) if p["n"] <= STANDARD else (BULK_W, BULK_H)
        key = s3_key(p["customer_id"], p["doc"])
        path = OUT / key.removeprefix("kyc/")
        path.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        render(p, size).save(buf, format="PNG", optimize=True)
        path.write_bytes(buf.getvalue())
        kb = math.ceil(len(buf.getvalue()) / 1024)      # whole KB, rounded up (seed loader expects an int)
        biggest = max(biggest, kb)
        rows.append({
            "file_id": f"KYC-{p['doc']}-{p['customer_id']}",
            "customer_id": p["customer_id"],
            "doc_type": p["doc"],
            "s3_key": key,
            "size_kb": kb,
            "aadhaar_last4": p["last4"],
            "pan_fake": p["pan"],
            "unmasked_aadhaar": "true" if p["unmasked"] else "false",
            "synthetic_name": p["name"],
        })

    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for r in rows:
        k = r["doc_type"] + (" (FULL number)" if r["unmasked_aadhaar"] == "true" else "")
        counts[k] = counts.get(k, 0) + 1
    print(f"{len(rows)} images in {OUT}")
    print("  " + ", ".join(f"{k}: {v}" for k, v in counts.items()))
    print(f"  largest file: {biggest} KB")
    print(f"manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
