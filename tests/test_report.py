import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import blender_stubs  # noqa: E402

blender_stubs.install()

import build_zip  # noqa: E402
import measure_overlay as mo  # noqa: E402
from blender_stubs import FakeContext, FakeObject, FakeSettings  # noqa: E402


def geometry(report):
    return {row[0]: row[1] for heading, rows in report["sections"] if heading == "Geometry" for row in rows}


def dimensions(report):
    return {row[0]: row[1] for heading, rows in report["sections"]
            if heading in ("Dimensions", "Selection Size") for row in rows}


def headings(report):
    return [heading for heading, _ in report["sections"]]


class ReportTests(unittest.TestCase):
    def test_no_active_object(self):
        report = mo.build_report(FakeContext(None))
        self.assertEqual(report["title"], "No active object")
        self.assertEqual(report["sections"], [])

    def test_single_mesh(self):
        cube = FakeObject("Cube")
        report = mo.build_report(FakeContext(cube))
        self.assertEqual(report["title"], "Cube")
        self.assertEqual(geometry(report), {"Vertices": "8", "Edges": "12", "Faces": "6"})
        self.assertEqual(dimensions(report), {"X": "2.000 m", "Y": "2.000 m", "Z": "2.000 m"})

    def test_modifier_note_follows_setting(self):
        cube = FakeObject("Cube", modifiers=True)
        on = mo.build_report(FakeContext(cube, settings=FakeSettings(include_modifiers=True)))
        off = mo.build_report(FakeContext(cube, settings=FakeSettings(include_modifiers=False)))
        self.assertIn("with modifiers", on["subtitle"])
        self.assertNotIn("with modifiers", off["subtitle"])

    def test_multi_selection_combines_everything(self):
        cube = FakeObject("Cube")  # spans x 0..2
        rock = FakeObject("Rock", counts=(500, 900, 400), dims=(1, 1, 1), offset=(5, 0, 0))  # x 5..6
        report = mo.build_report(FakeContext(cube, [cube, rock]))
        self.assertEqual(report["title"], "2 meshes selected")
        self.assertIn("Active: Cube", report["subtitle"])
        self.assertEqual(headings(report)[0], "Selection Size")
        self.assertEqual(dimensions(report)["X"], "6.000 m")
        self.assertEqual(geometry(report)["Vertices"], "508")
        self.assertEqual(geometry(report)["Faces"], "406")

    def test_huge_selection_is_capped(self):
        objs = [FakeObject(f"Obj{i}") for i in range(mo.MAX_OBJECTS + 1)]
        report = mo.build_report(FakeContext(objs[0], objs))
        self.assertIn(f"First {mo.MAX_OBJECTS}", report["subtitle"])

    def test_edit_mode_shows_selected_over_total(self):
        cube = FakeObject("Cube", mode="EDIT")
        report = mo.build_report(FakeContext(cube, in_mode=[cube]))
        self.assertIn("Edit Mode", report["subtitle"])
        self.assertEqual(geometry(report), {"Vertices": "3 / 100", "Edges": "2 / 200", "Faces": "1 / 101"})

    def test_non_mesh_object(self):
        camera = FakeObject("Camera", type="CAMERA")
        report = mo.build_report(FakeContext(camera))
        self.assertIn("Not a mesh (Camera)", report["subtitle"])
        self.assertEqual(report["sections"], [])

    def test_sections_can_be_hidden(self):
        cube = FakeObject("Cube")
        report = mo.build_report(FakeContext(cube, settings=FakeSettings(show_dimensions=False)))
        self.assertEqual(headings(report), ["Geometry"])
        report = mo.build_report(FakeContext(cube, settings=FakeSettings(show_geometry=False)))
        self.assertEqual(headings(report), ["Dimensions"])

    def test_report_to_text(self):
        text = mo.report_to_text(mo.build_report(FakeContext(FakeObject("Cube"))))
        self.assertTrue(text.startswith("Cube"))
        self.assertIn("Dimensions:", text)
        self.assertIn("  X: 2.000 m", text)
        self.assertIn("  Faces: 6", text)


class BudgetTests(unittest.TestCase):
    def report_for(self, budget):
        cube = FakeObject("Cube")  # 6 faces
        settings = FakeSettings(use_budget=True, budget=budget)
        return mo.build_report(FakeContext(cube, settings=settings))

    def test_under_budget_is_good(self):
        report = self.report_for(10)  # 60%
        self.assertEqual(report["accent"], "good")
        self.assertEqual(geometry(report)["Faces"], "6  (60%)")

    def test_near_budget_warns(self):
        self.assertEqual(self.report_for(7)["accent"], "warn")  # 86%

    def test_over_budget_is_bad(self):
        self.assertEqual(self.report_for(5)["accent"], "bad")  # 120%

    def test_budget_disabled(self):
        self.assertEqual(mo.budget_state(FakeSettings(use_budget=False), 999), (None, None))


class UnitTests(unittest.TestCase):
    def test_no_unit_system_has_no_suffix(self):
        ctx = FakeContext(FakeObject("Cube"), unit_system="NONE")
        self.assertEqual(mo.fmt_length(ctx, 2.0), "2.000")

    def test_unit_scale_is_applied(self):
        ctx = FakeContext(FakeObject("Cube"), scale_length=0.01)
        self.assertEqual(mo.fmt_length(ctx, 100.0), "1.000 m")


class PackagingTests(unittest.TestCase):
    def test_versions_are_in_sync(self):
        py_version, manifest_version = build_zip.read_versions()
        self.assertEqual(py_version, manifest_version)


if __name__ == "__main__":
    unittest.main()
