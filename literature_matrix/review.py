"""Review logic: BibTeX and RIS import, screening counts for a PRISMA diagram, the theme matrix, gap analysis and
outlines. A synthesis matrix is about comparing sources across themes, not summarising them one by one."""
import csv
import io
import re
from collections import Counter

STAGES = ["Identified", "Duplicate", "Excluded at title", "Excluded at abstract", "Excluded at full text", "Included"]
EXCLUDE_REASONS = ["Wrong population", "Wrong intervention", "Wrong outcome", "Wrong study design", "Not peer reviewed", "Not in English", "No full text", "Other"]
QUALITY = ["High", "Moderate", "Low", "Not assessed"]
METHODS = ["Randomised trial", "Quasi-experiment", "Cohort", "Cross-sectional survey", "Case study", "Interviews", "Ethnography", "Mixed methods",
           "Systematic review", "Meta-analysis", "Modelling", "Theoretical", "Other"]


def split_tags(text):
    return [t.strip() for t in re.split(r"[;,]", text or "") if t.strip()]


def _entries(text):
    pos = 0
    while True:
        m = re.compile(r"@(\w+)\s*\{").search(text, pos)
        if not m:
            return
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        pos = i
        if m.group(1).lower() not in ("comment", "string", "preamble"):
            yield text[m.end():i - 1]


def _clean(v):
    return re.sub(r"\s+", " ", re.sub(r"[{}]", "", v)).strip()


def parse_bibtex(text):
    out = []
    for body in _entries(text):
        key, _, rest = body.partition(",")
        f = {}
        for m in re.finditer(r"([\w-]+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|[^,\n]+)", rest):
            f[m.group(1).lower()] = _clean(m.group(2).strip().strip('"'))
        if f.get("title"):
            y = re.search(r"\d{4}", f.get("year", ""))
            out.append({"citekey": key.strip(), "title": f["title"], "authors": f.get("author", "").replace(" and ", "; "), "year": int(y.group()) if y else None,
                        "venue": f.get("journal") or f.get("booktitle"), "doi": f.get("doi"), "abstract": f.get("abstract")})
    return out


def parse_ris(text):
    out, cur, authors = [], None, []
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])\s{2}-\s?(.*)$", line.strip())
        if not m:
            continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur, authors = {}, []
        elif cur is None:
            continue
        elif tag == "ER":
            cur["authors"] = "; ".join(authors)
            if cur.get("title"):
                out.append(cur)
            cur = None
        elif tag in ("AU", "A1"):
            authors.append(val)
        elif tag in ("TI", "T1"):
            cur["title"] = val
        elif tag in ("JO", "JF", "T2"):
            cur.setdefault("venue", val)
        elif tag in ("PY", "Y1"):
            y = re.search(r"\d{4}", val)
            if y:
                cur["year"] = int(y.group())
        elif tag == "DO":
            cur["doi"] = val
        elif tag == "AB":
            cur["abstract"] = val
    return out


def parse_any(text):
    if re.search(r"^\s*@\w+\s*\{", text, re.M):
        return parse_bibtex(text)
    if re.search(r"^TY\s{2}-", text, re.M):
        return parse_ris(text)
    raise ValueError("this does not look like BibTeX or RIS")


def _key(title):
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def import_papers(store, text):
    """Add new papers as Identified; duplicates by DOI or title are recorded as Duplicate. Returns (added, duplicates)."""
    existing = store.list("paper")
    dois = {(p["doi"] or "").lower() for p in existing if p["doi"]}
    titles = {_key(p["title"]) for p in existing}
    added = dup = 0
    for r in parse_any(text):
        is_dup = (r.get("doi") or "").lower() in dois and r.get("doi") or _key(r["title"]) in titles
        row = {k: v for k, v in r.items() if v is not None and k in {f.name for f in store.schema["paper"].fields}}
        row["stage"] = "Duplicate" if is_dup else "Identified"
        store.insert("paper", **row)
        dup += 1 if is_dup else 0
        added += 0 if is_dup else 1
        titles.add(_key(r["title"]))
        if r.get("doi"):
            dois.add(r["doi"].lower())
    return added, dup


def prisma(papers):
    """Counts for the PRISMA 2020 flow from the stage of each record."""
    c = Counter(p["stage"] for p in papers)
    identified = len(papers)
    after_dups = identified - c["Duplicate"]
    screened = after_dups
    title_out = c["Excluded at title"]
    abstract_out = c["Excluded at abstract"]
    full = screened - title_out - abstract_out
    out = {"identified": identified, "duplicates": c["Duplicate"], "screened": screened, "excluded_title": title_out, "excluded_abstract": abstract_out,
           "full_text": full, "excluded_full": c["Excluded at full text"], "included": c["Included"], "pending": c["Identified"],
           "reasons": Counter(p["reason"] for p in papers if p["stage"] == "Excluded at full text" and p.get("reason"))}
    return out


