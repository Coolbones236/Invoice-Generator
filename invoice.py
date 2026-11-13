"""Invoice data model, totals, persistence and export (no GUI imports)."""
import copy
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

import renderer
from renderer import fmt_qty, money  # re-exported for the GUI

TONES = {
    "Work": {"color": "#1D4ED8", "hover": "#1E40AF", "badge_bg": "#DBEAFE",
             "notes": "Please include the invoice number on your check\nor wire transfer."},
    "School": {"color": "#0F766E", "hover": "#115E59", "badge_bg": "#CCFBF1",
               "notes": "Include student ID on all correspondence."},
    "Personal": {"color": "#9333EA", "hover": "#7E22CE", "badge_bg": "#F3E8FF",
                 "notes": "Thanks! Let me know if you have any questions."},
}

CURRENCIES = ["$", "€", "£", "¥"]

DEFAULT_SETTINGS = {
    "currency": "$",
    "appearance": "light",          # light | dark | system
    "number_prefix": "INV-",
    "next_number": 1,
    "export_png_with_pdf": True,
    "sender": {"sender_name": "", "sender_email": "", "sender_address": "", "logo_path": ""},
    "clients": [],                  # [{"name", "addr1", "addr2"}]
}

TEXT_KEYS = [
    "logo_path", "sender_name", "sender_email", "sender_address",
    "recipient_name", "recipient_addr1", "recipient_addr2",
    "inv_date", "inv_due", "due_message", "inv_project", "inv_number", "currency",
]


# ------------------------------------------------------------------- helpers
def to_float(value, default=None):
    """Parse '1,234.50', '$12', '€ 3' etc. Returns `default` if not a number."""
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else default
    cleaned = re.sub(r"[^\d.\-]", "", str(value or ""))
    if cleaned in ("", "-", ".", "-."):
        return default
    try:
        number = float(cleaned)
    except ValueError:
        return default
    return number if math.isfinite(number) else default


