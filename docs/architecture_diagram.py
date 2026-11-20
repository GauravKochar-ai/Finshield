import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

out = sys.argv[1]
fig, ax = plt.subplots(figsize=(16, 9), dpi=150)
ax.set_xlim(0, 160); ax.set_ylim(0, 90); ax.axis("off")
fig.patch.set_facecolor("white")

C = {"src": "#E8F0FE", "bus": "#FDE7D3", "fn": "#FFF4D6", "data": "#E3F4E8",
     "ai": "#EFE6FB", "web": "#E6F4F7", "edge": "#37474F"}

def box(x, y, w, h, title, sub="", color="fn"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.5",
                                fc=C[color], ec="#546E7A", lw=1.2))
    ax.text(x + w / 2, y + h / 2 + (1.6 if sub else 0), title, ha="center", va="center",
            fontsize=10.5, weight="bold", color="#1F2933")
    if sub:
        ax.text(x + w / 2, y + h / 2 - 2.2, sub, ha="center", va="center", fontsize=8, color="#455A64")
    return (x, y, w, h)

def arrow(a, b, label="", side="r2l", dash=False):
    ax_, ay, aw, ah = a; bx, by, bw, bh = b
    if side == "r2l":
        p, q = (ax_ + aw + 0.5, ay + ah / 2), (bx - 0.5, by + bh / 2)
    elif side == "t2b":
        p, q = (ax_ + aw / 2, ay - 0.5), (bx + bw / 2, by + bh + 0.5)
    elif side == "b2t":
        p, q = (ax_ + aw / 2, ay + ah + 0.5), (bx + bw / 2, by - 0.5)
    else:
        p, q = (ax_ - 0.5, ay + ah / 2), (bx + bw + 0.5, by + bh / 2)
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=12, lw=1.2,
                                 color=C["edge"], linestyle="--" if dash else "-"))
    if label:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + 1.3, label, ha="center", fontsize=7.5,
                color="#37474F", bbox=dict(fc="white", ec="none", pad=0.5))

# Region frame
ax.add_patch(FancyBboxPatch((2, 2), 156, 80, boxstyle="round,pad=0.5,rounding_size=2",
                            fc="none", ec="#90A4AE", lw=1.5, ls="--"))
ax.text(4, 80, "AWS account  ·  ap-south-1 (Mumbai)  ·  data stays in India", fontsize=10,
        color="#546E7A", va="top", weight="bold")
ax.text(80, 87, "FinShield AI: architecture", ha="center", fontsize=16, weight="bold", color="#1F2933")

# Sources
ct = box(6, 58, 22, 10, "CloudTrail", "mgmt + S3 data events (KYC)", "src")
cf = box(6, 44, 22, 10, "AWS Config", "3 managed rules", "src")
gd = box(6, 30, 22, 10, "GuardDuty", "findings", "src")
sim = box(6, 14, 22, 10, "Simulator Lambda", "replays SC-01..SC-10", "src")

bus = box(36, 30, 18, 38, "EventBridge", "finshield-dev-bus", "bus")
for s in (ct, cf, gd, sim):
    arrow(s, bus)

norm = box(62, 56, 22, 10, "normalizer", "Lambda → unified event", "fn")
det = box(62, 40, 22, 10, "detection", "Lambda · scores S1–S11", "fn")
arrow(bus, norm, "raw events")
arrow(norm, det, side="t2b")

ddb = box(62, 14, 22, 14, "DynamoDB", "Events · Alerts · Baselines\nConsent ledger · Approvals", "data")
arrow(det, ddb, side="t2b")

sfn = box(94, 40, 24, 12, "Step Functions", "finshield-dev-incident", "fn")
arrow(det, sfn, "alert.raised")

cont = box(94, 58, 24, 14, "Containment Lambdas",
           "revoke sessions · deactivate keys\nbucket deny · DNS block · release", "fn")
arrow(sfn, cont, side="b2t")

bed = box(126, 58, 28, 14, "Amazon Bedrock", "Converse, temp 0\n+ Guardrail (PII, Aadhaar, PAN)", "ai")
arrow(sfn, bed, "explain + report drafts")

ev = box(126, 40, 28, 12, "S3 Object Lock", "evidence chain (compliance mode)", "data")
arrow(sfn, ev, "seal")

sns = box(126, 24, 28, 10, "SNS", "alert email", "data")
arrow(sfn, sns)

api = box(94, 16, 24, 14, "HTTP API + Cognito", "JWT authorizer · /v1\nread + decision API", "web")
arrow(api, ddb, side="l2r")
arrow(api, sfn, "decision token", side="b2t", dash=True)

web = box(126, 6, 28, 12, "CloudFront web app", "Next.js static export (S3)", "web")
ax.add_patch(FancyArrowPatch((126, 12), (118.5, 20), arrowstyle="-|>", mutation_scale=12,
                             lw=1.2, color=C["edge"]))

ax.text(4, 4.5, "Code computes every score, severity and count. Bedrock only writes words, validated against contract schemas.",
        fontsize=8.5, color="#546E7A", style="italic")

plt.savefig(out, bbox_inches="tight", facecolor="white")
print("wrote", out)
