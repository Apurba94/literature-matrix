"""Literature Matrix desktop program."""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import appkit as ak
from . import review as rv
from .appkit import Entity, Field, entities

STANCES = ["Covers", "Supports", "Contradicts", "Qualifies"]
SCHEMA = entities(
    Entity("paper", "Paper", "Papers", "title", [
        Field("citekey", "Key", list_col=True, width=14),
        Field("title", "Title", required=True, list_col=True, width=40),
        Field("authors", "Authors (; separated)", list_col=True, width=22),
        Field("year", "Year", "int", list_col=True, width=6),
        Field("venue", "Journal or venue"),
        Field("doi", "DOI"),
        Field("stage", "Screening stage", "choice", rv.STAGES, default="Identified", list_col=True, width=18),
        Field("reason", "Exclusion reason", "choice", rv.EXCLUDE_REASONS),
        Field("method", "Method", "choice", rv.METHODS, list_col=True, width=16),
        Field("context", "Context or setting", list_col=True, width=14),
        Field("sample", "Sample"),
        Field("quality", "Quality", "choice", rv.QUALITY, default="Not assessed"),
        Field("findings", "Main findings", "long"),
        Field("limitations", "Limitations", "long"),
        Field("abstract", "Abstract", "long"),
    ], "COALESCE(year, 9999) DESC, id"),
    Entity("theme", "Theme", "Themes", "name", [
        Field("name", "Theme", required=True, list_col=True, width=30),
        Field("description", "Description", "long", list_col=True, width=50),
    ]),
    Entity("link", "Link", "Links", "stance", [
        Field("paper_id", "Paper", "ref", ref="paper", required=True, list_col=True, width=30),
        Field("theme_id", "Theme", "ref", ref="theme", required=True, list_col=True, width=26),
        Field("stance", "Stance", "choice", STANCES, default="Covers", list_col=True, width=12),
    ]),
)


def sample(store):
    store.set_setting("topic", "remote work and wellbeing (sample)")
    t1 = store.insert("theme", name="Autonomy", description="Whether control over time and place improves wellbeing.")
    t2 = store.insert("theme", name="Isolation", description="Social costs of working apart.")
    t3 = store.insert("theme", name="Productivity", description="Effects on output.")
    store.insert("theme", name="Caring responsibilities", description="How home duties change the picture.")
    data = [("Author, A.; Writer, B.", "Sample study on flexibility", 2019, "Cross-sectional survey", "UK", "Moderate", [(t1, "Supports"), (t2, "Covers")]),
            ("Researcher, C.", "Sample panel of remote staff", 2020, "Cross-sectional survey", "UK", "High", [(t1, "Supports"), (t3, "Supports")]),
            ("Scholar, D.; Fellow, E.; Peer, F.", "Sample interviews with new hires", 2021, "Interviews", "USA", "Moderate", [(t2, "Supports")]),
            ("Analyst, G.", "Sample output comparison", 2021, "Cross-sectional survey", "UK", "Low", [(t3, "Contradicts")]),
            ("Thinker, H.", "Sample review of the field", 2022, "Cross-sectional survey", "UK", "High", [(t1, "Qualifies"), (t3, "Supports")])]
    for au, title, y, m, c, q, links in data:
        pid = store.insert("paper", authors=au, title=title, year=y, method=m, context=c, quality=q, stage="Included", findings="A sample finding.")
        for t, s in links:
            store.insert("link", paper_id=pid, theme_id=t, stance=s)
    for i, st in enumerate(("Identified", "Duplicate", "Excluded at title", "Excluded at title", "Excluded at abstract", "Excluded at full text")):
        store.insert("paper", title="Sample record %d" % (i + 1), year=2015 + i, stage=st, reason="Wrong outcome" if "full" in st else None)


def data(store):
    return store.list("paper"), store.list("theme"), store.list("link")


class Papers(ttk.Frame):
    title = "Papers"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.view = ak.EntityView(self, app, "paper", buttons=[("Import file", self.import_file), ("Paste", self.paste)], split=0.6)
        self.view.pack(fill="both", expand=True)
        self.refresh, self.commit = self.view.refresh, self.view.commit

    def load(self, text):
        try:
            a, d = rv.import_papers(self.app.store, text)
        except ValueError as exc:
            messagebox.showerror("Import", str(exc), parent=self)
            return
        self.refresh()
        self.app.status("Added %d, marked %d as duplicates" % (a, d))

    def import_file(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("References", "*.bib *.ris *.txt"), ("All files", "*.*")])
        if path:
            with open(path, encoding="utf-8", errors="replace") as fh:
                self.load(fh.read())

    def paste(self):
        win = tk.Toplevel(self)
        win.title("Paste BibTeX or RIS")
        win.geometry("%dx%d" % (600 * self.app.scale, 380 * self.app.scale))
        win.transient(self.winfo_toplevel())
        win.configure(bg=self.app.colors["bg"])
        frame, t = ak.make_text(win, self.app.colors, mono=True)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        def go():
            self.load(ak.get_text(t))
            win.destroy()
        ttk.Button(win, text="Import", style="Accent.TButton", command=go).pack(pady=(0, 8))