def format_date(d):
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def parse_date(text):
    from datetime import datetime
    text = (text or "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d", "%m %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _atomic_write_json(path, payload):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _dec(x):
    return Decimal(str(x))


def _cents(x):
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------- backend
class InvoiceBackend:
    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.join(os.path.expanduser("~"), "InvoiceGenerator")
        self.json_dir = os.path.join(self.base_dir, "drafts")
        self.pdf_dir = os.path.join(self.base_dir, "pdf")
        self.image_dir = os.path.join(self.base_dir, "images")
        for folder in (self.json_dir, self.pdf_dir, self.image_dir):
            os.makedirs(folder, exist_ok=True)
        self.settings_path = os.path.join(self.base_dir, "settings.json")

        self.settings = self._load_settings()
        self.trash_bin = []  # [{"desc", "qty", "rate"}]
        self.data = self.new_invoice_data()

    # ---- settings -------------------------------------------------------
    def _load_settings(self):
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        try:
            with open(self.settings_path, encoding="utf-8") as fh:
                saved = json.load(fh)
            for key, default in DEFAULT_SETTINGS.items():
                if key in saved and isinstance(saved[key], type(default)):
                    settings[key] = saved[key]
            if settings["currency"] not in CURRENCIES:
                settings["currency"] = "$"
            if settings["appearance"] not in ("light", "dark", "system"):
                settings["appearance"] = "light"
            settings["next_number"] = max(1, int(settings["next_number"]))
        except (OSError, ValueError, TypeError):
            pass
        return settings

    def save_settings(self):
        _atomic_write_json(self.settings_path, self.settings)

    # ---- invoice numbers ------------------------------------------------
    def suggested_number(self):
        return f"{self.settings['number_prefix']}{self.settings['next_number']:04d}"

    def mark_number_used(self):
        """Advance the counter if the current invoice used the suggested number."""
        if self.data.get("inv_number") == self.suggested_number():
            self.settings["next_number"] += 1
            self.save_settings()

    # ---- data -----------------------------------------------------------
    def new_invoice_data(self):
        today = date.today()
        sender = self.settings["sender"]
        return {
            "logo_path": sender.get("logo_path", ""),
            "sender_name": sender.get("sender_name", ""),
            "sender_email": sender.get("sender_email", ""),
            "sender_address": sender.get("sender_address", ""),
            "recipient_name": "",
            "recipient_addr1": "",
            "recipient_addr2": "",
            "inv_date": format_date(today),
            "inv_due": format_date(today + timedelta(days=30)),
            "due_message": "Net 30",
            "inv_project": "",
            "inv_number": self.suggested_number(),
            "currency": self.settings["currency"],
            "tone": "Work",
            "tax_percent": 0.0,
            "discount_amount": 0.0,
            "notes": TONES["Work"]["notes"],
            "items": [{"desc": "", "qty": 1.0, "rate": 0.0, "date": ""}],
        }

    def reset_invoice(self):
        self.data = self.new_invoice_data()
        return self.data

    def remember_sender(self):
        """Keep sender details so the next invoice starts pre-filled."""
        keys = ("sender_name", "sender_email", "sender_address", "logo_path")
        self.settings["sender"] = {k: self.data.get(k, "") for k in keys}
        self.save_settings()

    def _clean(self, raw):
        """Merge arbitrary loaded data onto defaults, coercing types."""
        base = self.new_invoice_data()
        if not isinstance(raw, dict):
            raise ValueError("Draft file does not contain an invoice.")
        for key in TEXT_KEYS:
            if key in raw and raw[key] is not None:
                base[key] = str(raw[key])
        if base["currency"] not in CURRENCIES:
            base["currency"] = self.settings["currency"]
        if raw.get("tone") in TONES:
            base["tone"] = raw["tone"]
        if "notes" in raw:
            base["notes"] = str(raw["notes"] or "")
        base["tax_percent"] = max(0.0, to_float(raw.get("tax_percent"), 0.0))
        base["discount_amount"] = max(0.0, to_float(raw.get("discount_amount"), 0.0))
        items = []
        for entry in raw.get("items", []) if isinstance(raw.get("items"), list) else []:
            if isinstance(entry, dict):
                items.append({
                    "desc": str(entry.get("desc", "")),
                    "date": str(entry.get("date") or ""),
                    "qty": to_float(entry.get("qty"), 0.0),
                    "rate": to_float(entry.get("rate"), 0.0),
                })
        base["items"] = items
        return base

    def save_draft(self, filepath):
        _atomic_write_json(filepath, self.data)
        self.remember_sender()

    def load_draft(self, filepath):
        try:
            with open(filepath, encoding="utf-8") as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Not a valid JSON file: {exc}") from exc
        self.data = self._clean(raw)
        return self.data

    # ---- totals ---------------------------------------------------------
    def calculate_totals(self):
        """Discount is taken off the subtotal first; tax applies to what remains."""
        d = self.data
        subtotal = sum((_dec(i["qty"]) * _dec(i["rate"]) for i in d["items"]), Decimal(0))
        discount = min(_dec(d.get("discount_amount", 0)), max(subtotal, Decimal(0)))
        taxable = subtotal - discount
        tax = taxable * _dec(d.get("tax_percent", 0)) / Decimal(100)
        subtotal, discount, tax = _cents(subtotal), _cents(discount), _cents(tax)
        total = subtotal - discount + tax
        return {"subtotal": float(subtotal), "discount": float(discount),
                "tax": float(tax), "total": float(total)}

    # ---- address book ---------------------------------------------------
    def add_client(self, name, addr1="", addr2=""):
        name = name.strip()
        if not name:
            raise ValueError("Enter a recipient name first.")
        clients = [c for c in self.settings["clients"] if c["name"].lower() != name.lower()]
        clients.append({"name": name, "addr1": addr1.strip(), "addr2": addr2.strip()})
        self.settings["clients"] = sorted(clients, key=lambda c: c["name"].lower())
        self.save_settings()

    def remove_client(self, name):
        self.settings["clients"] = [c for c in self.settings["clients"] if c["name"] != name]
        self.save_settings()

    # ---- trash ----------------------------------------------------------
    def move_to_trash(self, desc, qty, rate, date=""):
        self.trash_bin.append({"desc": desc, "qty": qty, "rate": rate, "date": date})

    def restore_from_trash(self, index):
        return self.trash_bin.pop(index)

    def empty_trash(self):
        self.trash_bin.clear()

    # ---- export ---------------------------------------------------------
    def _tone_color(self):
        return TONES.get(self.data.get("tone"), TONES["Work"])["color"]

    def export_pdf(self, filepath):
        renderer.export_pdf(filepath, self.data, self.calculate_totals(), self._tone_color())
        self.remember_sender()
        self.mark_number_used()

    def export_image(self, filepath):
        """Returns the list of files written (one per page)."""
        return renderer.export_image(filepath, self.data, self.calculate_totals(), self._tone_color())

    def print_invoice(self, temp_path):
        renderer.export_pdf(temp_path, self.data, self.calculate_totals(), self._tone_color())
        if sys.platform.startswith("win"):
            try:
                os.startfile(temp_path, "print")  # type: ignore[attr-defined]
            except OSError:
                os.startfile(temp_path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["lpr", temp_path], check=True)
        else:
            try:
                subprocess.run(["lp", temp_path], check=True)
            except (FileNotFoundError, subprocess.CalledProcessError):
                subprocess.run(["xdg-open", temp_path], check=True)
