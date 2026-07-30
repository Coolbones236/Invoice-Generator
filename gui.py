import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from tkcalendar import Calendar
from PIL import Image
from invoice import InvoiceBackend
import os

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, parent, title, is_expanded=False, **kwargs):
        super().__init__(parent, **kwargs)
        self.title = title
        self.is_expanded = is_expanded
        panel_bg_color = "white"
        header_font = ("Open Sans", 13, "bold")
        self.configure(fg_color=panel_bg_color, corner_radius=8, border_width=1, border_color="#E2E8F0")
        
        self.header_frame = ctk.CTkFrame(self, fg_color=panel_bg_color, corner_radius=8, cursor="hand2")
        self.header_frame.pack(fill="x", pady=2, padx=2)
        self.header_frame.bind("<Button-1>", self.toggle_click)
        
        self.title_label = ctk.CTkLabel(self.header_frame, text=self.title, font=header_font, text_color="#1E293B")
        self.title_label.pack(side="left", padx=15, pady=12)
        self.title_label.bind("<Button-1>", self.toggle_click)
        
        self.toggle_button = ctk.CTkLabel(self.header_frame, text="^" if self.is_expanded else "v", font=header_font, text_color="#64748B")
        self.toggle_button.pack(side="right", padx=15)
        self.toggle_button.bind("<Button-1>", self.toggle_click)
        
        self.content_frame = ctk.CTkFrame(self, fg_color=panel_bg_color, corner_radius=8)
        if self.is_expanded:
            self.content_frame.pack(fill="both", expand=True, pady=(0, 15), padx=15)

    def toggle_click(self, event=None):
        if self.is_expanded:
            self.content_frame.pack_forget()
            self.toggle_button.configure(text="v")
        else:
            self.content_frame.pack(fill="both", expand=True, pady=(0, 15), padx=15)
            self.toggle_button.configure(text="^")
        self.is_expanded = not self.is_expanded


