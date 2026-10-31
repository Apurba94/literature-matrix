# Literature Matrix

A literature review should compare sources across ideas, not summarise them one after another. This program keeps you doing
the former.

* **Papers:** import BibTeX or RIS, with duplicates caught by DOI or title. Record method, context, sample, quality, findings
  and limitations.
* **Screening:** decide on each record, and a PRISMA-style flow diagram with exact counts updates as you go.
* **Themes:** record whether each paper supports, contradicts, qualifies or simply covers a theme.
* **Matrix:** papers against themes at a glance, with CSV export. The empty columns are the interesting ones.
* **Gaps:** themes with little evidence, one method or setting dominating, ageing evidence, low quality, and conflicts in
  findings that a new study could explain.
* **Outline:** a review skeleton organised by theme, placing sources under agreement, disagreement and limits.

`--demo` opens a temporary database with fictional sample papers.

## Download

Windows: get the `.exe` from [Releases](https://github.com/Apurba94/literature-matrix/releases/latest) and double-click it. No installation or Python is needed.
Windows may show a SmartScreen warning the first time because the program is not code-signed: choose *More info*, then *Run anyway*.

## From source

```bash
python -m literature_matrix
python -m unittest discover -s tests -t .
python build_exe.py
```

## Limits

The outline is a structure for your writing, not finished text. The diagram follows the PRISMA flow, but you should check
your journal's current template and reporting requirements. Gap detection only sees the fields you fill in.

## License

MIT
