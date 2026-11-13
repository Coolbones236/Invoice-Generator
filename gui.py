import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from dialogs import ClientsDialog, SettingsDialog, TrashDialog, open_calendar
from invoice import CURRENCIES, TONES, InvoiceBackend, fmt_qty, money, to_float
from widgets import (BG, BORDER, HOVER, INPUT, LABEL, MUTED, PANEL, TEXT, PAPER_GRAY, PAPER_INK,
                     PAPER_MUTED, PAPER_RULE, DANGER, CollapsibleFrame, date_field, font,
                     labeled_entry, style_numeric_entry)

ctk.set_default_color_theme("blue")

# Entry-backed text fields: backend key -> StringVar
TEXT_FIELDS = [
    "logo_path", "sender_name", "sender_email", "sender_address",
    "recipient_name", "recipient_addr1", "recipient_addr2",
    "inv_date", "inv_due", "due_message", "inv_project", "inv_number", "currency",
]


class InvoiceGeneratorApp(ctk.CTk):
    def __init__(self, backend=None):
        ctk.set_appearance_mode(
            (backend.settings["appearance"] if backend else "light"))
        super().__init__()
        self.backend = backend if backend else InvoiceBackend()
        ctk.set_appearance_mode(self.backend.settings["appearance"])
        self.title("Invoice Generator")
        self.geometry("1440x900")
        self.minsize(1100, 700)
        self.configure(fg_color=BG)

        self._refresh_after_id = None
        self._status_after_id = None
        self._last_snapshot = None
        self._logo_ref = None
        self.item_ui_rows = []
        self.current_tone = self.backend.data.get("tone", "Work")

        self.init_variables()
        self.main_container = ctk.CTkFrame(self, fg_color=BG)
        self.main_container.pack(fill="both", expand=True)
        self.create_top_bar()
        self.create_main_content()
        self.bind_shortcuts()
        self.refresh_preview()

    # ------------------------------------------------------------ variables
    def init_variables(self):
        d = self.backend.data
        self.vars = {key: tk.StringVar(value=str(d.get(key, ""))) for key in TEXT_FIELDS}
        self.var_tax = tk.StringVar(value=f"{d['tax_percent']:g}")
        self.var_discount = tk.StringVar(value=f"{d['discount_amount']:g}")
        for var in [*self.vars.values(), self.var_tax, self.var_discount]:
            var.trace_add("write", self.schedule_refresh)

    def reload_ui_from_backend(self):
        d = self.backend.data
        for key, var in self.vars.items():
            var.set(str(d.get(key, "")))
        self.var_tax.set(f"{d.get('tax_percent', 0):g}")
        self.var_discount.set(f"{d.get('discount_amount', 0):g}")

        self.notes_textbox.delete("1.0", "end")
        self.notes_textbox.insert("1.0", d.get("notes", ""))

        self.current_tone = d.get("tone", "Work")
        self.tab_menu.set(self.current_tone)

        for ref in list(self.item_ui_rows):
            ref["frame"].destroy()
        self.item_ui_rows.clear()
        for item in d.get("items", []):
            self.add_item_ui_row(item["desc"], fmt_qty(item["qty"]), f"{item['rate']:.2f}", item.get("date", ""))
        self._last_snapshot = None
        self.refresh_preview()

    def bind_shortcuts(self):
        for combo, action in (("<Control-s>", self.save_draft_action), ("<Control-o>", self.import_draft_action),
                              ("<Control-e>", self.export_pdf_action), ("<Control-p>", self.print_action),
                              ("<Control-n>", self.new_invoice_action)):
            self.bind(combo, lambda _e, fn=action: fn())

    # --------------------------------------------------------------- status
    def show_status(self, message, error=False):
        self.status_label.configure(text=message, text_color=DANGER if error else MUTED)
        if self._status_after_id:
            self.after_cancel(self._status_after_id)
        self._status_after_id = self.after(3500, lambda: self.status_label.configure(text=""))

    def schedule_refresh(self, *_args):
        if self._refresh_after_id:
            self.after_cancel(self._refresh_after_id)
        self._refresh_after_id = self.after(250, self.refresh_preview)

    # -------------------------------------------------------------- dialogs
    def open_calendar(self, target_var):
        open_calendar(self, target_var)

    def open_settings_window(self):
        SettingsDialog(self, self.backend, self.on_settings_saved)

    def on_settings_saved(self):
        ctk.set_appearance_mode(self.backend.settings["appearance"])
        self.schedule_refresh()
        self.show_status("Settings saved")

    def open_trash_window(self):
        TrashDialog(self, self.backend, self.restore_trashed_item)

    def restore_trashed_item(self, item):
        self.add_item_ui_row(item["desc"], fmt_qty(item["qty"]), f"{item['rate']:.2f}", item.get("date", ""))
        self.show_status("Item restored")

    def open_clients_window(self):
        ClientsDialog(self, self.backend, self.apply_client)

    def apply_client(self, client):
        self.vars["recipient_name"].set(client["name"])
        self.vars["recipient_addr1"].set(client["addr1"])
        self.vars["recipient_addr2"].set(client["addr2"])

    def save_client_action(self):
        try:
            self.backend.add_client(self.vars["recipient_name"].get(), self.vars["recipient_addr1"].get(),
                                    self.vars["recipient_addr2"].get())
        except (ValueError, OSError) as exc:
            self.show_status(str(exc), error=True)
            return
        self.show_status("Client saved to address book")

    def select_logo(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All Files", "*.*")])
        if file_path:
            self.vars["logo_path"].set(file_path)

    # -------------------------------------------------------------- top bar
    def create_top_bar(self):
        bar = ctk.CTkFrame(self.main_container, height=60, fg_color=PANEL, corner_radius=0)
        bar.pack(side="top", fill="x")
        ctk.CTkFrame(self.main_container, height=1, fg_color=BORDER, corner_radius=0).pack(side="top", fill="x")

        ctk.CTkLabel(bar, text="Invoice Generator", font=font(20, True), text_color=TEXT).pack(
            side="left", padx=(20, 10))

        self.tab_menu = ctk.CTkSegmentedButton(
            bar, values=list(TONES), font=font(13, True), text_color=TEXT, fg_color=HOVER,
            selected_color=PANEL, unselected_color=HOVER, corner_radius=8, command=self.on_tone_change)
        self.tab_menu.set(self.current_tone)
        self.tab_menu.pack(side="left", padx=20, pady=12)

        self.status_label = ctk.CTkLabel(bar, text="", font=font(12), text_color=MUTED)
        self.status_label.pack(side="left", padx=10)

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right", padx=20)

        def icon_button(text, command):
            ctk.CTkButton(right, text=text, width=36, height=36, font=("Arial", 18), text_color=MUTED,
                          fg_color="transparent", hover_color=HOVER, command=command).pack(side="left", padx=4)

        def text_button(text, command, width):
            btn = ctk.CTkButton(right, text=text, font=font(13, True), height=36, width=width, fg_color=PANEL,
                                hover_color=HOVER, text_color=TEXT, border_width=1, border_color=BORDER,
                                command=command)
            btn.pack(side="left", padx=4)
            return btn

        icon_button("🗑", self.open_trash_window)
        icon_button("⚙", self.open_settings_window)
        text_button("New", self.new_invoice_action, 56)
        self.import_btn = text_button("Import", self.import_draft_action, 75)
        self.save_btn = text_button("Save Draft", self.save_draft_action, 90)
        self.export_btn = ctk.CTkButton(right, text="Export PDF", font=font(13, True), height=36, width=110,
                                        fg_color=TONES[self.current_tone]["color"], text_color="white",
                                        command=self.export_pdf_action)
        self.export_btn.pack(side="left", padx=(4, 0))

    def on_tone_change(self, tab):
        """Switching tone recolours the invoice and swaps the notes, unless the user edited them."""
        current_notes = self.notes_textbox.get("1.0", "end-1c").strip()
        if current_notes in ("", TONES[self.current_tone]["notes"].strip()):
            self.notes_textbox.delete("1.0", "end")
            self.notes_textbox.insert("1.0", TONES[tab]["notes"])
        self.current_tone = tab
        self.schedule_refresh()

    # ----------------------------------------------------------------- body
    def create_main_content(self):
        wrapper = ctk.CTkFrame(self.main_container, fg_color=BG)
        wrapper.pack(fill="both", expand=True)

        left = ctk.CTkFrame(wrapper, width=420, fg_color=BG)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self.left_sidebar = ctk.CTkScrollableFrame(left, fg_color=BG, corner_radius=0,
                                                   scrollbar_button_color=BORDER,
                                                   scrollbar_button_hover_color=MUTED)
        self.left_sidebar.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(self.left_sidebar, text="Draft Invoice", font=font(20, True), text_color=TEXT,
                     anchor="w").pack(fill="x", pady=(0, 20))

        self.create_sender_panel()
        self.create_recipient_panel()
        self.create_details_panel()
        self.create_items_panel()
        self.create_adjustments_panel()
        self.create_notes_panel()

        ctk.CTkFrame(wrapper, width=1, fg_color=BORDER).pack(side="left", fill="y")
        self.right_area = ctk.CTkScrollableFrame(wrapper, fg_color=BG, corner_radius=0,
                                                 scrollbar_button_color=BORDER,
                                                 scrollbar_button_hover_color=MUTED)
        self.right_area.pack(side="left", fill="both", expand=True)
        self.build_preview_skeleton()

    def create_sender_panel(self):
        self.sender_panel = CollapsibleFrame(self.left_sidebar, "Sender Information")
        self.sender_panel.pack(fill="x", pady=8)
        c = self.sender_panel.content_frame
        ctk.CTkButton(c, text="Upload Logo Image", fg_color=BORDER, text_color=TEXT, hover_color=HOVER,
                      command=self.select_logo).pack(fill="x", pady=(0, 10))
        labeled_entry(c, "Sender Name", self.vars["sender_name"])
        labeled_entry(c, "Address", self.vars["sender_address"])
        labeled_entry(c, "Email Address", self.vars["sender_email"], pady=(0, 0))

    def create_recipient_panel(self):
        self.recipient_panel = CollapsibleFrame(self.left_sidebar, "Recipient Information")
        self.recipient_panel.pack(fill="x", pady=8)
        c = self.recipient_panel.content_frame
        buttons = ctk.CTkFrame(c, fg_color="transparent")
        buttons.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(buttons, text="Address Book", fg_color=BORDER, text_color=TEXT, hover_color=HOVER,
                      command=self.open_clients_window).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(buttons, text="Save Client", fg_color=BORDER, text_color=TEXT, hover_color=HOVER,
                      command=self.save_client_action).pack(side="left", expand=True, fill="x", padx=(4, 0))
        labeled_entry(c, "Recipient Name", self.vars["recipient_name"])
        labeled_entry(c, "Address Line 1", self.vars["recipient_addr1"])
        labeled_entry(c, "Address Line 2", self.vars["recipient_addr2"], pady=(0, 0))

    def create_details_panel(self):
        self.details_panel = CollapsibleFrame(self.left_sidebar, "Invoice Details")
        self.details_panel.pack(fill="x", pady=8)
        c = self.details_panel.content_frame
        labeled_entry(c, "Invoice Number", self.vars["inv_number"])
        date_field(c, "Date", self.vars["inv_date"], self.open_calendar)
        date_field(c, "Due Date", self.vars["inv_due"], self.open_calendar)
        labeled_entry(c, "Message next to Due Date", self.vars["due_message"])
        labeled_entry(c, "Project", self.vars["inv_project"], pady=(0, 0))

    def create_items_panel(self):
        self.items_panel = CollapsibleFrame(self.left_sidebar, "Items & Services", is_expanded=True)
        self.items_panel.pack(fill="x", pady=8)
        c = self.items_panel.content_frame

        header = ctk.CTkFrame(c, fg_color="transparent")
        header.pack(fill="x", pady=(0, 5))
        self._configure_item_columns(header)
        for col, text, anchor in ((0, "Description", "w"), (1, "Qty", "w"), (2, "Rate", "w")):
            ctk.CTkLabel(header, text=text, font=font(12, True), text_color=LABEL, anchor=anchor).grid(
                row=0, column=col, sticky="w")

        self.items_list_frame = ctk.CTkFrame(c, fg_color="transparent")
        self.items_list_frame.pack(fill="x")
        for item in self.backend.data["items"]:
            self.add_item_ui_row(item["desc"], fmt_qty(item["qty"]), f"{item['rate']:.2f}", item.get("date", ""))

        accent = TONES["Work"]["color"]
        ctk.CTkButton(c, text="+ Add Item", font=font(13, True), text_color=accent, fg_color=PANEL,
                      hover_color=HOVER, border_width=1, border_color=accent,
                      command=lambda: self.add_item_ui_row("", "1", "0.00", focus=True)).pack(fill="x", pady=(10, 0))

    @staticmethod
    def _configure_item_columns(frame):
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, minsize=58)
        frame.grid_columnconfigure(2, minsize=82)
        frame.grid_columnconfigure(3, minsize=36)

    def add_item_ui_row(self, desc, qty, rate, date="", focus=False):
        row = ctk.CTkFrame(self.items_list_frame, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))
        self._configure_item_columns(row)

        var_desc, var_qty, var_rate = tk.StringVar(value=desc), tk.StringVar(value=qty), tk.StringVar(value=rate)
        var_date = tk.StringVar(value=date)
        for v in (var_desc, var_qty, var_rate, var_date):
            v.trace_add("write", self.schedule_refresh)

        desc_entry = ctk.CTkEntry(row, textvariable=var_desc, fg_color=INPUT, border_color=BORDER,
                                  text_color=TEXT, height=32)
        desc_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        qty_entry = ctk.CTkEntry(row, textvariable=var_qty, width=50, fg_color=INPUT, border_color=BORDER,
                                 text_color=TEXT, height=32)
        qty_entry.grid(row=0, column=1, padx=(0, 8))
        rate_entry = ctk.CTkEntry(row, textvariable=var_rate, width=74, fg_color=INPUT, border_color=BORDER,
                                  text_color=TEXT, height=32)
        rate_entry.grid(row=0, column=2, padx=(0, 4))
        style_numeric_entry(qty_entry, var_qty, allow_blank=False, minimum=0)
        style_numeric_entry(rate_entry, var_rate, allow_blank=False)

        date_entry = ctk.CTkEntry(row, textvariable=var_date, fg_color=INPUT, border_color=BORDER,
                                  text_color=TEXT, height=28, placeholder_text="Date (optional)")
        date_entry.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(4, 0))
        ctk.CTkButton(row, text="📅", width=32, height=28, fg_color=HOVER, hover_color=BORDER, text_color=TEXT,
                      command=lambda: self.open_calendar(var_date)).grid(row=1, column=1, columnspan=2,
                                                                         sticky="w", pady=(4, 0))

        ref = {"frame": row, "desc": var_desc, "qty": var_qty, "rate": var_rate, "date": var_date}
        ctk.CTkButton(row, text="🗑", width=32, height=32, font=("Arial", 16), text_color=DANGER,
                      fg_color="transparent", hover_color="#FEE2E2",
                      command=lambda r=ref: self.remove_item_ui_row(r)).grid(row=0, column=3)
        self.item_ui_rows.append(ref)
        if focus:
            desc_entry.focus_set()
        self.schedule_refresh()

    def remove_item_ui_row(self, ref):
        self.backend.move_to_trash(ref["desc"].get(), to_float(ref["qty"].get(), 0.0),
                                   to_float(ref["rate"].get(), 0.0), ref["date"].get())
        ref["frame"].destroy()
        self.item_ui_rows.remove(ref)
        self.show_status("Item moved to Recycle Bin (🗑 to restore)")
        self.schedule_refresh()

    def create_adjustments_panel(self):
        self.adjustments_panel = CollapsibleFrame(self.left_sidebar, "Adjustments & Taxes")
        self.adjustments_panel.pack(fill="x", pady=8)
        c = self.adjustments_panel.content_frame

        row = ctk.CTkFrame(c, fg_color="transparent")
        row.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(row, text="Currency", font=font(12, True), text_color=LABEL).pack(side="left")
        ctk.CTkComboBox(row, values=CURRENCIES, variable=self.vars["currency"], width=90,
                        state="readonly").pack(side="right")

        tax = labeled_entry(c, "Tax Percentage (%)", self.var_tax)
        disc = labeled_entry(c, "Discount Amount", self.var_discount, pady=(0, 0))
        style_numeric_entry(tax, self.var_tax, minimum=0)
        style_numeric_entry(disc, self.var_discount, minimum=0)

    def create_notes_panel(self):
        self.notes_panel = CollapsibleFrame(self.left_sidebar, "Invoice Notes")
        self.notes_panel.pack(fill="x", pady=8)
        self.notes_textbox = ctk.CTkTextbox(self.notes_panel.content_frame, height=90, fg_color=INPUT,
                                            text_color=TEXT, font=font(13), border_width=1, border_color=BORDER)
        self.notes_textbox.insert("1.0", self.backend.data.get("notes", ""))
        self.notes_textbox.pack(fill="x")
        self.notes_textbox.bind("<KeyRelease>", self.schedule_refresh)

    # -------------------------------------------------------------- preview
    def build_preview_skeleton(self):
        tools = ctk.CTkFrame(self.right_area, height=50, fg_color=BG)
        tools.pack(fill="x", padx=40, pady=(20, 0))
        self.draft_badge = ctk.CTkLabel(tools, text="≡ Draft", font=font(12, True), corner_radius=12,
                                        width=70, height=24)
        self.draft_badge.pack(side="left")

        icons = ctk.CTkFrame(tools, fg_color="transparent")
        icons.pack(side="right")
        for text, command in (("🖨", self.print_action), ("🖼", self.export_image_action)):
            ctk.CTkButton(icons, text=text, width=36, height=36, font=("Arial", 16), text_color=MUTED,
                          fg_color="transparent", hover_color=HOVER, command=command).pack(side="left", padx=5)

        self.paper_frame = ctk.CTkFrame(self.right_area, fg_color="white", corner_radius=4, border_width=1,
                                        border_color=PAPER_RULE)
        self.paper_frame.pack(fill="both", expand=True, padx=40, pady=(10, 40))

    def sync_ui_to_backend(self):
        d = self.backend.data
        for key, var in self.vars.items():
            d[key] = var.get()
        d["tone"] = self.current_tone
        d["notes"] = self.notes_textbox.get("1.0", "end-1c").strip()
        d["tax_percent"] = max(0.0, to_float(self.var_tax.get(), 0.0))
        d["discount_amount"] = max(0.0, to_float(self.var_discount.get(), 0.0))
        d["items"] = [{"desc": ref["desc"].get(),
                       "date": ref["date"].get().strip(),
                       "qty": max(0.0, to_float(ref["qty"].get(), 0.0)),
                       "rate": to_float(ref["rate"].get(), 0.0)} for ref in self.item_ui_rows]

    def refresh_preview(self):
        self._refresh_after_id = None
        self.sync_ui_to_backend()
        tone = TONES[self.current_tone]
        self.draft_badge.configure(fg_color=tone["badge_bg"], text_color=tone["color"])
        self.export_btn.configure(fg_color=tone["color"], hover_color=tone["hover"])

        # Skip the (flicker-prone) rebuild when nothing visible changed
        snapshot = json.dumps([self.backend.data, self.current_tone, self._logo_mtime()], sort_keys=True)
        if snapshot == self._last_snapshot:
            return
        self._last_snapshot = snapshot

        for widget in self.paper_frame.winfo_children():
            widget.destroy()
        d = self.backend.data
        totals = self.backend.calculate_totals()
        cur = d["currency"]

        doc = ctk.CTkFrame(self.paper_frame, fg_color="transparent")
        doc.pack(fill="both", expand=True, padx=50, pady=50)
        self._preview_header(doc, d, tone)
        self._preview_parties(doc, d)
        self._preview_table(doc, d, cur)
        self._preview_footer(doc, d, totals, cur, tone)

    def _logo_mtime(self):
        path = self.backend.data.get("logo_path")
        try:
            return os.path.getmtime(path) if path else 0
        except OSError:
            return -1

    def _preview_header(self, doc, d, tone):
        top = ctk.CTkFrame(doc, fg_color="transparent")
        top.pack(fill="x", pady=(0, 30))
        left = ctk.CTkFrame(top, fg_color="transparent")
        left.pack(side="left")

        self._logo_ref = None
        if d["logo_path"]:
            try:
                with Image.open(d["logo_path"]) as src:
                    img = src.convert("RGBA")
                scale = min(60 / img.width, 60 / img.height)
                size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
                self._logo_ref = ctk.CTkImage(light_image=img, size=size)
                ctk.CTkLabel(left, image=self._logo_ref, text="").pack(anchor="w", pady=(0, 15))
            except Exception:
                ctk.CTkLabel(left, text="Logo could not be loaded", text_color="#DC2626",
                             font=font(12)).pack(anchor="w", pady=(0, 15))
        else:
            ctk.CTkButton(left, text="+ Logo", font=font(12, True), width=60, height=60, fg_color="#F1F5F9",
                          hover_color="#E2E8F0", text_color=PAPER_MUTED, border_width=1, border_color="#CBD5E1",
                          corner_radius=8, command=self.select_logo).pack(anchor="w", pady=(0, 15))

        ctk.CTkLabel(left, text=d["sender_name"], font=font(24, True), text_color=PAPER_INK).pack(anchor="w")
        for line in (d["sender_address"], d["sender_email"]):
            if line:
                ctk.CTkLabel(left, text=line, font=font(13), text_color=PAPER_GRAY).pack(anchor="w")

        right = ctk.CTkFrame(top, fg_color="transparent")
        right.pack(side="right", anchor="n")
        ctk.CTkLabel(right, text="INVOICE", font=font(36, True), text_color=tone["color"]).pack(anchor="e")
        ctk.CTkLabel(right, text=d["inv_number"], font=font(13), text_color=PAPER_MUTED).pack(anchor="e")

    def _preview_parties(self, doc, d):
        section = ctk.CTkFrame(doc, fg_color="transparent")
        section.pack(fill="x", pady=(20, 40))
        bill = ctk.CTkFrame(section, fg_color="transparent")
        bill.pack(side="left", anchor="n")
        ctk.CTkLabel(bill, text="BILL TO", font=font(11, True), text_color=PAPER_MUTED).pack(anchor="w")
        ctk.CTkLabel(bill, text=d["recipient_name"], font=font(15, True), text_color=PAPER_INK).pack(anchor="w")
        for key in ("recipient_addr1", "recipient_addr2"):
            if d[key]:
                ctk.CTkLabel(bill, text=d[key], font=font(13), text_color=PAPER_GRAY).pack(anchor="w")

        meta = ctk.CTkFrame(section, fg_color="transparent")
        meta.pack(side="right", anchor="n")
        ctk.CTkLabel(meta, text="DETAILS", font=font(11, True), text_color=PAPER_MUTED).grid(
            row=0, column=1, sticky="e", pady=(0, 5))
        due = f"{d['inv_due']} ({d['due_message']})" if d["due_message"] else d["inv_due"]
        rows = [("Date:", d["inv_date"]), ("Due Date:", due)]
        if d["inv_project"]:
            rows.append(("Project:", d["inv_project"]))
        for i, (label, value) in enumerate(rows, start=1):
            ctk.CTkLabel(meta, text=label, font=font(13), text_color=PAPER_GRAY).grid(
                row=i, column=0, sticky="e", padx=(0, 15))
            ctk.CTkLabel(meta, text=value, font=font(13), text_color=PAPER_INK).grid(row=i, column=1, sticky="e")

    def _preview_table(self, doc, d, cur):
        table = ctk.CTkFrame(doc, fg_color="transparent")
        table.pack(fill="x")
        table.grid_columnconfigure(0, weight=1)
        table.grid_columnconfigure(1, minsize=60)
        table.grid_columnconfigure(2, minsize=110)
        table.grid_columnconfigure(3, minsize=120)

        for col, (text, sticky) in enumerate((("Description", "w"), ("Qty", "e"), ("Rate", "e"), ("Amount", "e"))):
            ctk.CTkLabel(table, text=text, font=font(13, True), text_color=PAPER_INK).grid(
                row=0, column=col, sticky=sticky, padx=(0, 0 if col == 0 else 10))
        ctk.CTkFrame(table, height=2, fg_color=PAPER_INK).grid(row=1, column=0, columnspan=4, sticky="ew",
                                                              pady=(5, 12))
        row = 2
        for item in d["items"]:
            amount = item["qty"] * item["rate"]
            cell = ctk.CTkFrame(table, fg_color="transparent")
            cell.grid(row=row, column=0, sticky="w")
            ctk.CTkLabel(cell, text=item["desc"], font=font(13, True), text_color=PAPER_INK, anchor="w",
                         justify="left", wraplength=380).pack(anchor="w")
            if item.get("date"):
                ctk.CTkLabel(cell, text=item["date"], font=font(11), text_color=PAPER_MUTED,
                             anchor="w").pack(anchor="w")
            for col, text in ((1, fmt_qty(item["qty"])), (2, money(cur, item["rate"])), (3, money(cur, amount))):
                ctk.CTkLabel(table, text=text, font=font(13), text_color=PAPER_INK).grid(
                    row=row, column=col, sticky="e", padx=(0, 10))
            ctk.CTkFrame(table, height=1, fg_color=PAPER_RULE).grid(row=row + 1, column=0, columnspan=4,
                                                                    sticky="ew", pady=(12, 12))
            row += 2

    def _preview_footer(self, doc, d, totals, cur, tone):
        footer = ctk.CTkFrame(doc, fg_color="transparent")
        footer.pack(fill="x", pady=(40, 0))
        notes = ctk.CTkFrame(footer, fg_color="transparent")
        notes.pack(side="left", anchor="nw")
        if d["notes"]:
            ctk.CTkLabel(notes, text="NOTES & PAYMENT INSTRUCTIONS", font=font(11, True),
                         text_color=PAPER_MUTED).pack(anchor="w")
            ctk.CTkLabel(notes, text=d["notes"], font=font(13), text_color=PAPER_GRAY, justify="left",
                         wraplength=330).pack(anchor="w", pady=(5, 0))

        block = ctk.CTkFrame(footer, fg_color="transparent")
        block.pack(side="right", anchor="n")
        discount = f"-{money(cur, totals['discount'])}" if totals["discount"] > 0 else money(cur, 0)
        self.draw_total_row(block, 0, "Subtotal", money(cur, totals["subtotal"]))
        self.draw_total_row(block, 1, "Discount", discount)
        self.draw_total_row(block, 2, f"Tax ({d['tax_percent']:g}%)", money(cur, totals["tax"]), pady=(0, 15))
        grand = ctk.CTkFrame(block, fg_color="transparent")
        grand.grid(row=3, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(grand, text="Total", font=font(18, True), text_color=PAPER_INK).pack(side="left")
        ctk.CTkLabel(grand, text=money(cur, totals["total"]), font=font(20, True),
                     text_color=tone["color"]).pack(side="right", padx=(30, 0))

    @staticmethod
    def draw_total_row(parent, row, label, value, pady=0):
        ctk.CTkLabel(parent, text=label, font=font(13), text_color=PAPER_GRAY).grid(
            row=row, column=0, sticky="w", padx=(0, 30), pady=pady)
        ctk.CTkLabel(parent, text=value, font=font(13), text_color=PAPER_INK).grid(
            row=row, column=1, sticky="e", pady=pady)

    # -------------------------------------------------------------- actions
    def _flash(self, button, done_text, original):
        button.configure(text=done_text)
        self.after(2000, lambda: button.configure(text=original))

    def _file_name(self, ext, prefix=""):
        raw = self.backend.data.get("inv_number") or "Invoice"
        safe = "".join(c if c.isalnum() or c in "-_ ." else "_" for c in raw).strip() or "Invoice"
        return f"{prefix}{safe}.{ext}"

    def new_invoice_action(self):
        if not messagebox.askyesno("New Invoice", "Start a new invoice? Unsaved changes will be lost.",
                                   parent=self):
            return
        self.backend.reset_invoice()
        self.backend.trash_bin.clear()
        self.reload_ui_from_backend()
        self.show_status("New invoice started")

    def save_draft_action(self):
        self.sync_ui_to_backend()
        filepath = filedialog.asksaveasfilename(
            initialdir=self.backend.json_dir, initialfile=self._file_name("json", "Draft_"),
            defaultextension=".json", filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Save Draft As")
        if not filepath:
            return
        try:
            self.backend.save_draft(filepath)
        except OSError as exc:
            messagebox.showerror("Save failed", f"Could not save the draft:\n{exc}", parent=self)
            return
        self._flash(self.save_btn, "Saved!", "Save Draft")

    def import_draft_action(self):
        filepath = filedialog.askopenfilename(
            initialdir=self.backend.json_dir, filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Import Draft JSON")
        if not filepath:
            return
        try:
            self.backend.load_draft(filepath)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Import failed", f"Could not load that draft:\n{exc}", parent=self)
            return
        self.reload_ui_from_backend()
        self._flash(self.import_btn, "Loaded!", "Import")

    def export_pdf_action(self):
        self.sync_ui_to_backend()
        filepath = filedialog.asksaveasfilename(
            initialdir=self.backend.pdf_dir, initialfile=self._file_name("pdf"), defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf"), ("All Files", "*.*")], title="Export Invoice as PDF")
        if not filepath:
            return
        try:
            self.backend.export_pdf(filepath)
            if self.backend.settings["export_png_with_pdf"]:
                self.backend.export_image(os.path.splitext(filepath)[0] + ".png")
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not export the invoice:\n{exc}", parent=self)
            return
        self._flash(self.export_btn, "Exported!", "Export PDF")

    def export_image_action(self):
        self.sync_ui_to_backend()
        filepath = filedialog.asksaveasfilename(
            initialdir=self.backend.image_dir, initialfile=self._file_name("png"), defaultextension=".png",
            filetypes=[("PNG Images", "*.png"), ("JPEG Images", "*.jpg"), ("All Files", "*.*")],
            title="Export Invoice as Image")
        if not filepath:
            return
        try:
            written = self.backend.export_image(filepath)
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not export the image:\n{exc}", parent=self)
            return
        self.show_status("Image saved" if len(written) == 1 else f"Saved {len(written)} page images")

    def print_action(self):
        self.sync_ui_to_backend()
        try:
            self.backend.print_invoice(os.path.join(self.backend.pdf_dir, "Print_Temp.pdf"))
        except Exception as exc:
            messagebox.showerror("Print failed", f"Could not send the invoice to a printer:\n{exc}", parent=self)


if __name__ == "__main__":
    InvoiceGeneratorApp().mainloop()
