"""Local Tk integration tests; requires a desktop/Tk display, not a Pico."""
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from midi_gui import ConverterWindow
from melody_format import read_document

class WindowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=tk.Tk()
        self.root.withdraw()
        self.app=ConverterWindow(self.root)
        self.app.folder.set(self.temp.name)
        self.errors=[]
        self.error_patch=patch("midi_gui.messagebox.showerror",side_effect=lambda *a,**k:self.errors.append(a))
        self.error_patch.start()

    def tearDown(self):
        self.wait()
        self.app.close()
        self.error_patch.stop()
        self.temp.cleanup()

    def wait(self):
        deadline=time.monotonic()+30
        while self.app.busy and time.monotonic()<deadline:
            self.root.update()
            time.sleep(.01)
        self.root.update()
        self.assertFalse(self.app.busy,"background job did not finish")

    def demo(self,variant):
        self.app.load_demo(variant)
        self.wait()
        self.root.update()
        self.assertEqual(self.app.selection()["track"],2)
        self.assertEqual(self.app.transpose.get(),"5")
        self.assertEqual(self.app.filename.get(),"queens_"+variant)

    def test_example_button_to_generated_json_and_stale_result(self):
        for variant,count in (("first",132),("full",572)):
            self.demo(variant)
            self.app.generate_button.invoke()
            self.wait()
            self.assertFalse(self.errors,self.errors)
            self.assertIsNotNone(self.app.result)
            self.assertEqual(len(read_document(self.app.result[0])["notes"]),count)
        self.app.transpose.set("4")
        self.assertIsNone(self.app.result)
        self.assertIn("disabled",self.app.preview_button.state())

    def test_bad_numeric_input_and_cancelled_overwrite_preserve_files(self):
        self.demo("first")
        target=Path(self.temp.name)/"queens_first.json"
        target.write_bytes(b"keep")
        self.app.speed.set("0")
        self.app.generate()
        self.assertTrue(self.errors)
        self.assertEqual(target.read_bytes(),b"keep")
        self.app.speed.set("100")
        with patch("midi_gui.messagebox.askyesno",return_value=False):
            self.app.generate()
        self.assertFalse(self.app.busy)
        self.assertEqual(target.read_bytes(),b"keep")

    def test_bad_file_clears_previous_selection_and_result(self):
        self.demo("first")
        self.app.load_file(Path(self.temp.name)/"missing.mid")
        self.wait()
        self.assertIsNone(self.app.score)
        self.assertIsNone(self.app.result)
        self.assertIn("disabled",self.app.generate_button.state())
        self.assertTrue(self.errors)

    def test_two_column_layout_fits_short_windows_with_both_tabs(self):
        self.demo("full")
        self.app.generate()
        self.wait()
        self.assertFalse(self.errors)
        self.root.deiconify()

        def assert_inside_parent(parent):
            for widget in parent.winfo_children():
                if not widget.winfo_ismapped():
                    continue
                x, y = widget.winfo_x(), widget.winfo_y()
                width, height = widget.winfo_width(), widget.winfo_height()
                with self.subTest(widget=str(widget)):
                    self.assertGreaterEqual(x, 0)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(x + width, parent.winfo_width() + 2)
                    self.assertLessEqual(y + height, parent.winfo_height() + 2)
                assert_inside_parent(widget)

        for size in ("1180x680", "1080x620", "940x580"):
            self.root.geometry(size)
            self.root.update()
            dimensions = self.root.winfo_width(), self.root.winfo_height()
            for tab in (self.app.basic, self.app.advanced):
                with self.subTest(size=size, tab=str(tab)):
                    self.app.settings_tabs.select(tab)
                    self.root.update()
                    self.assertEqual(dimensions, (self.root.winfo_width(), self.root.winfo_height()))
                    self.assertGreaterEqual(self.app.right.winfo_x(),
                                            self.app.left.winfo_x() + self.app.left.winfo_width())
                    self.assertGreaterEqual(self.app.tree.winfo_height(), 72)
                    assert_inside_parent(self.root)

    def test_background_load_keeps_tk_responsive(self):
        from midi_gui import engine
        read=engine.read_score
        def slow(file):
            time.sleep(.2)
            return read(file)
        heartbeats=[]
        with patch("midi_gui.engine.read_score",side_effect=slow):
            self.root.after(20,lambda:heartbeats.append(True))
            self.app.load_demo("first")
            self.assertIn("disabled",self.app.generate_button.state())
            self.wait()
        self.assertTrue(heartbeats)
        self.assertFalse(self.errors)

if __name__=="__main__":
    unittest.main()
