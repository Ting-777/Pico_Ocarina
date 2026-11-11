"""GUI form tests without a display; reuse the production conversion engine."""
import argparse
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import midi_gui_model as gui
from midi_gui_audio import MidiPlayer
from melody_format import MelodyError
import midi_to_melody as engine

parser=argparse.ArgumentParser(add_help=False)
parser.add_argument("--checker")
options,rest=parser.parse_known_args()

class GuiFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.score=engine.read_score(ROOT/"examples/queens_road_east/source.mid")

    def test_both_example_forms_equal_golden_files(self):
        for variant in ("first","full"):
            source,digest,recipe=gui.demo(variant)
            self.assertEqual(self.score.sha256,digest)
            form=gui.form_for_demo(self.score,recipe)
            document,report=gui.convert(self.score,2,0,form)
            expected=json.loads((source.parent/("melody_%s_v1_proposed.json"%variant)).read_text(encoding="utf-8"))
            for field in ("notes","duration_us","countdown_us","title"):
                self.assertEqual(document[field],expected[field])
            with tempfile.TemporaryDirectory() as folder:
                paths=engine.emit_conversion(source,document,report,Path(folder)/"gui.json")
                if options.checker:
                    subprocess.run([options.checker,str(paths[0])],check=True,capture_output=True)
            self.assertIn(str(len(document["notes"])),gui.summary(document,report))

    def test_percent_countdown_and_beat_conversion_are_exact(self):
        form=gui.Form(transpose="+5",speed_percent="80",countdown_seconds="0.5",start_beat="44",end_beat="140")
        settings=gui.settings(self.score,2,0,form)
        self.assertEqual(settings["speed"],Fraction(4,5))
        self.assertEqual(settings["countdown_us"],500000)
        self.assertEqual(settings["start_tick"],4224)
        self.assertEqual(settings["end_tick"],13440)
        self.assertEqual(gui.settings(self.score,2,0,gui.Form())["end_tick"],None)
        self.assertEqual(gui.beat_tick("1/2",96,"片段"),48)

    def test_bad_numbers_report_errors(self):
        for field,value in (("transpose","5.0"),("transpose","abc"),("speed_percent","0"),
                ("speed_percent","-1"),("speed_percent","nan"),("countdown_seconds","11"),
                ("countdown_seconds","0.0000001"),("start_beat","-1"),("end_beat","1/7")):
            with self.subTest(field=field,value=value),self.assertRaises(MelodyError):
                gui.settings(self.score,2,0,replace(gui.Form(),**{field:value}))

    def test_output_names_cannot_be_paths_or_windows_reserved_files(self):
        for name in ("","../source","a/b","a\\b","CON","con.json","NUL.foo","com1","song.","a:bad"):
            with self.subTest(name=name),self.assertRaises(MelodyError):
                gui.output_path("out/gui",name)
        self.assertEqual(gui.output_path("out/gui","歌曲.json").name,"歌曲.json")
        with self.assertRaises(MelodyError):
            gui.output_path("","song")

    def test_gui_does_not_silently_fold_or_resolve_polyphony(self):
        with self.assertRaises(MelodyError):
            gui.convert(self.score,2,0,gui.Form(transpose="0",start_beat="44",end_beat="140"))
        with self.assertRaisesRegex(MelodyError,"同时"):
            gui.convert(self.score,2,0,gui.Form(transpose="5",start_beat="44",end_beat="492"))
        document,report=gui.convert(self.score,2,0,gui.Form(transpose="5",start_beat="44",end_beat="492",polyphony="octave-highest"))
        self.assertEqual(len(document["notes"]),572)
        self.assertEqual(len(report["omitted_notes"]),5)

    def test_mci_player_lifecycle_and_failed_start_closes_device(self):
        class Fake(MidiPlayer):
            def __init__(self):
                super().__init__()
                self.commands=[]
                self.failure=False
            def _command(self,text):
                self.commands.append(text)
                if text.startswith("play") and self.failure:
                    raise RuntimeError("test device unavailable")
                return "playing" if text.startswith("status") else ""
        player=Fake()
        player.play("out/gui/试听.mid",123)
        self.assertTrue(player.opened)
        self.assertTrue(player.playing())
        self.assertTrue(player.commands[-2].endswith("from 123"))
        player.stop()
        self.assertFalse(player.opened)
        self.assertTrue(player.commands[-1].startswith("close"))
        player.failure=True
        with self.assertRaises(RuntimeError):
            player.play("out/gui/试听.mid")
        self.assertFalse(player.opened)
        self.assertTrue(player.commands[-1].startswith("close"))

if __name__=="__main__":
    unittest.main(argv=[sys.argv[0],*rest])