class Screening(ttk.Frame):
    title = "Screening"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True)
        left, right = ttk.Frame(pane), ttk.Frame(pane)
        pane.add(left, weight=2)
        pane.add(right, weight=3)
        pane.bind("<Map>", lambda e: pane.after_idle(lambda: pane.sashpos(0, int(pane.winfo_width() * 0.4))))
        ttk.Label(left, text="Records waiting for a decision", style="Muted.TLabel").pack(anchor="w")
        self.queue = ak.Table(left, app, [("title", "Title", 36), ("year", "Year", 6)], on_select=self.show)
        self.queue.pack(fill="both", expand=True)
        frame, self.abstract = ak.make_text(left, app.colors, height=7)
        frame.pack(fill="x", pady=4)
        row = ttk.Frame(left)
        row.pack(fill="x")
        for text, stage in (("Include", "Included"), ("Exclude: title", "Excluded at title"), ("Exclude: abstract", "Excluded at abstract"), ("Exclude: full text", "Excluded at full text")):
            ttk.Button(row, text=text, command=lambda s=stage: self.decide(s)).pack(side="left", padx=(0, 4))
        self.canvas = tk.Canvas(right, bg=app.colors["panel"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.draw())

    def decide(self, stage):
        sel = self.queue.selected()
        if sel:
            self.app.store.update("paper", int(sel), stage=stage)
            self.refresh()

    def show(self, sel):
        if sel:
            p = self.app.store.get("paper", int(sel))
            ak.set_text(self.abstract, p["abstract"] or "No abstract recorded.", readonly=True)

    def draw(self):
        c, col, s = self.canvas, self.app.colors, self.app.scale
        c.delete("all")
        p = rv.prisma(self.app.store.list("paper"))
        w = max(c.winfo_width(), 300)

        def box(x, y, text, width=250, height=52, side=False):
            x0, y0 = x * s, y * s
            c.create_rectangle(x0, y0, x0 + width * s, y0 + height * s, fill=col["bg"] if side else col["sel"], outline=col["line"])
            c.create_text(x0 + width * s / 2, y0 + height * s / 2, text=text, fill=col["ink"], width=(width - 12) * s, justify="center", font=(ak.FONT, 9))
            return x0 + width * s / 2, y0, y0 + height * s, x0 + width * s
        sx = min(290, (w / s - 40) / 2)
        steps = [("Records identified\nn = %d" % p["identified"], "Duplicates removed\nn = %d" % p["duplicates"]),
                 ("Records screened\nn = %d" % p["screened"], "Excluded at title\nn = %d" % p["excluded_title"]),
                 ("Abstracts assessed\nn = %d" % (p["screened"] - p["excluded_title"]), "Excluded at abstract\nn = %d" % p["excluded_abstract"]),
                 ("Full texts assessed\nn = %d" % p["full_text"], "Excluded at full text\nn = %d" % p["excluded_full"]),
                 ("Studies included\nn = %d" % p["included"], "Awaiting a decision\nn = %d" % p["pending"])]
        for i, (main, side) in enumerate(steps):
            y = 10 + i * 78
            mx, y0, y1, right = box(10, y, main, min(250, sx - 30))
            _, sy0, sy1, _ = box(sx, y, side, min(220, sx - 10), side=True)
            c.create_line(right, (y0 + y1) / 2, sx * s, (y0 + y1) / 2, arrow="last", fill=col["muted"])
            if i < len(steps) - 1:
                c.create_line(mx, y1, mx, y1 + 26 * s, arrow="last", fill=col["muted"])

    def refresh(self):
        rows = self.app.store.list("paper", "stage='Identified'")
        self.queue.fill([(r["id"], (r["title"], r["year"] or "")) for r in rows])
        self.draw()


class Themes(ttk.Frame):
    title = "Themes"

    def __init__(self, parent, app):
        super().__init__(parent)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.themes = ak.EntityView(nb, app, "theme")
        self.links = ak.EntityView(nb, app, "link")
        nb.add(self.themes, text="Themes")
        nb.add(self.links, text="Which paper says what")

    def refresh(self):
        self.themes.refresh()
        self.links.refresh()

    def commit(self):
        return self.themes.commit() and self.links.commit()


class Matrix(ttk.Frame):
    title = "Matrix"
    MARK = {"Supports": "+", "Contradicts": "-", "Qualifies": "~", "Covers": "o"}

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="+ supports    - contradicts    ~ qualifies    o covers", style="Muted.TLabel").pack(side="left")
        ttk.Button(top, text="Export CSV", command=self.export).pack(side="right")
        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg=app.colors["panel"], highlightthickness=0)
        v, h = ttk.Scrollbar(holder, command=self.canvas.yview), ttk.Scrollbar(holder, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v.set, xscrollcommand=h.set)
        h.pack(side="bottom", fill="x")
        v.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

    def refresh(self):
        c, col, s = self.canvas, self.app.colors, self.app.scale
        c.delete("all")
        papers, themes, links = data(self.app.store)
        rows, counts = rv.matrix(papers, themes, links)
        if not rows or not themes:
            c.create_text(20 * s, 20 * s, anchor="w", fill=col["muted"], text="Include papers and add themes to build the matrix.")
            return
        left, cw, ch, top = 240 * s, 104 * s, 28 * s, 54 * s
        fills = {"+": col["ok"], "-": col["danger"], "~": col["warning"], "o": col["accent"]}
        for j, t in enumerate(themes):
            x = left + j * cw
            c.create_text(x + cw / 2, 20 * s, text=ak.short(t["name"], 15), fill=col["ink"], font=(ak.FONT, 9, "bold"))
            c.create_text(x + cw / 2, 38 * s, text="%d paper(s)" % counts[t["id"]], fill=col["muted"], font=(ak.FONT, 8))
        for i, (p, d) in enumerate(rows):
            y = top + i * ch
            c.create_text(8 * s, y + ch / 2, anchor="w", text=ak.short("%s: %s" % (rv.cite(p), p["title"]), 40), fill=col["ink"], font=(ak.FONT, 9))
            for j, t in enumerate(themes):
                x = left + j * cw
                c.create_rectangle(x, y, x + cw, y + ch, outline=col["line"], fill=col["panel"])
                if t["id"] in d:
                    m = self.MARK.get(d[t["id"]], "o")
                    c.create_rectangle(x + 3, y + 3, x + cw - 3, y + ch - 3, fill=fills[m], outline="")
                    c.create_text(x + cw / 2, y + ch / 2, text=m, fill="#ffffff", font=(ak.FONT, 11, "bold"))
        c.configure(scrollregion=(0, 0, left + len(themes) * cw + 12, top + len(rows) * ch + 12))

    def export(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".csv", initialfile="synthesis-matrix.csv")
        if path:
            with open(path, "w", encoding="utf-8-sig", newline="") as fh:
                fh.write(rv.to_csv(*data(self.app.store)))
            self.app.status("Saved " + path)


