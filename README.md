# 🧾 Python Invoice Generator

A modern, desktop-based invoice generator built with Python and CustomTkinter. This application allows users to effortlessly create, preview, and export professional invoices. Featuring a live-updating preview pane, automatic calculations, and seamless exporting to PDF and PNG, it is designed for freelancers, students, and small business owners.

---

## ✨ Features

*   **⚡ Live Preview:** The invoice preview updates instantly as you type in the form fields.
*   **📑 Multiple Export Options:** Export your finished invoices as high-quality PDFs (via ReportLab) or shareable PNG images (via Pillow).
*   **💾 Draft Management:** Save your work-in-progress as a `.json` draft and load it later to pick up where you left off.
*   **🎨 Contextual Themes:** Switch between **Work**, **School**, and **Personal** modes to automatically adjust the accent colors and default payment instructions.
*   **🖼️ Custom Logos:** Easily upload and embed your own business logo into the invoice header.
*   **🧮 Automatic Calculations:** Automatically computes row amounts, subtotals, custom tax percentages, flat discounts, and the final total due.
*   **🗑️ Recycle Bin:** Accidentally deleted an item? Retrieve it or permanently delete it using the built-in trash window.
*   **📅 Interactive Calendars:** Use the pop-up calendar widget to easily select Issue Dates and Due Dates.

---

📥 Download & Installation
Go to the Releases section on the right side of this page.
Download the latest TextToSpeechStudio.exe file.
Double-click TextToSpeechStudio.exe to launch—no installation required!

---

## How To Use 
Navigating the App:
Drafting: Use the collapsible panels on the left to enter Sender details, Recipient details, Invoice metadata, and Line Items.

Adjusting: Add applicable tax percentages or flat-rate discounts in the "Adjustments & Taxes" panel.

Saving: Click Save Draft to store your progress as a .json file in the auto-generated exports/json/ folder.

Exporting: Click Export PDF to generate both a .pdf and a .png copy of your invoice, saved securely in your exports/ folder.

Settings: Click the ⚙️ Gear icon to change the default currency symbol (e.g., $, €, £).

---

## 📁 Project Structure

Invoice-Generator/
│
├── main.py              # The main entry point to launch the application
├── gui.py               # Handles the CustomTkinter user interface and front-end logic
├── invoice.py           # Handles data state, math, and the PDF/Image export engine
├── create_icon.py       # A helper script to generate the app_icon.ico and .png files
├── app_icon.ico         # Generated Windows application icon
├── .gitignore           # Git ignore rules (prevents tracking exported files)
│
└── exports/             # Auto-generated directory for output files
    ├── json/            # Saved drafts
    ├── pdfs/            # Exported PDF invoices
    └── images/          # Exported PNG invoices

---

## 💻 Built With
CustomTkinter - UI Framework

ReportLab - PDF Generation

Pillow (PIL) - Image Processing & Exporting

tkcalendar - Date Picker Widget

📄 License & Terms
Text To Speech Studio is distributed under custom terms allowing free personal use while restricting modification and redistribution. See the full [LICENSE](LICENSE.md) file for details.