class InvoiceGeneratorApp(ctk.CTk):
    def __init__(self, backend=None):
        super().__init__()
        self.backend = backend if backend else InvoiceBackend()
        self.title("Invoice Generator")
        self.geometry("1440x900")
        self.configure(fg_color="#F8FAFC")
        
        self._refresh_after_id = None
        self.item_ui_rows = [] 
        self.current_tone = "Work"
        self.tones = {
            "Work": {"color": "#1D4ED8", "hover": "#1E40AF", "badge_bg": "#DBEAFE", "notes": "Please include the invoice number on your check\nor wire transfer."},
            "School": {"color": "#0F766E", "hover": "#115E59", "badge_bg": "#CCFBF1", "notes": "Include student ID on all correspondence."},
            "Personal": {"color": "#9333EA", "hover": "#7E22CE", "badge_bg": "#F3E8FF", "notes": "Thanks! Let me know if you have any questions."}
        }

        self.init_variables()
        self.main_container = ctk.CTkFrame(self, fg_color="#F8FAFC")
        self.main_container.pack(fill="both", expand=True)

        self.create_top_bar()
        self.create_main_content()
        self.refresh_preview() 

    def init_variables(self):
        d = self.backend.data
        self.var_logo = tk.StringVar(value=d["logo_path"])
        self.var_sender_name = tk.StringVar(value=d["sender_name"])
        self.var_sender_email = tk.StringVar(value=d["sender_email"])
        self.var_sender_addr = tk.StringVar(value=d["sender_address"])
        self.var_recip_name = tk.StringVar(value=d["recipient_name"])
        self.var_recip_addr1 = tk.StringVar(value=d["recipient_addr1"])
        self.var_recip_addr2 = tk.StringVar(value=d["recipient_addr2"])
        self.var_inv_date = tk.StringVar(value=d["inv_date"])
        self.var_inv_due = tk.StringVar(value=d["inv_due"])
        self.var_due_msg = tk.StringVar(value=d["due_message"])
        self.var_inv_proj = tk.StringVar(value=d["inv_project"])
        self.var_inv_num = tk.StringVar(value=d["inv_number"])
        self.var_tax = tk.StringVar(value=str(d["tax_percent"]))
        self.var_discount = tk.StringVar(value=str(d["discount_amount"]))

        vars_to_trace = [
            self.var_logo, self.var_sender_name, self.var_sender_email, self.var_sender_addr,
            self.var_recip_name, self.var_recip_addr1, self.var_recip_addr2,
            self.var_inv_date, self.var_inv_due, self.var_due_msg, self.var_inv_proj, self.var_inv_num,
            self.var_tax, self.var_discount
        ]
        for v in vars_to_trace:
            v.trace_add("write", self.schedule_refresh)

    def reload_ui_from_backend(self):
        d = self.backend.data
        self.var_logo.set(d.get("logo_path", ""))
        self.var_sender_name.set(d.get("sender_name", ""))
        self.var_sender_email.set(d.get("sender_email", ""))
        self.var_sender_addr.set(d.get("sender_address", ""))
        self.var_recip_name.set(d.get("recipient_name", ""))
        self.var_recip_addr1.set(d.get("recipient_addr1", ""))
        self.var_recip_addr2.set(d.get("recipient_addr2", ""))
        self.var_inv_date.set(d.get("inv_date", ""))
        self.var_inv_due.set(d.get("inv_due", ""))
        self.var_due_msg.set(d.get("due_message", ""))
        self.var_inv_proj.set(d.get("inv_project", ""))
        self.var_inv_num.set(d.get("inv_number", ""))
        self.var_tax.set(str(d.get("tax_percent", 0.0)))
        self.var_discount.set(str(d.get("discount_amount", 0.0)))

        if hasattr(self, 'notes_textbox'):
            self.notes_textbox.delete("1.0", "end")
            self.notes_textbox.insert("1.0", d.get("notes", ""))

        for ref in list(self.item_ui_rows):
            ref["frame"].destroy()
        self.item_ui_rows.clear()

        for item in d.get("items", []):
            self.add_item_ui_row(item.get("desc", ""), str(item.get("qty", 1.0)), str(item.get("rate", 0.0)))

    def schedule_refresh(self, *args):
        if self._refresh_after_id:
            self.after_cancel(self._refresh_after_id)
        self._refresh_after_id = self.after(300, self.refresh_preview)

    def open_calendar(self, target_var):
        top = ctk.CTkToplevel(self)
        top.title("Select Date")
        top.geometry("300x250")
        top.attributes('-topmost', True)

        cal = Calendar(top, selectmode='day', date_pattern='M d, yyyy')
        cal.pack(pady=20, fill="both", expand=True)

        def set_date():
            target_var.set(cal.get_date())
            top.destroy()

        ctk.CTkButton(top, text="Confirm", font=("Open Sans", 14, "bold"), command=set_date).pack(pady=10)

    def open_settings_window(self):
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("Settings")
        settings_win.geometry("400x300")
        settings_win.attributes('-topmost', True)
        
        ctk.CTkLabel(settings_win, text="Application Settings", font=("Open Sans", 18, "bold")).pack(pady=20)
        
        currency_frame = ctk.CTkFrame(settings_win, fg_color="transparent")
        currency_frame.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(currency_frame, text="Default Currency:", font=("Open Sans", 14)).pack(side="left")
        
        currency_select = ctk.CTkComboBox(currency_frame, values=["$", "€", "£", "¥"], font=("Open Sans", 14))
        currency_select.set(self.backend.settings["currency"])
        currency_select.pack(side="right")

        def save_settings():
            self.backend.settings["currency"] = currency_select.get()
            self.schedule_refresh()
            settings_win.destroy()

        ctk.CTkButton(settings_win, text="Save Settings", font=("Open Sans", 14, "bold"), command=save_settings).pack(pady=30)

    def open_trash_window(self):
        trash_win = ctk.CTkToplevel(self)
        trash_win.title("Recycle Bin (Deleted Items)")
        trash_win.geometry("400x400")
        trash_win.attributes('-topmost', True)
        
        ctk.CTkLabel(trash_win, text="Deleted Items", font=("Open Sans", 18, "bold")).pack(pady=20)
        scroll = ctk.CTkScrollableFrame(trash_win)
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        if not self.backend.trash_bin:
            ctk.CTkLabel(scroll, text="Trash is empty.", text_color="#64748B", font=("Open Sans", 14)).pack(pady=20)
        else:
            for item in self.backend.trash_bin:
                ctk.CTkLabel(scroll, text=f"• {item['desc']} (${item['rate']})", font=("Open Sans", 13)).pack(anchor="w")

        ctk.CTkButton(trash_win, text="Empty Trash", font=("Open Sans", 14, "bold"), fg_color="#EF4444", hover_color="#DC2626", 
                      command=lambda: [self.backend.trash_bin.clear(), trash_win.destroy()]).pack(pady=10)

    def select_logo(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if file_path:
            self.var_logo.set(file_path)

    def create_top_bar(self):
        top_bar_frame = ctk.CTkFrame(self.main_container, height=60, fg_color="#ffffff", corner_radius=0)
        top_bar_frame.pack(side="top", fill="x")
        ctk.CTkFrame(self.main_container, height=1, fg_color="#E2E8F0", corner_radius=0).pack(side="top", fill="x")

        ctk.CTkLabel(top_bar_frame, text="Invoice Generator", font=("Open Sans", 20, "bold"), text_color="#1E293B").pack(side="left", padx=(20, 10))

        self.tab_menu = ctk.CTkSegmentedButton(top_bar_frame, values=["Work", "School", "Personal"],
                                                 font=("Open Sans", 13, "bold"), text_color="#1E293B", 
                                                 fg_color="#F1F5F9", selected_color="white", unselected_color="#F1F5F9", 
                                                 corner_radius=8,
                                                 command=lambda tab: [setattr(self, 'current_tone', tab), self.schedule_refresh()])
        self.tab_menu.set("Work")
        self.tab_menu.pack(side="left", padx=20, pady=12)

        right_icons_frame = ctk.CTkFrame(top_bar_frame, fg_color="transparent")
        right_icons_frame.pack(side="right", padx=20)

        trash_btn = ctk.CTkButton(right_icons_frame, text="🗑", width=36, height=36, font=("Arial", 18), text_color="#64748B", 
                                  fg_color="transparent", hover_color="#F1F5F9", command=self.open_trash_window)
        trash_btn.pack(side="left", padx=5)

        settings_btn = ctk.CTkButton(right_icons_frame, text="⚙", width=36, height=36, font=("Arial", 18), text_color="#64748B", 
                                     fg_color="transparent", hover_color="#F1F5F9", command=self.open_settings_window)
        settings_btn.pack(side="left", padx=5)

        self.import_btn = ctk.CTkButton(right_icons_frame, text="Import", font=("Open Sans", 13, "bold"), height=36,
                                        fg_color="white", hover_color="#F8FAFC", text_color="#1E293B", border_width=1, border_color="#CBD5E1", width=75,
                                        command=self.import_draft_action)
        self.import_btn.pack(side="left", padx=(10, 5))

        self.save_btn = ctk.CTkButton(right_icons_frame, text="Save Draft", font=("Open Sans", 13, "bold"), height=36,
                                      fg_color="white", hover_color="#F8FAFC", text_color="#1E293B", border_width=1, border_color="#CBD5E1", width=90,
                                      command=self.save_draft_action)
        self.save_btn.pack(side="left", padx=(5, 5))

        self.export_btn = ctk.CTkButton(right_icons_frame, text="Export PDF", font=("Open Sans", 13, "bold"), height=36,
                                        fg_color=self.tones["Work"]["color"], text_color="white", width=110,
                                        command=self.export_pdf_action)
        self.export_btn.pack(side="left", padx=(5, 0))

    def create_main_content(self):
        content_wrapper = ctk.CTkFrame(self.main_container, fg_color="#F8FAFC")
        content_wrapper.pack(fill="both", expand=True)

        left_panel_wrapper = ctk.CTkFrame(content_wrapper, width=420, fg_color="#F8FAFC")
        left_panel_wrapper.pack(side="left", fill="y")
        left_panel_wrapper.pack_propagate(False)

        self.left_sidebar = ctk.CTkScrollableFrame(left_panel_wrapper, fg_color="#F8FAFC", corner_radius=0, scrollbar_button_color="#E2E8F0", scrollbar_button_hover_color="#CBD5E1")
        self.left_sidebar.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(self.left_sidebar, text="Draft New Invoice", font=("Open Sans", 20, "bold"), text_color="#1E293B", anchor="w").pack(fill="x", pady=(0, 20))

        self.create_sender_panel()
        self.create_recipient_panel()
        self.create_details_panel()
        self.create_items_panel()
        self.create_adjustments_panel()
        self.create_notes_panel()

        ctk.CTkFrame(content_wrapper, width=1, fg_color="#E2E8F0").pack(side="left", fill="y")

        self.right_area = ctk.CTkScrollableFrame(content_wrapper, fg_color="#F8FAFC", corner_radius=0, scrollbar_button_color="#E2E8F0", scrollbar_button_hover_color="#CBD5E1")
        self.right_area.pack(side="left", fill="both", expand=True)
        self.build_preview_skeleton()

    def create_sender_panel(self):
        self.sender_panel = CollapsibleFrame(self.left_sidebar, title="Sender Information", is_expanded=False)
        self.sender_panel.pack(fill="x", pady=8)
        content = self.sender_panel.content_frame
        
        ctk.CTkButton(content, text="Upload Logo Image", fg_color="#E2E8F0", text_color="black", hover_color="#CBD5E1", 
                      command=self.select_logo).pack(fill="x", pady=(0,10))
        
        self.add_form_field(content, "Sender Name", self.var_sender_name)
        self.add_form_field(content, "Address", self.var_sender_addr)
        self.add_form_field(content, "Email Address", self.var_sender_email, pady=(0,0))

    def create_recipient_panel(self):
        self.recipient_panel = CollapsibleFrame(self.left_sidebar, title="Recipient Information", is_expanded=False)
        self.recipient_panel.pack(fill="x", pady=8)
        content = self.recipient_panel.content_frame
        self.add_form_field(content, "Recipient Name", self.var_recip_name)
        self.add_form_field(content, "Address Line 1", self.var_recip_addr1)
        self.add_form_field(content, "Address Line 2", self.var_recip_addr2, pady=(0,0))

    def create_details_panel(self):
        self.details_panel = CollapsibleFrame(self.left_sidebar, title="Invoice Details", is_expanded=False)
        self.details_panel.pack(fill="x", pady=8)
        content = self.details_panel.content_frame
        self.add_form_field(content, "Invoice Number", self.var_inv_num)
        
        date_frame = ctk.CTkFrame(content, fg_color="transparent")
        date_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(date_frame, text="Date", font=("Open Sans", 12, "bold"), text_color="#475569").pack(anchor="w")
        d_entry = ctk.CTkEntry(date_frame, textvariable=self.var_inv_date, corner_radius=6, border_color="#E2E8F0", fg_color="white", height=32)
        d_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(date_frame, text="📅", width=32, height=32, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#1E293B", command=lambda: self.open_calendar(self.var_inv_date)).pack(side="left", padx=(8,0))

        due_frame = ctk.CTkFrame(content, fg_color="transparent")
        due_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(due_frame, text="Due Date", font=("Open Sans", 12, "bold"), text_color="#475569").pack(anchor="w")
        du_entry = ctk.CTkEntry(due_frame, textvariable=self.var_inv_due, corner_radius=6, border_color="#E2E8F0", fg_color="white", height=32)
        du_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(due_frame, text="📅", width=32, height=32, fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#1E293B", command=lambda: self.open_calendar(self.var_inv_due)).pack(side="left", padx=(8,0))

        self.add_form_field(content, "Message next to Due Date", self.var_due_msg)
        self.add_form_field(content, "Project", self.var_inv_proj, pady=(0,0))

    def create_items_panel(self):
        self.items_panel = CollapsibleFrame(self.left_sidebar, title="Items & Services", is_expanded=True)
        self.items_panel.pack(fill="x", pady=8)
        content = self.items_panel.content_frame

        labels_frame = ctk.CTkFrame(content, fg_color="transparent")
        labels_frame.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(labels_frame, text="Description", font=("Open Sans", 12, "bold"), text_color="#475569").pack(side="left")
        ctk.CTkLabel(labels_frame, text="Rate", font=("Open Sans", 12, "bold"), text_color="#475569").pack(side="right", padx=(45, 10))
        ctk.CTkLabel(labels_frame, text="Qty", font=("Open Sans", 12, "bold"), text_color="#475569").pack(side="right", padx=(0, 45))

        self.items_list_frame = ctk.CTkFrame(content, fg_color="transparent")
        self.items_list_frame.pack(fill="x")

        for item in self.backend.data["items"]:
            self.add_item_ui_row(item["desc"], str(item["qty"]), str(item["rate"]))

        ctk.CTkButton(content, text="+ Add Item", font=("Open Sans", 13, "bold"), text_color=self.tones["Work"]["color"], fg_color="white", border_width=1, 
                      border_color=self.tones["Work"]["color"], command=lambda: self.add_item_ui_row("", "1.0", "0.00")).pack(fill="x", pady=(10, 0))

    def add_item_ui_row(self, desc, qty, rate):
        row_frame = ctk.CTkFrame(self.items_list_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=(0, 10))
        
        var_desc = tk.StringVar(value=desc)
        var_qty = tk.StringVar(value=qty)
        var_rate = tk.StringVar(value=rate)

        for v in (var_desc, var_qty, var_rate): v.trace_add("write", self.schedule_refresh)

        ctk.CTkEntry(row_frame, textvariable=var_desc, fg_color="white", height=32).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkEntry(row_frame, textvariable=var_qty, width=45, fg_color="white", height=32).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row_frame, textvariable=var_rate, width=70, fg_color="white", height=32).pack(side="left", padx=(0, 8))

        item_ref = {"frame": row_frame, "desc": var_desc, "qty": var_qty, "rate": var_rate}
        self.item_ui_rows.append(item_ref)

        del_btn = ctk.CTkButton(row_frame, text="🗑", width=32, height=32, font=("Arial", 16), text_color="#EF4444", 
                                fg_color="transparent", hover_color="#FEE2E2", command=lambda ref=item_ref: self.remove_item_ui_row(ref))
        del_btn.pack(side="left")
        self.schedule_refresh()

    def remove_item_ui_row(self, item_ref):
        try:
            self.backend.trash_bin.append({
                "desc": item_ref["desc"].get(),
                "rate": item_ref["rate"].get()
            })
        except: pass
        item_ref["frame"].destroy()
        self.item_ui_rows.remove(item_ref)
        self.schedule_refresh()

    def create_adjustments_panel(self):
        self.adjustments_panel = CollapsibleFrame(self.left_sidebar, title="Adjustments & Taxes", is_expanded=False)
        self.adjustments_panel.pack(fill="x", pady=8)
        content = self.adjustments_panel.content_frame
        self.add_form_field(content, "Tax Percentage (%)", self.var_tax)
        self.add_form_field(content, "Discount Amount", self.var_discount, pady=(0,0))

    def create_notes_panel(self):
        self.notes_panel = CollapsibleFrame(self.left_sidebar, title="Invoice Notes", is_expanded=False)
        self.notes_panel.pack(fill="x", pady=8)
        content = self.notes_panel.content_frame
        
        self.notes_textbox = ctk.CTkTextbox(content, height=80, fg_color="white", font=("Open Sans", 13), border_width=1, border_color="#E2E8F0")
        self.notes_textbox.insert("1.0", self.tones["Work"]["notes"])
        self.notes_textbox.pack(fill="x")
        self.notes_textbox.bind("<KeyRelease>", self.schedule_refresh)

    def add_form_field(self, parent, label_text, text_var, pady=(0, 12)):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", pady=pady)
        ctk.CTkLabel(container, text=label_text, font=("Open Sans", 12, "bold"), text_color="#475569").pack(anchor="w")
        ctk.CTkEntry(container, textvariable=text_var, fg_color="white", height=32).pack(fill="x", pady=(2, 0))

    def build_preview_skeleton(self):
        self.tools_frame = ctk.CTkFrame(self.right_area, height=50, fg_color="#F8FAFC")
        self.tools_frame.pack(fill="x", padx=40, pady=(20, 0))
        
        self.draft_badge = ctk.CTkLabel(self.tools_frame, text="≡ Draft", font=("Open Sans", 12, "bold"), corner_radius=12, width=70, height=24)
        self.draft_badge.pack(side="left")

        icons_right = ctk.CTkFrame(self.tools_frame, fg_color="transparent")
        icons_right.pack(side="right")
        
        search_ico = ctk.CTkButton(icons_right, text="🔍", width=36, height=36, font=("Arial", 16), text_color="#64748B", fg_color="transparent", hover_color="#F1F5F9")
        search_ico.pack(side="left", padx=5)
        
        print_ico = ctk.CTkButton(icons_right, text="🖨", width=36, height=36, font=("Arial", 16), text_color="#64748B", fg_color="transparent", hover_color="#F1F5F9", command=self.print_action)
        print_ico.pack(side="left", padx=5)
        
        share_ico = ctk.CTkButton(icons_right, text="🔗", width=36, height=36, font=("Arial", 16), text_color="#64748B", fg_color="transparent", hover_color="#F1F5F9", command=self.export_image_action)
        share_ico.pack(side="left", padx=5)

        self.paper_frame = ctk.CTkFrame(self.right_area, fg_color="white", corner_radius=4, border_width=1, border_color="#E2E8F0")
        self.paper_frame.pack(fill="both", expand=True, padx=40, pady=(10, 40))

    def sync_ui_to_backend(self):
        d = self.backend.data
        d["logo_path"] = self.var_logo.get()
        d["sender_name"] = self.var_sender_name.get()
        d["sender_email"] = self.var_sender_email.get()
        d["sender_address"] = self.var_sender_addr.get()
        d["recipient_name"] = self.var_recip_name.get()
        d["recipient_addr1"] = self.var_recip_addr1.get()
        d["recipient_addr2"] = self.var_recip_addr2.get()
        d["inv_date"] = self.var_inv_date.get()
        d["inv_due"] = self.var_inv_due.get()
        d["due_message"] = self.var_due_msg.get()
        d["inv_project"] = self.var_inv_proj.get()
        d["inv_number"] = self.var_inv_num.get()
        d["notes"] = self.notes_textbox.get("1.0", "end-1c").strip()
        
        try: d["tax_percent"] = float(self.var_tax.get())
        except ValueError: d["tax_percent"] = 0.0
        try: d["discount_amount"] = float(self.var_discount.get().replace('$', '').replace(',', ''))
        except ValueError: d["discount_amount"] = 0.0

        d["items"] = []
        for ref in self.item_ui_rows:
            try: q = float(ref["qty"].get())
            except ValueError: q = 0.0
            try: r = float(ref["rate"].get().replace('$', '').replace(',', ''))
            except ValueError: r = 0.0
            d["items"].append({"desc": ref["desc"].get(), "qty": q, "rate": r})

    def refresh_preview(self):
        self.sync_ui_to_backend()
        active_tone = self.tones[self.current_tone]
        self.draft_badge.configure(fg_color=active_tone["badge_bg"], text_color=active_tone["color"])
        self.export_btn.configure(fg_color=active_tone["color"], hover_color=active_tone["hover"])
        
        for widget in self.paper_frame.winfo_children():
            widget.destroy()

        d = self.backend.data
        totals = self.backend.calculate_totals()
        currency = self.backend.settings["currency"]

        doc = ctk.CTkFrame(self.paper_frame, fg_color="transparent")
        doc.pack(fill="both", expand=True, padx=50, pady=50)

        top_section = ctk.CTkFrame(doc, fg_color="transparent")
        top_section.pack(fill="x", pady=(0, 30))
        left_header = ctk.CTkFrame(top_section, fg_color="transparent")
        left_header.pack(side="left")

        if d["logo_path"]:
            try:
                img_data = Image.open(d["logo_path"])
                logo_img = ctk.CTkImage(light_image=img_data, size=(60, 60))
                ctk.CTkLabel(left_header, image=logo_img, text="").pack(anchor="w", pady=(0, 15))
            except Exception:
                ctk.CTkLabel(left_header, text="Invalid Logo", text_color="red").pack(anchor="w", pady=(0, 15))
        else:
            logo_box = ctk.CTkButton(left_header, text="+ Logo", font=("Open Sans", 12, "bold"), width=60, height=60, 
                                     fg_color="#F1F5F9", hover_color="#E2E8F0", text_color="#64748B", border_width=1, border_color="#CBD5E1", 
                                     corner_radius=8, command=self.select_logo)
            logo_box.pack(anchor="w", pady=(0, 15))

        ctk.CTkLabel(left_header, text=d["sender_name"], font=("Open Sans", 24, "bold"), text_color="#1E293B").pack(anchor="w")
        ctk.CTkLabel(left_header, text=d["sender_address"], font=("Open Sans", 13), text_color="#475569").pack(anchor="w")

        right_header = ctk.CTkFrame(top_section, fg_color="transparent")
        right_header.pack(side="right", anchor="n")
        ctk.CTkLabel(right_header, text="INVOICE", font=("Open Sans", 36, "bold"), text_color=active_tone["color"]).pack(anchor="e")
        ctk.CTkLabel(right_header, text=d["inv_number"], font=("Open Sans", 13), text_color="#64748B").pack(anchor="e")

        details_section = ctk.CTkFrame(doc, fg_color="transparent")
        details_section.pack(fill="x", pady=(20, 40))
        bill_to = ctk.CTkFrame(details_section, fg_color="transparent")
        bill_to.pack(side="left")
        
        ctk.CTkLabel(bill_to, text="BILL TO", font=("Open Sans", 11, "bold"), text_color="#64748B").pack(anchor="w")
        ctk.CTkLabel(bill_to, text=d["recipient_name"], font=("Open Sans", 15, "bold"), text_color="#1E293B").pack(anchor="w")
        ctk.CTkLabel(bill_to, text=d["recipient_addr1"], font=("Open Sans", 13), text_color="#475569").pack(anchor="w")
        ctk.CTkLabel(bill_to, text=d["recipient_addr2"], font=("Open Sans", 13), text_color="#475569").pack(anchor="w")

        meta_details = ctk.CTkFrame(details_section, fg_color="transparent")
        meta_details.pack(side="right", anchor="s")
        ctk.CTkLabel(meta_details, text="DETAILS", font=("Open Sans", 11, "bold"), text_color="#64748B").grid(row=0, column=1, sticky="e", pady=(0, 5))
        
        formatted_due = f"{d['inv_due']} ({d['due_message']})" if d['due_message'] else d['inv_due']
        
        row_idx = 1
        for label, val in [("Date:", d["inv_date"]), ("Due Date:", formatted_due), ("Project:", d["inv_project"])]:
            ctk.CTkLabel(meta_details, text=label, font=("Open Sans", 13), text_color="#475569").grid(row=row_idx, column=0, sticky="e", padx=(0, 15))
            ctk.CTkLabel(meta_details, text=val, font=("Open Sans", 13), text_color="#1E293B").grid(row=row_idx, column=1, sticky="w")
            row_idx += 1

        table_section = ctk.CTkFrame(doc, fg_color="transparent")
        table_section.pack(fill="x")
        header_row = ctk.CTkFrame(table_section, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(header_row, text="Description", font=("Open Sans", 13, "bold"), text_color="#1E293B").pack(side="left")
        ctk.CTkLabel(header_row, text="Amount", font=("Open Sans", 13, "bold"), text_color="#1E293B").pack(side="right")
        ctk.CTkLabel(header_row, text="Rate", font=("Open Sans", 13, "bold"), text_color="#1E293B").pack(side="right", padx=(0, 50))
        ctk.CTkLabel(header_row, text="Qty", font=("Open Sans", 13, "bold"), text_color="#1E293B").pack(side="right", padx=(0, 60))
        ctk.CTkFrame(table_section, height=2, fg_color="#1E293B").pack(fill="x", pady=(0, 15))

        for i, item in enumerate(d["items"]):
            amt = item["qty"] * item["rate"]
            row = ctk.CTkFrame(table_section, fg_color="transparent")
            row.pack(fill="x", pady=(0, 15))
            ctk.CTkLabel(row, text=item["desc"], font=("Open Sans", 13, "bold"), text_color="#1E293B").pack(side="left")
            ctk.CTkLabel(row, text=f"{currency}{amt:,.2f}", font=("Open Sans", 13), text_color="#1E293B").pack(side="right")
            ctk.CTkLabel(row, text=f"{currency}{item['rate']:,.2f}", font=("Open Sans", 13), text_color="#1E293B").pack(side="right", padx=(0, 40))
            ctk.CTkLabel(row, text=str(item["qty"]), font=("Open Sans", 13), text_color="#1E293B").pack(side="right", padx=(0, 80))
            ctk.CTkFrame(table_section, height=1, fg_color="#E2E8F0").pack(fill="x", pady=(0, 15))

        footer_section = ctk.CTkFrame(doc, fg_color="transparent")
        footer_section.pack(fill="x", side="bottom", pady=(50, 0))
        notes_block = ctk.CTkFrame(footer_section, fg_color="transparent", width=350)
        notes_block.pack(side="left", anchor="nw")
        
        ctk.CTkLabel(notes_block, text="NOTES & PAYMENT INSTRUCTIONS", font=("Open Sans", 11, "bold"), text_color="#64748B").pack(anchor="w")
        ctk.CTkLabel(notes_block, text=d["notes"], text_color="#475569", font=("Open Sans", 13), justify="left").pack(anchor="w", pady=(5, 0))

        totals_block = ctk.CTkFrame(footer_section, fg_color="transparent")
        totals_block.pack(side="right", anchor="n")
        
        self.draw_total_row(totals_block, 0, "Subtotal", f"{currency}{totals['subtotal']:,.2f}")
        self.draw_total_row(totals_block, 1, f"Tax ({d['tax_percent']}%)", f"{currency}{totals['tax']:,.2f}")
        self.draw_total_row(totals_block, 2, "Discount", f"-{currency}{totals['discount']:,.2f}", pady=(0, 15))
        
        grand = ctk.CTkFrame(totals_block, fg_color="transparent")
        grand.grid(row=3, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(grand, text="Total", font=("Open Sans", 18, "bold"), text_color="#1E293B").pack(side="left")
        ctk.CTkLabel(grand, text=f"{currency}{totals['total']:,.2f}", font=("Open Sans", 20, "bold"), text_color=active_tone["color"]).pack(side="right")

    def draw_total_row(self, parent, row, label, value, pady=0):
        ctk.CTkLabel(parent, text=label, font=("Open Sans", 13), text_color="#475569").grid(row=row, column=0, sticky="w", padx=(0, 30), pady=pady)
        ctk.CTkLabel(parent, text=value, font=("Open Sans", 13), text_color="#1E293B").grid(row=row, column=1, sticky="e", pady=pady)

    # --- Button Action Handlers ---
    def save_draft_action(self):
        self.sync_ui_to_backend()
        default_name = f"Draft_{self.backend.data.get('inv_number', '001')}.json"
        
        filepath = filedialog.asksaveasfilename(
            initialdir=self.backend.json_dir,
            initialfile=default_name,
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Save Draft As"
        )
        
        if filepath:
            self.backend.save_draft(filepath)
            self.save_btn.configure(text="Saved!")
            self.after(2000, lambda: self.save_btn.configure(text="Save Draft"))

    def import_draft_action(self):
        filepath = filedialog.askopenfilename(
            initialdir=self.backend.json_dir,
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Import Draft JSON"
        )
        
        if filepath:
            self.backend.load_draft(filepath)
            self.reload_ui_from_backend()
            self.refresh_preview()
            self.import_btn.configure(text="Loaded!")
            self.after(2000, lambda: self.import_btn.configure(text="Import"))

    def export_pdf_action(self):
        self.sync_ui_to_backend()
        default_name = f"{self.backend.data.get('inv_number', 'Invoice')}.pdf"
        
        filepath = filedialog.asksaveasfilename(
            initialdir=self.backend.pdf_dir,
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf"), ("All Files", "*.*")],
            title="Export Invoice as PDF"
        )
        
        if filepath:
            # 1. Export PDF
            self.backend.export_pdf(filepath)
            
            # 2. Automatically export an Image version in the same location
            image_filepath = os.path.splitext(filepath)[0] + ".png"
            self.backend.export_image(self.paper_frame, image_filepath)
            
            self.export_btn.configure(text="Exported Both!")
            self.after(2000, lambda: self.export_btn.configure(text="Export PDF"))

    def export_image_action(self):
        self.sync_ui_to_backend()
        default_name = f"{self.backend.data.get('inv_number', 'Invoice')}.png"
        
        filepath = filedialog.asksaveasfilename(
            initialdir=self.backend.image_dir,
            initialfile=default_name,
            defaultextension=".png",
            filetypes=[("PNG Images", "*.png"), ("JPEG Images", "*.jpg"), ("All Files", "*.*")],
            title="Export Invoice as Image"
        )
        
        if filepath:
            self.backend.export_image(self.paper_frame, filepath)

    def print_action(self):
        self.sync_ui_to_backend()
        default_filepath = os.path.join(self.backend.pdf_dir, "Print_Temp.pdf")
        self.backend.print_invoice(default_filepath)

if __name__ == "__main__":
    app = InvoiceGeneratorApp()
    app.mainloop()