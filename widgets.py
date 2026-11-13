"""Theme colours and small reusable widgets. Colour pairs are (light, dark)."""
from tkinter import font as tkfont

import customtkinter as ctk

from invoice import to_float

# App chrome (follows light/dark mode)
BG = ("#F8FAFC", "#0B1220")
PANEL = ("#FFFFFF", "#162033")
BORDER = ("#E2E8F0", "#2B3A55")
TEXT = ("#1E293B", "#F1F5F9")
MUTED = ("#64748B", "#94A3B8")
LABEL = ("#475569", "#CBD5E1")
INPUT = ("#FFFFFF", "#0F172A")
HOVER = ("#F1F5F9", "#1F2A44")
DANGER = "#EF4444"
DANGER_HOVER = "#DC2626"

# The invoice "paper" is always light so it matches the exported file
PAPER_INK = "#1E293B"
PAPER_GRAY = "#475569"
PAPER_MUTED = "#64748B"
PAPER_RULE = "#E2E8F0"

_family = None


def font(size=13, bold=False):
    """Pick the first installed preferred family (Open Sans may be missing)."""
    global _family
    if _family is None:
        installed = set(tkfont.families())
        for name in ("Open Sans", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Arial"):
            if name in installed:
                _family = name
                break
        else:
            _family = "Helvetica"
    return (_family, size, "bold") if bold else (_family, size)


class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, parent, title, is_expanded=False, **kwargs):
        super().__init__(parent, fg_color=PANEL, corner_radius=8, border_width=1,
                         border_color=BORDER, **kwargs)
        self.is_expanded = is_expanded

        self.header_frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=8, cursor="hand2")
        self.header_frame.pack(fill="x", pady=2, padx=2)
        self.title_label = ctk.CTkLabel(self.header_frame, text=title, font=font(13, True), text_color=TEXT)
        self.title_label.pack(side="left", padx=15, pady=12)
        self.toggle_button = ctk.CTkLabel(self.header_frame, text="", font=font(13, True), text_color=MUTED)
        self.toggle_button.pack(side="right", padx=15)
        for w in (self.header_frame, self.title_label, self.toggle_button):
            w.bind("<Button-1>", self.toggle_click)

        self.content_frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=8)
        self._apply_state()

    def _apply_state(self):
        if self.is_expanded:
            self.content_frame.pack(fill="both", expand=True, pady=(0, 15), padx=15)
        else:
            self.content_frame.pack_forget()
        self.toggle_button.configure(text="▴" if self.is_expanded else "▾")

    def toggle_click(self, event=None):
        self.is_expanded = not self.is_expanded
        self._apply_state()


def style_numeric_entry(entry, var, allow_blank=True, minimum=None):
    """Turn the entry's border red while its text isn't a valid number."""
    def check(*_):
        text = var.get().strip()
        value = to_float(text)
        ok = (text == "" and allow_blank) or (value is not None and (minimum is None or value >= minimum))
        entry.configure(border_color=BORDER if ok else DANGER)
    var.trace_add("write", check)
    check()


def labeled_entry(parent, label_text, text_var, pady=(0, 12), placeholder=None):
    container = ctk.CTkFrame(parent, fg_color="transparent")
    container.pack(fill="x", pady=pady)
    ctk.CTkLabel(container, text=label_text, font=font(12, True), text_color=LABEL).pack(anchor="w")
    entry = ctk.CTkEntry(container, textvariable=text_var, fg_color=INPUT, border_color=BORDER,
                         text_color=TEXT, height=32, placeholder_text=placeholder)
    entry.pack(fill="x", pady=(2, 0))
    return entry


def date_field(parent, label_text, text_var, on_calendar, pady=(0, 12)):
    container = ctk.CTkFrame(parent, fg_color="transparent")
    container.pack(fill="x", pady=pady)
    ctk.CTkLabel(container, text=label_text, font=font(12, True), text_color=LABEL).pack(anchor="w")
    row = ctk.CTkFrame(container, fg_color="transparent")
    row.pack(fill="x", pady=(2, 0))
    ctk.CTkEntry(row, textvariable=text_var, fg_color=INPUT, border_color=BORDER, text_color=TEXT,
                 height=32).pack(side="left", fill="x", expand=True)
    ctk.CTkButton(row, text="📅", width=32, height=32, fg_color=HOVER, hover_color=BORDER,
                  text_color=TEXT, command=lambda: on_calendar(text_var)).pack(side="left", padx=(8, 0))
