"""Pop-up windows: calendar, settings, recycle bin, address book."""
from datetime import date
from tkinter import messagebox

import customtkinter as ctk
from tkcalendar import Calendar

from invoice import CURRENCIES, format_date, fmt_qty, money, parse_date, to_float
from widgets import (BG, BORDER, DANGER, DANGER_HOVER, HOVER, INPUT, LABEL, MUTED, PANEL, TEXT,
                     font)


class BaseDialog(ctk.CTkToplevel):
    def __init__(self, master, title, width, height):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=BG)
        self.resizable(False, False)
        x = master.winfo_rootx() + (master.winfo_width() - width) // 2
        y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")
        self.transient(master)
        self.after(150, self._take_focus)

    def _take_focus(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass  # window closed before it became visible


def open_calendar(master, target_var):
    win = BaseDialog(master, "Select Date", 300, 330)
    start = parse_date(target_var.get()) or date.today()
    cal = Calendar(win, selectmode="day", year=start.year, month=start.month, day=start.day)
    cal.pack(padx=16, pady=16, fill="both", expand=True)

    def confirm():
        target_var.set(format_date(cal.selection_get()))
        win.destroy()

    ctk.CTkButton(win, text="Confirm", font=font(14, True), command=confirm).pack(pady=(0, 16))


class SettingsDialog(BaseDialog):
    def __init__(self, master, backend, on_save):
        super().__init__(master, "Settings", 420, 470)
        self.backend, self.on_save = backend, on_save
        s = backend.settings

        ctk.CTkLabel(self, text="Application Settings", font=font(18, True), text_color=TEXT).pack(pady=(20, 10))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=36)

        self.currency = self._row(body, "Default currency", ctk.CTkComboBox, values=CURRENCIES, width=110)
        self.currency.set(s["currency"])
        self.appearance = self._row(body, "Appearance", ctk.CTkSegmentedButton, values=["light", "dark", "system"])
        self.appearance.set(s["appearance"])
        self.prefix = self._row(body, "Invoice number prefix", ctk.CTkEntry, width=110)
        self.prefix.insert(0, s["number_prefix"])
        self.next_no = self._row(body, "Next invoice number", ctk.CTkEntry, width=110)
        self.next_no.insert(0, str(s["next_number"]))

        self.png_switch = ctk.CTkSwitch(body, text="Also save a PNG when exporting PDF", font=font(13),
                                        text_color=TEXT)
        self.png_switch.pack(anchor="w", pady=14)
        if s["export_png_with_pdf"]:
            self.png_switch.select()

        self.error = ctk.CTkLabel(self, text="", text_color=DANGER, font=font(12))
        self.error.pack()
        ctk.CTkButton(self, text="Save Settings", font=font(14, True), command=self.save).pack(pady=14)

    def _row(self, parent, label, widget_cls, **kwargs):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=8)
        ctk.CTkLabel(row, text=label, font=font(14), text_color=TEXT).pack(side="left")
        widget = widget_cls(row, **kwargs)
        widget.pack(side="right")
        return widget

    def save(self):
        number = to_float(self.next_no.get())
        if number is None or number < 1 or number != int(number):
            self.error.configure(text="Next invoice number must be a whole number, 1 or more.")
            return
        s = self.backend.settings
        s["currency"] = self.currency.get() if self.currency.get() in CURRENCIES else "$"
        s["appearance"] = self.appearance.get()
        s["number_prefix"] = self.prefix.get().strip()
        s["next_number"] = int(number)
        s["export_png_with_pdf"] = bool(self.png_switch.get())
        try:
            self.backend.save_settings()
        except OSError as exc:
            self.error.configure(text=f"Could not save settings: {exc}")
            return
        self.on_save()
        self.destroy()


class TrashDialog(BaseDialog):
    def __init__(self, master, backend, on_restore):
        super().__init__(master, "Recycle Bin", 440, 460)
        self.backend, self.on_restore = backend, on_restore
        ctk.CTkLabel(self, text="Deleted Items", font=font(18, True), text_color=TEXT).pack(pady=(20, 6))
        ctk.CTkLabel(self, text="Items removed from this invoice. Restore adds them back.",
                     font=font(12), text_color=MUTED).pack()
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=PANEL)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=12)
        self.empty_btn = ctk.CTkButton(self, text="Empty Trash", font=font(14, True), fg_color=DANGER,
                                       hover_color=DANGER_HOVER, command=self.empty)
        self.empty_btn.pack(pady=(0, 16))
        self.render()

    def render(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        items = self.backend.trash_bin
        self.empty_btn.configure(state="normal" if items else "disabled")
        if not items:
            ctk.CTkLabel(self.scroll, text="Trash is empty.", text_color=MUTED, font=font(14)).pack(pady=20)
            return
        cur = self.backend.settings["currency"]
        for index, item in enumerate(items):
            row = ctk.CTkFrame(self.scroll, fg_color="transparent")
            row.pack(fill="x", pady=3)
            summary = f"{item['desc'] or '(no description)'}  ·  {fmt_qty(item['qty'])} × {money(cur, item['rate'])}"
            ctk.CTkLabel(row, text=summary, font=font(13), text_color=TEXT, anchor="w",
                         wraplength=250, justify="left").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="Restore", width=70, height=28, font=font(12, True),
                          command=lambda i=index: self.restore(i)).pack(side="right")

    def restore(self, index):
        self.on_restore(self.backend.restore_from_trash(index))
        self.render()

    def empty(self):
        if messagebox.askyesno("Empty Trash", "Permanently delete all items in the trash?", parent=self):
            self.backend.empty_trash()
            self.render()


class ClientsDialog(BaseDialog):
    def __init__(self, master, backend, on_pick):
        super().__init__(master, "Address Book", 440, 460)
        self.backend, self.on_pick = backend, on_pick
        ctk.CTkLabel(self, text="Saved Clients", font=font(18, True), text_color=TEXT).pack(pady=(20, 6))
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=PANEL)
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        self.render()

    def render(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        clients = self.backend.settings["clients"]
        if not clients:
            ctk.CTkLabel(self.scroll, text="No saved clients yet.\nUse “Save Client” in the recipient panel.",
                         text_color=MUTED, font=font(13), justify="center").pack(pady=20)
            return
        for client in clients:
            row = ctk.CTkFrame(self.scroll, fg_color="transparent")
            row.pack(fill="x", pady=3)
            lines = [client["name"]] + [a for a in (client["addr1"], client["addr2"]) if a]
            ctk.CTkLabel(row, text="\n".join(lines), font=font(13), text_color=TEXT, anchor="w",
                         justify="left").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="✕", width=30, height=28, fg_color="transparent", text_color=DANGER,
                          hover_color=HOVER, command=lambda n=client["name"]: self.delete(n)).pack(side="right")
            ctk.CTkButton(row, text="Use", width=50, height=28, font=font(12, True),
                          command=lambda c=client: self.pick(c)).pack(side="right", padx=(0, 6))

    def pick(self, client):
        self.on_pick(client)
        self.destroy()

    def delete(self, name):
        self.backend.remove_client(name)
        self.render()
