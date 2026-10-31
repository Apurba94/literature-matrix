import csv
import io
import os
import shutil
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from literature_matrix import app as A
from literature_matrix import appkit as ak
from literature_matrix import review as rv

BIB = """@article{lee2020, author = {Lee, Ana and Park, Ji}, title = {A {Study} of Things}, journal = {J. Things}, year = {2020}, doi = {10.1/abc}}
@comment{skip}
@inproceedings{kim2021, author = "Kim, Bo", title = "Other work", booktitle = "Proc", year = 2021}
"""
RIS = "TY  - JOUR\nAU  - Doe, Jane\nAU  - Roe, Rick\nTI  - Ris paper\nJO  - Journal\nPY  - 2019/01/01\nDO  - 10.2/xyz\nER  - \n"


def store():
    s = ak.Store(A.SCHEMA)
    A.sample(s)
    return s


class TestImport(unittest.TestCase):
    def test_bibtex(self):
        rows = rv.parse_bibtex(BIB)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["citekey"], "lee2020")
        self.assertEqual(rows[0]["title"], "A Study of Things")
        self.assertEqual(rows[0]["authors"], "Lee, Ana; Park, Ji")
        self.assertEqual((rows[0]["year"], rows[0]["doi"]), (2020, "10.1/abc"))
        self.assertEqual(rows[1]["venue"], "Proc")

    def test_ris_and_detection(self):
        r = rv.parse_any(RIS)[0]
        self.assertEqual((r["title"], r["authors"], r["year"]), ("Ris paper", "Doe, Jane; Roe, Rick", 2019))
        with self.assertRaises(ValueError):
            rv.parse_any("plain words")

    def test_duplicates(self):
        s = ak.Store(A.SCHEMA)
        self.assertEqual(rv.import_papers(s, BIB), (2, 0))
        self.assertEqual(rv.import_papers(s, BIB), (0, 2))
        same_title = "@article{x, title = {a study of things!}, year = 2020}"
        self.assertEqual(rv.import_papers(s, same_title), (0, 1))
        self.assertEqual(rv.import_papers(s, RIS), (1, 0))
        self.assertEqual(s.count("paper", "stage='Duplicate'"), 3)


class TestPrisma(unittest.TestCase):
    def test_counts_are_consistent(self):
        s = store()
        p = rv.prisma(s.list("paper"))
        self.assertEqual(p["identified"], 11)
        self.assertEqual(p["duplicates"], 1)
        self.assertEqual(p["screened"], 10)
        self.assertEqual((p["excluded_title"], p["excluded_abstract"], p["excluded_full"]), (2, 1, 1))
        self.assertEqual(p["included"], 5)
        self.assertEqual(p["pending"], 1)
        self.assertEqual(p["reasons"]["Wrong outcome"], 1)
        self.assertEqual(p["full_text"], p["included"] + p["excluded_full"] + p["pending"])


class TestMatrix(unittest.TestCase):
    def setUp(self):
        self.s = store()
        self.data = self.s.list("paper"), self.s.list("theme"), self.s.list("link")

    def test_matrix(self):
        rows, counts = rv.matrix(*self.data)
        self.assertEqual(len(rows), 5)
        names = {t["name"]: counts[t["id"]] for t in self.data[1]}
        self.assertEqual(names, {"Autonomy": 3, "Isolation": 2, "Productivity": 3, "Caring responsibilities": 0})

    def test_gaps(self):
        text = " ".join(rv.gaps(*self.data))
        self.assertIn('No included paper addresses the theme "Caring responsibilities"', text)
        self.assertIn("4 of 5 papers use cross-sectional survey", text)
        self.assertIn("4 of 5 papers come from UK", text)
        self.assertIn('Findings conflict on "Productivity"', text)
        self.assertEqual(rv.gaps([], [], []), ["No included papers yet."])

    def test_citation_forms(self):
        self.assertEqual(rv.cite({"authors": "Lee, Ana", "year": 2020}), "Lee (2020)")
        self.assertEqual(rv.cite({"authors": "Lee, Ana; Park, Ji", "year": 2020}), "Lee and Park (2020)")
        self.assertEqual(rv.cite({"authors": "A B; C D; E F", "year": None}), "B et al. (n.d.)")
        self.assertEqual(rv.cite({"authors": "", "year": 2000}), "Anonymous (2000)")

    def test_outline_is_by_theme(self):
        text = rv.outline(*self.data, "remote work")
        self.assertTrue(text.startswith("Literature review: remote work"))
        self.assertLess(text.index("Autonomy"), text.index("Isolation"))
        self.assertIn("Disagreement: Analyst (2021)", text)
        self.assertIn("No included sources yet.", text)
        self.assertIn("Gaps and direction", text)

    def test_csv(self):
        rows = list(csv.reader(io.StringIO(rv.to_csv(*self.data))))
        self.assertEqual(rows[0][:2], ["Source", "Method"])
        self.assertEqual(len(rows), 6)
        self.assertIn("Supports", rows[1])

    def test_timeline(self):
        self.assertEqual(rv.timeline(self.data[0]), {2019: 1, 2020: 1, 2021: 2, 2022: 1})


class TestGui(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = ak.Store(A.SCHEMA, os.path.join(self.dir, "t.sqlite3"), A.APP.APP_NAME)
        A.sample(self.store)
        try:
            self.app = A.APP(self.store)
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.errors = []
        self.app.report_callback_exception = lambda e, v, t: self.errors.append(repr(v))
        self.app.update()

    def tearDown(self):
        self.store.close()
        self.app.destroy()
        shutil.rmtree(self.dir, ignore_errors=True)
        self.assertEqual(self.errors, [])

    def test_every_screen_in_both_themes(self):
        for theme in ("Dark", "Light"):
            self.app.set_theme(theme)
            for t in self.app.titles():
                self.app.navigate(t)
                self.app.update()

    def test_screening_decision_moves_counts(self):
        self.app.navigate("Screening")
        v = self.app.views["Screening"]
        rid = self.store.list("paper", "stage='Identified'")[0]["id"]
        v.queue.tree.selection_set(str(rid))
        v.decide("Included")
        self.assertEqual(self.store.get("paper", rid)["stage"], "Included")
        self.assertEqual(v.queue.tree.get_children(), ())

    def test_import_screen(self):
        v = self.app.views["Papers"]
        n = self.store.count("paper")
        v.load(BIB)
        self.assertEqual(self.store.count("paper"), n + 2)
        with mock.patch("tkinter.messagebox.showerror") as err:
            v.load("nonsense")
        self.assertTrue(err.called)

    def test_outline_screen(self):
        self.app.navigate("Gaps and outline")
        a = self.app.views["Gaps and outline"]
        self.assertIn("Caring responsibilities", ak.get_text(a.gaps))
        a.topic.set("New topic")
        a.build()
        self.assertEqual(self.store.get_setting("topic"), "New topic")
        self.assertIn("New topic", ak.get_text(a.out))

    def test_empty_database(self):
        self.store.close()
        self.app.destroy()
        self.store = ak.Store(A.SCHEMA, os.path.join(self.dir, "e.sqlite3"), A.APP.APP_NAME)
        self.app = A.APP(self.store)
        for t in self.app.titles():
            self.app.navigate(t)
            self.app.update()


if __name__ == "__main__":
    unittest.main()