def matrix(papers, themes, links):
    """Rows of (paper, {theme id: note}) for the included papers, and how many papers cover each theme."""
    by_paper = {}
    for l in links:
        by_paper.setdefault(l["paper_id"], {})[l["theme_id"]] = l["stance"] or "Covers"
    rows = [(p, by_paper.get(p["id"], {})) for p in papers if p["stage"] == "Included"]
    counts = {t["id"]: sum(1 for _, d in rows if t["id"] in d) for t in themes}
    return rows, counts


def gaps(papers, themes, links):
    """What the included literature does not yet say. Returns plain sentences."""
    inc = [p for p in papers if p["stage"] == "Included"]
    out = []
    if not inc:
        return ["No included papers yet."]
    rows, counts = matrix(papers, themes, links)
    for t in themes:
        n = counts[t["id"]]
        if n == 0:
            out.append('No included paper addresses the theme "%s".' % t["name"])
        elif n <= max(1, len(inc) // 10):
            out.append('Only %d paper(s) address the theme "%s".' % (n, t["name"]))
    methods = Counter(p["method"] for p in inc if p["method"])
    if methods and len(inc) >= 4:
        m, k = methods.most_common(1)[0]
        if k / len(inc) >= 0.6:
            out.append("%d of %d papers use %s: other designs are under-represented." % (k, len(inc), m.lower()))
    contexts = Counter(p["context"] for p in inc if p["context"])
    if contexts and len(inc) >= 4:
        c, k = contexts.most_common(1)[0]
        if k / len(inc) >= 0.6:
            out.append("%d of %d papers come from %s: other settings are missing." % (k, len(inc), c))
    years = sorted(p["year"] for p in inc if p["year"])
    if len(years) >= 4 and years[len(years) // 2] < years[-1] - 5:
        out.append("Half of the evidence is older than %d: recent work may have moved on." % years[len(years) // 2])
    weak = sum(1 for p in inc if p.get("quality") == "Low")
    if weak and weak / len(inc) >= 0.4:
        out.append("%d of %d papers are rated low quality." % (weak, len(inc)))
    tensions = {}
    for l in links:
        tensions.setdefault(l["theme_id"], set()).add(l["stance"])
    for t in themes:
        s = tensions.get(t["id"], set())
        if "Supports" in s and "Contradicts" in s:
            out.append('Findings conflict on "%s": explaining why is a possible contribution.' % t["name"])
    return out or ["No obvious gaps from these fields. Look at what the theme list itself leaves out."]


def surname(authors):
    first = (authors or "").split(";")[0].strip()
    if not first:
        return "Anonymous"
    return first.split(",")[0].strip() if "," in first else first.split()[-1]


def cite(p):
    n = len([a for a in (p["authors"] or "").split(";") if a.strip()])
    who = surname(p["authors"])
    if n == 2:
        who += " and %s" % surname((p["authors"] or "").split(";")[1])
    elif n > 2:
        who += " et al."
    return "%s (%s)" % (who, p["year"] or "n.d.")


def outline(papers, themes, links, topic="the topic"):
    """A review skeleton organised by theme, not by paper, with sources placed under each stance."""
    rows, counts = matrix(papers, themes, links)
    out = ["Literature review: %s" % topic, "", "Introduction", "Scope, search strategy and how %d sources were selected." % len(rows), ""]
    for t in themes:
        out.append(t["name"])
        if t.get("description"):
            out.append(t["description"])
        groups = {}
        for p, d in rows:
            if t["id"] in d:
                groups.setdefault(d[t["id"]], []).append(p)
        if not groups:
            out.append("No included sources yet.")
        for stance in ("Supports", "Contradicts", "Qualifies", "Covers"):
            ps = groups.get(stance)
            if ps:
                out.append("%s: %s" % ({"Supports": "Agreement", "Contradicts": "Disagreement", "Qualifies": "Conditions and limits", "Covers": "Discussed by"}[stance],
                                       "; ".join(cite(p) for p in sorted(ps, key=lambda x: x["year"] or 0))))
        out.append("")
    out += ["Gaps and direction for this study"] + ["- " + g for g in gaps(papers, themes, links)]
    return "\n".join(out) + "\n"


def to_csv(papers, themes, links):
    rows, _ = matrix(papers, themes, links)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Source", "Method", "Context", "Sample", "Findings", "Quality"] + [t["name"] for t in themes])
    for p, d in rows:
        w.writerow([cite(p), p["method"] or "", p["context"] or "", p["sample"] or "", p["findings"] or "", p["quality"] or ""] + [d.get(t["id"], "") for t in themes])
    return buf.getvalue()


def timeline(papers):
    """{year: count} of the included papers."""
    return dict(sorted(Counter(p["year"] for p in papers if p["stage"] == "Included" and p["year"]).items()))
