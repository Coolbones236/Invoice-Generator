import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor

# --- Page Configuration ---
st.set_page_config(page_title="Invoice Generator", page_icon="🧾", layout="centered")
st.title("🧾 Invoice Generator")

# --- Form Inputs ---
with st.expander("Sender Information", expanded=True):
    sender_name = st.text_input("Sender Name", "Acme Design Studio")
    sender_email = st.text_input("Sender Email", "billing@acme.com")
    sender_address = st.text_input("Sender Address", "123 Creative Blvd, San Francisco, CA")

with st.expander("Recipient Information"):
    recipient_name = st.text_input("Recipient Name", "Global Tech Corp")
    recipient_addr1 = st.text_input("Address Line 1", "456 Enterprise Dr, Suite 900")
    recipient_addr2 = st.text_input("Address Line 2", "Austin, TX 78701")

with st.expander("Invoice Details"):
    col1, col2 = st.columns(2)
    inv_number = col1.text_input("Invoice Number", "INV-2024-001")
    inv_project = col2.text_input("Project", "Q4 Redesign")
    inv_date = col1.date_input("Invoice Date").strftime("%b %d, %Y")
    inv_due = col2.date_input("Due Date").strftime("%b %d, %Y")
    due_message = st.text_input("Due Message", "Upon Receipt")

# --- Line Items (Using Streamlit's interactive dataframe) ---
st.subheader("Items & Services")
default_items = pd.DataFrame([
    {"Description": "UI/UX Design", "Qty": 1.0, "Rate": 1200.00},
    {"Description": "Custom Icon Set", "Qty": 1.0, "Rate": 450.00}
])
edited_items = st.data_editor(default_items, num_rows="dynamic", use_container_width=True)

with st.expander("Adjustments & Notes"):
    col3, col4 = st.columns(2)
    tax_percent = col3.number_input("Tax Percentage (%)", value=0.0, step=1.0)
    discount_amount = col4.number_input("Discount Amount ($)", value=0.0, step=10.0)
    notes = st.text_area("Notes & Payment Instructions", "Please include the invoice number on your check or wire transfer.")

# --- Calculations ---
subtotal = sum(row["Qty"] * row["Rate"] for index, row in edited_items.iterrows())
tax_amount = subtotal * (tax_percent / 100.0)
total = max(0.0, subtotal + tax_amount - discount_amount)

st.write("---")
st.subheader(f"**Total: ${total:,.2f}**")

# --- PDF Generation Function ---
def generate_pdf():
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    primary_text = HexColor("#1E293B")
    secondary_text = HexColor("#475569")
    accent_color = HexColor("#1D4ED8")

    # Header
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(primary_text)
    c.drawString(50, height - 100, sender_name)
    c.setFont("Helvetica", 12)
    c.setFillColor(secondary_text)
    c.drawString(50, height - 115, sender_address)
    c.drawString(50, height - 130, sender_email)

    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(accent_color)
    c.drawRightString(width - 50, height - 100, "INVOICE")
    c.setFont("Helvetica", 12)
    c.setFillColor(secondary_text)
    c.drawRightString(width - 50, height - 120, inv_number)

    # Bill To
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, height - 180, "BILL TO")
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(primary_text)
    c.drawString(50, height - 200, recipient_name)
    c.setFont("Helvetica", 12)
    c.setFillColor(secondary_text)
    c.drawString(50, height - 215, recipient_addr1)
    c.drawString(50, height - 230, recipient_addr2)

    # Details
    c.setFont("Helvetica", 12)
    c.drawRightString(width - 220, height - 200, "Date:")
    c.drawRightString(width - 50, height - 200, inv_date)
    formatted_due = f"{inv_due} ({due_message})" if due_message else inv_due
    c.drawRightString(width - 220, height - 215, "Due Date:")
    c.drawRightString(width - 50, height - 215, formatted_due)
    
    # Table Header
    y_pos = height - 280
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(primary_text)
    c.drawString(50, y_pos, "Description")
    c.drawRightString(width - 200, y_pos, "Qty")
    c.drawRightString(width - 120, y_pos, "Rate")
    c.drawRightString(width - 50, y_pos, "Amount")
    c.line(50, y_pos - 10, width - 50, y_pos - 10)
    y_pos -= 30

    # Table Rows
    c.setFont("Helvetica", 12)
    for index, row in edited_items.iterrows():
        amt = row["Qty"] * row["Rate"]
        c.drawString(50, y_pos, str(row["Description"]))
        c.drawRightString(width - 200, y_pos, str(row["Qty"]))
        c.drawRightString(width - 120, y_pos, f"${row['Rate']:,.2f}")
        c.drawRightString(width - 50, y_pos, f"${amt:,.2f}")
        c.setStrokeColor(HexColor("#E2E8F0"))
        c.line(50, y_pos - 10, width - 50, y_pos - 10)
        y_pos -= 30

    # Totals
    y_pos -= 20
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(secondary_text)
    c.drawString(50, y_pos, "NOTES & PAYMENT INSTRUCTIONS")
    c.setFont("Helvetica", 11)
    text_y = y_pos - 15
    for line in notes.split('\n'):
        c.drawString(50, text_y, line)
        text_y -= 15

    c.setFont("Helvetica", 12)
    c.drawRightString(width - 150, y_pos, "Subtotal:")
    c.drawRightString(width - 50, y_pos, f"${subtotal:,.2f}")
    c.drawRightString(width - 150, y_pos - 20, f"Tax ({tax_percent}%):")
    c.drawRightString(width - 50, y_pos - 20, f"${tax_amount:,.2f}")
    c.drawRightString(width - 150, y_pos - 40, "Discount:")
    c.drawRightString(width - 50, y_pos - 40, f"-${discount_amount:,.2f}")
    
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(primary_text)
    c.drawRightString(width - 150, y_pos - 70, "Total:")
    c.setFillColor(accent_color)
    c.drawRightString(width - 50, y_pos - 70, f"${total:,.2f}")

    c.save()
    buffer.seek(0)
    return buffer

# --- Download Button ---
pdf_buffer = generate_pdf()
st.download_button(
    label="⬇️ Download Invoice as PDF",
    data=pdf_buffer,
    file_name=f"{inv_number}.pdf",
    mime="application/pdf",
    type="primary",
    use_container_width=True
)