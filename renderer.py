"""Shared invoice layout drawn onto either a PDF (reportlab) or a PNG (Pillow).

The layout is written once in `render_invoice` using top-down point
coordinates (US Letter, 612 x 792). Two small adapters turn those calls into
PDF pages or PNG images, so the exports always match each other.
"""
import os

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

INK = "#1E293B"
GRAY = "#475569"
MUTED = "#64748B"
RULE = "#E2E8F0"


# ---------------------------------------------------------------- formatting
def fmt_qty(q):
    """2.0 -> '2', 2.5 -> '2.5', 1234.567 -> '1234.57'."""
    q = float(q)
    if q == int(q):
        return str(int(q))
    return f"{q:.2f}".rstrip("0").rstrip(".")


def money(currency, amount):
    amount = float(amount)
    sign = "-" if amount < 0 else ""
    return f"{sign}{currency}{abs(amount):,.2f}"


# --------------------------------------------------------------------- fonts
_FONT_PAIRS = [
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
]


def find_font_pair():
    for regular, bold in _FONT_PAIRS:
        if os.path.isfile(regular) and os.path.isfile(bold):
            return regular, bold
    return None


_PAIR = find_font_pair()
_RL_REGULAR, _RL_BOLD = "Helvetica", "Helvetica-Bold"
if _PAIR:
    try:
        pdfmetrics.registerFont(TTFont("InvoiceRegular", _PAIR[0]))
        pdfmetrics.registerFont(TTFont("InvoiceBold", _PAIR[1]))
        _RL_REGULAR, _RL_BOLD = "InvoiceRegular", "InvoiceBold"
    except Exception:  # unreadable font file: fall back to built-ins
        _RL_REGULAR, _RL_BOLD = "Helvetica", "Helvetica-Bold"


# ------------------------------------------------------------------ adapters
class BaseRenderer:
    W = 612
    H = 792

    def width(self, text, size, bold=False):
        raise NotImplementedError

    def wrap(self, text, size, bold, max_width):
        """Greedy word wrap that respects explicit newlines."""
        lines = []
        for paragraph in str(text).split("\n"):
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                trial = f"{current} {word}"
                if self.width(trial, size, bold) <= max_width:
                    current = trial
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines


class PdfRenderer(BaseRenderer):
    def __init__(self, path):
        self.c = rl_canvas.Canvas(path, pagesize=(self.W, self.H))
        self.c.setTitle(os.path.splitext(os.path.basename(path))[0])

    def _font(self, bold):
        return _RL_BOLD if bold else _RL_REGULAR

    def width(self, text, size, bold=False):
        return pdfmetrics.stringWidth(text, self._font(bold), size)

    def text(self, x, y, s, size=10, bold=False, color=INK, align="left"):
        c = self.c
        c.setFont(self._font(bold), size)
        c.setFillColor(HexColor(color))
        if align == "right":
            c.drawRightString(x, self.H - y, s)
        else:
            c.drawString(x, self.H - y, s)

    def line(self, x1, y, x2, width=1, color=RULE):
        self.c.setStrokeColor(HexColor(color))
        self.c.setLineWidth(width)
        self.c.line(x1, self.H - y, x2, self.H - y)

    def image(self, path, x, y, w, h):
        try:
            self.c.drawImage(ImageReader(path), x, self.H - y - h, w, h,
                             preserveAspectRatio=True, anchor="nw", mask="auto")
            return True
        except Exception:
            return False

    def new_page(self):
        self.c.showPage()

    def finish(self):
        self.c.save()


class PngRenderer(BaseRenderer):
    def __init__(self, scale=2.78):  # ~1700 px wide
        self.s = scale
        self.pages = []
        self._fonts = {}
        self.new_page()

    def new_page(self):
        img = Image.new("RGB", (round(self.W * self.s), round(self.H * self.s)), "white")
        self.pages.append(img)
        self.draw = ImageDraw.Draw(img)

    def _font(self, size, bold):
        key = (size, bold)
        if key not in self._fonts:
            px = max(1, round(size * self.s))
            font = None
            if _PAIR:
                try:
                    font = ImageFont.truetype(_PAIR[1] if bold else _PAIR[0], px)
                except OSError:
                    font = None
            if font is None:
                try:
                    font = ImageFont.load_default(px)
                except TypeError:
                    font = ImageFont.load_default()
            self._fonts[key] = font
        return self._fonts[key]

    def width(self, text, size, bold=False):
        return self._font(size, bold).getlength(text) / self.s

    def text(self, x, y, s, size=10, bold=False, color=INK, align="left"):
        font = self._font(size, bold)
        anchor = "rs" if align == "right" else "ls"
        try:
            self.draw.text((x * self.s, y * self.s), s, font=font, fill=color, anchor=anchor)
        except (ValueError, TypeError):  # bitmap fallback font has no anchors
            px = x * self.s - (font.getlength(s) if align == "right" else 0)
            self.draw.text((px, y * self.s - size * self.s), s, font=font, fill=color)

    def line(self, x1, y, x2, width=1, color=RULE):
        self.draw.line([(x1 * self.s, y * self.s), (x2 * self.s, y * self.s)],
                       fill=color, width=max(1, round(width * self.s)))

    def image(self, path, x, y, w, h):
        try:
            with Image.open(path) as src:
                logo = src.convert("RGBA")
            logo.thumbnail((round(w * self.s), round(h * self.s)))
            self.pages[-1].paste(logo, (round(x * self.s), round(y * self.s)), logo)
            return True
        except Exception:
            return False

    def finish(self, path):
        """Save page 1 to `path`; extra pages get _2, _3... suffixes."""
        root, ext = os.path.splitext(path)
        paths = []
        for i, page in enumerate(self.pages, start=1):
            target = path if i == 1 else f"{root}_{i}{ext}"
            fmt = "JPEG" if ext.lower() in (".jpg", ".jpeg") else "PNG"
            page.save(target, fmt)
            paths.append(target)
        return paths