class Analysis(ttk.Frame):
    title = "Gaps and outline"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        top = ttk.Frame(self)
        top.pack(fill="x")
        self.topic = tk.StringVar()
        ak.labeled_entry(top, "Review topic", self.topic, 50).pack(side="left")
        ttk.Button(top, text="Build outline", style="Accent.TButton", command=self.build).pack(side="left", padx=8, anchor="s")
        ttk.Button(top, text="Copy", command=self.copy).pack(side="left", anchor="s")
        ttk.Label(self, text="Possible gaps", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        frame, self.gaps = ak.make_text(self, app.colors, height=6)
        frame.pack(fill="x")
        ttk.Label(self, text="Outline organised by theme", style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        frame, self.out = ak.make_text(self, app.colors, height=12)
        frame.pack(fill="both", expand=True)

    def build(self):
        self.app.store.set_setting("topic", self.topic.get())
        papers, themes, links = data(self.app.store)
        ak.set_text(self.gaps, "\n".join("- " + g for g in rv.gaps(papers, themes, links)))
        ak.set_text(self.out, rv.outline(papers, themes, links, self.topic.get() or "the topic"))

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(ak.get_text(self.out))
        self.app.status("Outline copied")

    def refresh(self):
        self.topic.set(self.app.store.get_setting("topic"))
        self.build()


class APP(ak.BaseApp):
    APP_NAME, ACCENT = "Literature Matrix", "#15803d"
    SCHEMA, SAMPLE = SCHEMA, staticmethod(sample)
    VIEWS = [Papers, Screening, Themes, Matrix, Analysis, ak.DataView]


def main(argv=None):
    return ak.main(APP, argv)
