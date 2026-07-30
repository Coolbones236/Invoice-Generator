import json
import os
import platform
import subprocess
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from PIL import ImageGrab

class InvoiceBackend:
    def __init__(self):
        # 1. Setup Export Directories
        self.export_dir = "exports"
        self.json_dir = os.path.join(self.export_dir, "json")
        self.pdf_dir = os.path.join(self.export_dir, "pdfs")
        self.image_dir = os.path.join(self.export_dir, "images")

        # Create folders if they don't exist
        os.makedirs(self.json_dir, exist_ok=True)
        os.makedirs(self.pdf_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)

        self.data = {
            "logo_path": "",
            "sender_name": "Acme Design Studio",
            "sender_email": "billing@acme.com",
            "sender_address": "123 Creative Blvd, San Francisco, CA",
            
            "recipient_name": "Global Tech Corp",
            "recipient_addr1": "456 Enterprise Dr, Suite 900",
            "recipient_addr2": "Austin, TX 78701",
            
            "inv_date": "Oct 24, 2023",
            "inv_due": "Nov 23, 2023",
            "due_message": "Upon Receipt",
            "inv_project": "Q4 Redesign",
            "inv_number": "INV-2024-001",
            
            "items": [
                {"desc": "UI/UX Design - Landing Page", "qty": 1.0, "rate": 1200.00},
                {"desc": "Custom Icon Set", "qty": 1.0, "rate": 450.00}
            ],
            
            "tax_percent": 0.0,
            "discount_amount": 0.0,
            "notes": "Please include the invoice number on your check\nor wire transfer."
        }
        self.trash_bin = [] 
        self.settings = {"currency": "$", "theme": "Light"}

    def calculate_totals(self):
        subtotal = sum(item["qty"] * item["rate"] for item in self.data["items"])
        tax_amount = subtotal * (self.data["tax_percent"] / 100.0)
        total = subtotal + tax_amount - self.data["discount_amount"]
        
        return {
            "subtotal": subtotal,
            "tax": tax_amount,
            "discount": self.data["discount_amount"],
            "total": max(0.0, total)
        }

    def save_draft(self, filepath=None):
        if filepath is None:
            filepath = os.path.join(self.json_dir, "draft.json")
            
        export_data = self.data.copy()
        export_data["totals"] = self.calculate_totals()
        export_data["timestamp"] = datetime.now().isoformat()
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=4)
        return filepath

    def load_draft(self, filepath):
        """Loads a draft JSON file into backend data."""
        with open(filepath, 'r') as f:
            loaded_data = json.load(f)
        
        # Clean up metadata fields if stored in JSON
        if "totals" in loaded_data:
            del loaded_data["totals"]
        if "timestamp" in loaded_data:
            del loaded_data["timestamp"]
            
        self.data.update(loaded_data)
        return self.data

    def export_pdf(self, filepath=None):
        if filepath is None:
            filepath = os.path.join(self.pdf_dir, "Invoice_Export.pdf")
            
        c = canvas.Canvas(filepath, pagesize=letter)
        width, height = letter
        d = self.data
        totals = self.calculate_totals()
        
        primary_text = HexColor("#1E293B")
        secondary_text = HexColor("#475569")
        accent_color = HexColor("#1D4ED8")

        if d["logo_path"] and os.path.exists(d["logo_path"]):
            c.drawImage(d["logo_path"], 50, height - 110, width=60, height=60, preserveAspectRatio=True, mask='auto')
        
        c.setFont("Helvetica-Bold", 24)
        c.setFillColor(primary_text)
        c.drawString(50, height - 140, d["sender_name"])
        
        c.setFont("Helvetica", 12)
        c.setFillColor(secondary_text)
        c.drawString(50, height - 155, d["sender_address"])
        c.drawString(50, height - 170, d["sender_email"])

        c.setFont("Helvetica-Bold", 36)
        c.setFillColor(accent_color)
        c.drawRightString(width - 50, height - 100, "INVOICE")
        
        c.setFont("Helvetica", 12)
        c.setFillColor(secondary_text)
        c.drawRightString(width - 50, height - 120, d["inv_number"])

        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height - 220, "BILL TO")
        
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(primary_text)
        c.drawString(50, height - 240, d["recipient_name"])
        c.setFont("Helvetica", 12)
        c.setFillColor(secondary_text)
        c.drawString(50, height - 255, d["recipient_addr1"])
        c.drawString(50, height - 270, d["recipient_addr2"])

        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(width - 50, height - 220, "DETAILS")
        c.setFont("Helvetica", 12)
        
        c.drawRightString(width - 220, height - 240, "Date:")
        c.drawRightString(width - 50, height - 240, d["inv_date"])
        
        formatted_due = f"{d['inv_due']} ({d['due_message']})" if d.get("due_message") else d["inv_due"]
        c.drawRightString(width - 220, height - 255, "Due Date:")
        c.drawRightString(width - 50, height - 255, formatted_due)
        
        c.drawRightString(width - 220, height - 270, "Project:")
        c.drawRightString(width - 50, height - 270, d["inv_project"])

        y_pos = height - 320
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(primary_text)
        c.drawString(50, y_pos, "Description")
        c.drawRightString(width - 250, y_pos, "Qty")
        c.drawRightString(width - 150, y_pos, "Rate")
        c.drawRightString(width - 50, y_pos, "Amount")
        
        c.line(50, y_pos - 10, width - 50, y_pos - 10)
        y_pos -= 30

        c.setFont("Helvetica", 12)
        for item in d["items"]:
            amt = item["qty"] * item["rate"]
            c.drawString(50, y_pos, item["desc"])
            c.drawRightString(width - 250, y_pos, str(item["qty"]))
            c.drawRightString(width - 150, y_pos, f"{self.settings['currency']}{item['rate']:,.2f}")
            c.drawRightString(width - 50, y_pos, f"{self.settings['currency']}{amt:,.2f}")
            c.setStrokeColor(HexColor("#E2E8F0"))
            c.line(50, y_pos - 10, width - 50, y_pos - 10)
            y_pos -= 30

        y_pos -= 20
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(secondary_text)
        c.drawString(50, y_pos, "NOTES & PAYMENT INSTRUCTIONS")
        c.setFont("Helvetica", 11)
        
        text_y = y_pos - 15
        for line in d["notes"].split('\n'):
            c.drawString(50, text_y, line)
            text_y -= 15

        c.setFont("Helvetica", 12)
        c.drawRightString(width - 150, y_pos, "Subtotal:")
        c.drawRightString(width - 50, y_pos, f"{self.settings['currency']}{totals['subtotal']:,.2f}")
        
        c.drawRightString(width - 150, y_pos - 20, f"Tax ({d['tax_percent']}%):")
        c.drawRightString(width - 50, y_pos - 20, f"{self.settings['currency']}{totals['tax']:,.2f}")
        
        c.drawRightString(width - 150, y_pos - 40, "Discount:")
        c.drawRightString(width - 50, y_pos - 40, f"-{self.settings['currency']}{totals['discount']:,.2f}")
        
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(primary_text)
        c.drawRightString(width - 150, y_pos - 70, "Total:")
        c.setFillColor(accent_color)
        c.drawRightString(width - 50, y_pos - 70, f"{self.settings['currency']}{totals['total']:,.2f}")

        c.save()
        return filepath

    def export_image(self, widget, filepath=None):
        if filepath is None:
            filepath = os.path.join(self.image_dir, "Invoice_Export.png")
            
        x = widget.winfo_rootx()
        y = widget.winfo_rooty()
        w = widget.winfo_width()
        h = widget.winfo_height()
        
        img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        img.save(filepath)
        return filepath

    def print_invoice(self, filepath=None):
        if filepath is None:
            filepath = os.path.join(self.pdf_dir, "Print_Temp.pdf")
            
        filepath = self.export_pdf(filepath)
        try:
            if platform.system() == 'Windows':
                os.startfile(filepath, "print")
            elif platform.system() == 'Darwin': 
                subprocess.call(['open', filepath])
            else:
                subprocess.call(['xdg-open', filepath])
            return True
        except Exception as e:
            print(f"Printing failed: {e}")
            return False