# -------------------------------------------------------------------- layout
def render_invoice(r, d, totals, color):
    W, H, M = r.W, r.H, 48
    cur = d.get("currency", "$")
    items = d.get("items", [])
    qty_r, rate_r, amt_r = W - M - 175, W - M - 95, W - M
    desc_w = qty_r - 55 - M

    # ---- header: sender (left) and title (right)
    y = M
    left_y = y
    logo = d.get("logo_path")
    if logo and os.path.isfile(logo) and r.image(logo, M, y, 54, 54):
        left_y = y + 68
    if d.get("sender_name"):
        left_y += 14
        r.text(M, left_y, d["sender_name"], 18, True, INK)
    for block in (d.get("sender_address", ""), d.get("sender_email", "")):
        for line in r.wrap(block, 10, False, 280) if block else []:
            left_y += 14
            r.text(M, left_y, line, 10, False, GRAY)
    r.text(W - M, y + 26, "INVOICE", 28, True, color, "right")
    r.text(W - M, y + 44, d.get("inv_number", ""), 10, False, MUTED, "right")
    y = max(left_y, y + 44) + 38

    # ---- bill to (left) and details (right)
    r.text(M, y, "BILL TO", 8.5, True, MUTED)
    by = y + 16
    if d.get("recipient_name"):
        r.text(M, by, d["recipient_name"], 12, True, INK)
        by += 14
    for key in ("recipient_addr1", "recipient_addr2"):
        if d.get(key):
            r.text(M, by, d[key], 10, False, GRAY)
            by += 14

    due = d.get("inv_due", "")
    if d.get("due_message"):
        due = f"{due} ({d['due_message']})" if due else d["due_message"]
    rows = [("Date:", d.get("inv_date", "")), ("Due Date:", due)]
    if d.get("inv_project"):
        rows.append(("Project:", d["inv_project"]))
    max_w = max(r.width(v, 10, False) for _, v in rows)
    label_x = W - M - max_w - 14
    r.text(W - M, y, "DETAILS", 8.5, True, MUTED, "right")
    dy = y + 16
    for label, value in rows:
        r.text(label_x, dy, label, 10, False, GRAY, "right")
        r.text(W - M, dy, value, 10, False, INK, "right")
        dy += 15
    y = max(by, dy) + 26

    # ---- items table
    def table_header(top):
        r.text(M, top, "Description", 10, True, INK)
        r.text(qty_r, top, "Qty", 10, True, INK, "right")
        r.text(rate_r, top, "Rate", 10, True, INK, "right")
        r.text(amt_r, top, "Amount", 10, True, INK, "right")
        r.line(M, top + 8, W - M, 1.6, INK)
        return top + 27

    y = table_header(y)
    for item in items:
        lines = r.wrap(item.get("desc", ""), 10, True, desc_w) or [""]
        item_date = (item.get("date") or "").strip()
        extra = 1 if item_date else 0  # optional date line under the description
        row_h = 13 * (len(lines) - 1 + extra) + 26
        if y + row_h > H - M:
            r.new_page()
            y = table_header(M)
        for i, line in enumerate(lines):
            r.text(M, y + 13 * i, line, 10, True, INK)
        if item_date:
            r.text(M, y + 13 * len(lines), item_date, 9, False, MUTED)
        amount = item["qty"] * item["rate"]
        r.text(qty_r, y, fmt_qty(item["qty"]), 10, False, INK, "right")
        r.text(rate_r, y, money(cur, item["rate"]), 10, False, INK, "right")
        r.text(amt_r, y, money(cur, amount), 10, False, INK, "right")
        r.line(M, y + 13 * (len(lines) - 1 + extra) + 10, W - M, 0.6, RULE)
        y += row_h

    # ---- notes (left) and totals (right)
    notes_x_max = W - M - 190 - 30
    notes_lines = r.wrap(d.get("notes", ""), 10, False, notes_x_max - M) if d.get("notes") else []
    needed = max(110, 24 + 14 * len(notes_lines))
    if y + needed > H - M:
        r.new_page()
        y = M
    y += 12
    if notes_lines:
        r.text(M, y, "NOTES & PAYMENT INSTRUCTIONS", 8.5, True, MUTED)
        for i, line in enumerate(notes_lines):
            r.text(M, y + 18 + 14 * i, line, 10, False, GRAY)

    tx = W - M - 190
    discount = totals["discount"]
    pct = d.get("tax_percent", 0)
    pct_text = f"{pct:g}"
    total_rows = [
        ("Subtotal", money(cur, totals["subtotal"])),
        ("Discount", f"-{money(cur, discount)}" if discount > 0 else money(cur, 0)),
        (f"Tax ({pct_text}%)", money(cur, totals["tax"])),
    ]
    ty = y
    for label, value in total_rows:
        r.text(tx, ty, label, 10, False, GRAY)
        r.text(W - M, ty, value, 10, False, INK, "right")
        ty += 18
    r.line(tx, ty - 6, W - M, 0.8, RULE)
    ty += 12
    r.text(tx, ty, "Total", 14, True, INK)
    r.text(W - M, ty, money(cur, totals["total"]), 15, True, color, "right")


def export_pdf(path, d, totals, color):
    r = PdfRenderer(path)
    render_invoice(r, d, totals, color)
    r.finish()


def export_image(path, d, totals, color):
    r = PngRenderer()
    render_invoice(r, d, totals, color)
    return r.finish(path)
