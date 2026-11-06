"""Creates sample binary files (an off-brand banner image and a small PDF) for demos and tests.
Run:  python scripts/make_sample_assets.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "data" / "sample" / "content"
OUT.mkdir(parents=True, exist_ok=True)

# 1) Banner: small, odd shape, off-brand pink background, with a bold claim in the picture
img = Image.new("RGB", (640, 300), "#E91E8C")
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
except OSError:
    font = ImageFont.load_default()
d.text((30, 60), "Best price in India!", fill="white", font=font)
d.text((30, 150), "Lumio Invoice from Rs. 399", fill="white", font=font)
img.save(OUT / "banner.png")

# 2) PDF brief with a wrong number
c = canvas.Canvas(str(OUT / "product_brief.pdf"), pagesize=A4)
c.setFont("Helvetica", 12)
y = 780
for line in ["Lumio Invoice product brief", "",
             "Lumio Invoice is used by 15,000+ customers across India.",
             "Uptime is 99.99% and support is available 24x7.",
             "The Pro plan costs Rs. 1,299 per month. Terms apply."]:
    c.drawString(60, y, line)
    y -= 22
c.save()
print("created", [p.name for p in OUT.iterdir()])
