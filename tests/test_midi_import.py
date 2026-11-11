"""MIDI source -> melody JSON -> firmware parser/upload, without hardware."""
import argparse
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import mido
import midi_to_melody as importer
from melody_format import MelodyError, encode_document, preview_bytes, read_document
import upload_melody

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--checker")
parser.add_argument("--device")
OPTIONS, remaining = parser.parse_known_args()
SCRIPT = ROOT / "tools/midi_to_melody.py"
SOURCE = ROOT / "examples/queens_road_east/source.mid"
RECIPE = json.loads((SOURCE.parent / "import_recipe.json").read_text(encoding="utf-8"))

def run_cli(*args, cwd=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], cwd=cwd,
                          env=env, text=True, encoding="utf-8", capture_output=True)

def note_events(on, off, pitch=81, channel=0, zero_off=False):
    return [(on, mido.Message("note_on", note=pitch, channel=channel, velocity=90)),
            (off, mido.Message("note_on" if zero_off else "note_off", note=pitch, channel=channel, velocity=0))]

def save_midi(path, tracks, end=960, ppq=480, midi_type=None):
    midi = mido.MidiFile(type=(0 if len(tracks) == 1 else 1) if midi_type is None else midi_type,
                         ticks_per_beat=ppq)
    for events in tracks:
        track = mido.MidiTrack()
        midi.tracks.append(track)
        previous = 0
        for _, (tick, message) in sorted(enumerate(events), key=lambda item: (item[1][0], item[0])):
            track.append(message.copy(time=tick - previous))
            previous = tick
        track.append(mido.MetaMessage("end_of_track", time=end - previous))
    midi.save(path)
    return path

def demo_document(score, variant):
    settings = dict(RECIPE["variants"][variant])
    settings["speed"] = Fraction(settings["speed"])
    return importer.convert_score(score, **settings)

def decoded_preview(data):
    # Mido's independent merged playback timing, not the converter's TempoMap.
    now, active, result = 0.0, {}, []
    for message in mido.MidiFile(file=io.BytesIO(data)):
        now += message.time
        if message.type == "note_on" and message.velocity:
            active[message.note] = round(now * 1000000)
        elif message.type == "note_off" or (message.type == "note_on" and message.velocity == 0):
            result.append([active.pop(message.note), round(now * 1000000), message.note])
    if active:
        raise AssertionError("preview leaves held notes")
    return sorted(result)

class MidiImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.temp = Path(self.directory.name)
    def tearDown(self):
        self.directory.cleanup()
    def score(self, events, end=960, ppq=480):
        return importer.read_score(save_midi(self.temp / "input.mid", [events], end, ppq))

    def test_original_voice_577_and_demo_exact_events(self):
        score = importer.read_score(SOURCE)
        self.assertEqual(score.sha256, RECIPE["source_sha256"])
        voice = score.channels[(2, 0)]
        original = json.loads((SOURCE.parent / "source_voice.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted((n.on, n.off, n.pitch, n.velocity) for n in voice.notes),
                         sorted((n["t"], n["end"], n["n"], n["vel"]) for n in original["notes"]))
        self.assertEqual(len(voice.notes), 577)
        self.assertFalse(voice.errors)
        for variant, count, dropped in (("full", 572, 5), ("first", 132, 0)):
            document, report = demo_document(score, variant)
            expected = json.loads((SOURCE.parent / ("melody_%s_v1_proposed.json" % variant)).read_text(encoding="utf-8"))
            for key in ("format", "schema_version", "title", "fingering_profile", "countdown_us", "duration_us", "notes"):
                self.assertEqual(document[key], expected[key], (variant, key))
            self.assertEqual(len(document["notes"]), count)
            self.assertEqual(len(report["omitted_notes"]), dropped)
            self.assertEqual([n[2] for n in document["notes"] if 30508500 <= n[0] <= 31525450],
                             [77, 74, 74, 72, 74])
            preview, info = preview_bytes(document)
            actual = decoded_preview(preview)
            self.assertEqual(len(actual), count)
            for before, after in zip(document["notes"], actual):
                self.assertEqual(before[2], after[2])
                self.assertLessEqual(max(abs(before[0] - after[0]), abs(before[1] - after[1])), 10)
            self.assertLessEqual(info["max_event_error_us"], 10)

    def test_tempo_map_other_track_crossed_note_clip_and_speed(self):
        tempo = [(0, mido.MetaMessage("set_tempo", tempo=500000)),
                 (480, mido.MetaMessage("set_tempo", tempo=1000000))]
        voice = note_events(240, 720)
        score = importer.read_score(save_midi(self.temp / "tempo.mid", [tempo, voice]))
        document, _ = importer.convert_score(score, track=1, start_tick=240, end_tick=960)
        self.assertEqual(document["notes"], [[0, 750000, 81]])
        self.assertEqual(document["duration_us"], 1250000)
        fast, _ = importer.convert_score(score, track=1, start_tick=240, end_tick=960, speed=Fraction(2))
        self.assertEqual(fast["notes"], [[0, 375000, 81]])
        self.assertEqual(fast["duration_us"], 625000)
        clip, report = importer.convert_score(score, track=1, start_tick=480, end_tick=960)
        self.assertEqual(clip["notes"], [[0, 500000, 81]])
        self.assertEqual(len(report["clipped_notes"]), 1)
        audition = importer.read_score(self._write("audition.mid", importer.audition_bytes(score, 1, 0)))
        self.assertEqual(audition.tempo.at(720), Fraction(1000000))
        self.assertEqual(audition.channels[(1, 0)].notes[0].on, 240)

    def _write(self, name, data):
        path = self.temp / name
        path.write_bytes(data)
        return path

    def test_fractional_tempo_round_once(self):
        score = self.score(note_events(0, 1), end=100, ppq=96)
        score.tempo = importer.TempoMap(96, [(0, 500001), (1, 500003)])
        self.assertEqual(score.tempo.at(2), Fraction(1000004, 96))
        document, _ = importer.convert_score(score, track=0, end_tick=100)
        self.assertEqual(document["notes"][0], [0, round(Fraction(500001, 96)), 81])

    def test_type_zero_channel_selection_and_velocity_zero_off(self):
        score = self.score(note_events(0, 200, channel=0, zero_off=True) + note_events(0, 200, pitch=74, channel=1))
        self.assertEqual(score.midi_type, 0)
        with self.assertRaisesRegex(MelodyError, "channel"):
            importer.convert_score(score, track=0)
        document, _ = importer.convert_score(score, track=0, channel=1)
        self.assertEqual(document["notes"], [[0, 208333, 74]])
        rows = importer.inspect_score(score)["candidates"]
        self.assertEqual([row["channel"] for row in rows], [0, 1])

    def test_octave_choice_is_explicit_and_not_general_chord_highest(self):
        score = self.score(note_events(0, 200, pitch=60) + note_events(0, 200, pitch=72))
        with self.assertRaisesRegex(MelodyError, "同时"):
            importer.convert_score(score, track=0)
        document, report = importer.convert_score(score, track=0, polyphony="octave-highest")
        self.assertEqual(document["notes"][0][2], 72)
        self.assertEqual([entry["pitch"] for entry in report["omitted_notes"]], [60])
        chord = self.score(note_events(0, 200, pitch=72) + note_events(0, 200, pitch=76))
        with self.assertRaisesRegex(MelodyError, "不是纯八度"):
            importer.convert_score(chord, track=0, polyphony="octave-highest")

    def test_legato_requires_explicit_trim(self):
        score = self.score(note_events(0, 400) + note_events(350, 600, pitch=82))
        with self.assertRaisesRegex(MelodyError, "重叠"):
            importer.convert_score(score, track=0)
        document, report = importer.convert_score(score, track=0, overlap="trim")
        self.assertEqual(document["notes"][0], [0, 324583, 81])
        self.assertEqual(len(report["shortened_notes"]), 1)

    def test_no_octave_fold_and_speed_can_fix_release(self):
        score = self.score(note_events(0, 200, pitch=60))
        with self.assertRaisesRegex(MelodyError, "不会折八度"):
            importer.convert_score(score, track=0)
        document, _ = importer.convert_score(score, track=0, transpose=12)
        self.assertEqual(document["notes"][0][2], 72)
        wide = self.score(note_events(0, 100, pitch=60) + note_events(200, 300, pitch=79))
        with self.assertRaisesRegex(MelodyError, "跨度超过18"):
            importer.convert_score(wide, track=0)
        dense = self.score(note_events(0, 20) + note_events(30, 50, pitch=82), end=100, ppq=500)
        with self.assertRaisesRegex(MelodyError, "40ms"):
            importer.convert_score(dense, track=0)
        slowed, _ = importer.convert_score(dense, track=0, speed=Fraction(1, 2))
        self.assertEqual([row[0] for row in slowed["notes"]], [0, 60000])
        self.assertEqual(slowed["notes"][0][1], 20000)

    def test_pairing_errors_in_selected_track_only(self):
        bad = [(0, mido.Message("note_off", note=81))]
        good = note_events(0, 200)
        score = importer.read_score(save_midi(self.temp / "bad.mid", [bad, good]))
        with self.assertRaisesRegex(MelodyError, "配对"):
            importer.convert_score(score, track=0)
        self.assertEqual(len(importer.convert_score(score, track=1)[0]["notes"]), 1)
        for events in ([good[0]], [good[0], (100, good[0][1]), good[1]], note_events(10, 10)):
            broken = self.score(events)
            with self.assertRaisesRegex(MelodyError, "配对"):
                importer.convert_score(broken, track=0)

    def test_bend_pedal_initial_state_and_explicit_ignore(self):
        events = [(0, mido.Message("control_change", control=64, value=127)),
                  (100, mido.Message("pitchwheel", pitch=100))] + note_events(200, 400)
        score = self.score(events)
        with self.assertRaisesRegex(MelodyError, "弯音"):
            importer.convert_score(score, track=0, start_tick=200)
        document, report = importer.convert_score(score, track=0, start_tick=200, ignore_expression=True)
        self.assertEqual(report["ignored_expression"], ["pitch_bend", "sustain_pedal"])
        self.assertEqual(document["notes"][0][2], 81)
        reset = events + [(200, mido.Message("pitchwheel", pitch=0)),
                          (200, mido.Message("control_change", control=64, value=0))]
        clean = self.score(reset)
        importer.convert_score(clean, track=0, start_tick=201)

    def test_unsupported_time_type_tempo_conflicts_and_drums(self):
        path = save_midi(self.temp / "async.mid", [note_events(0, 100)], midi_type=2)
        with self.assertRaisesRegex(MelodyError, "类型2"):
            importer.read_score(path)
        smpte = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 0xe728) + b"MTrk" + struct.pack(">I", 4) + b"\x00\xff\x2f\x00"
        with self.assertRaisesRegex(MelodyError, "SMPTE"):
            importer.read_score(self._write("smpte.mid", smpte))
        with self.assertRaisesRegex(MelodyError, "冲突"):
            importer.TempoMap(480, [(0, 500000), (0, 600000)])
        with self.assertRaisesRegex(MelodyError, "大于0"):
            importer.TempoMap(480, [(0, 0)])
        drums = self.score(note_events(0, 100, channel=9))
        with self.assertRaisesRegex(MelodyError, "GM鼓"):
            importer.convert_score(drums, track=0)

    def test_clip_empty_bad_track_bad_end_and_speed(self):
        score = self.score(note_events(0, 200))
        for settings in ({"track": 99}, {"track": 0, "end_tick": 1000},
                         {"track": 0, "start_tick": -1}, {"track": 0, "speed": 0},
                         {"track": 0, "start_tick": 400}):
            with self.assertRaises(MelodyError):
                importer.convert_score(score, **settings)
        document, report = importer.convert_score(score, track=0, start_tick=100, end_tick=300)
        self.assertEqual(document["notes"][0][0], 0)
        self.assertEqual(len(report["clipped_notes"]), 1)

    def test_contract_limits_and_bad_json(self):
        score = self.score(note_events(0, 200))
        document, _ = importer.convert_score(score, track=0)
        for key, value in (("countdown_us", True), ("duration_us", 0), ("title", "a" * 81)):
            bad = dict(document, **{key: value})
            with self.assertRaises(MelodyError):
                encode_document(bad)
        large = dict(document, metadata={"audit": "a" * 65536})
        with self.assertRaisesRegex(MelodyError, "64KiB"):
            encode_document(large)
        duplicate = self._write("duplicate.json", b'{"format":"x","format":"x"}')
        with self.assertRaisesRegex(MelodyError, "重复"):
            read_document(duplicate)
        invalid = dict(document, notes=[[0, 100000, 81.0]])
        with self.assertRaises(MelodyError):
            encode_document(invalid)
        invalid = dict(document, metadata={"bad": float("nan")})
        with self.assertRaises(MelodyError):
            encode_document(invalid)
        invalid = dict(document, metadata={"deep": [[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]})
        with self.assertRaisesRegex(MelodyError, "16层"):
            encode_document(invalid)

    def test_preview_short_note_reports_quantization(self):
        score = self.score(note_events(0, 200))
        document, _ = importer.convert_score(score, track=0)
        document["notes"] = [[11, 12, 81]]
        data, info = preview_bytes(document)
        self.assertEqual(info["minimum_one_tick_notes"], [0])
        self.assertEqual(info["max_event_error_us"], 28)
        self.assertEqual(decoded_preview(data), [[20, 40, 81]])

    def test_cli_from_other_folder_and_failed_conversion_preserves_outputs(self):
        path = save_midi(self.temp / "input.mid", [note_events(0, 200, pitch=60)])
        output = self.temp / "song.json"
        files = (output, output.with_suffix(".preview.mid"), output.with_suffix(".report.json"))
        for target in files:
            target.write_bytes(b"keep")
        failed = run_cli("convert", path, "--track", 0, "-o", output, "--force", cwd=self.temp)
        self.assertNotEqual(failed.returncode, 0)
        self.assertNotIn("Traceback", failed.stderr)
        self.assertTrue(all(target.read_bytes() == b"keep" for target in files))
        made = run_cli("convert", path, "--track", 0, "--transpose", 12, "-o", output, "--force", cwd=self.temp)
        self.assertEqual(made.returncode, 0, made.stderr)
        document = read_document(output)
        self.assertEqual(document["notes"][0][2], 72)
        report = json.loads(files[2].read_text(encoding="utf-8"))
        self.assertEqual(report["melody_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
        preserved = output.read_bytes()
        existing = run_cli("convert", path, "--track", 0, "--transpose", 12, "-o", output, cwd=self.temp)
        self.assertNotEqual(existing.returncode, 0)
        self.assertEqual(output.read_bytes(), preserved)
        collision = run_cli("convert", path, "--track", 0, "--transpose", 12, "-o", path, "--force")
        self.assertNotEqual(collision.returncode, 0)
        inspected = run_cli("inspect", path, "--json", "--audition-dir", self.temp / "auditions", cwd=self.temp)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertTrue(Path(json.loads(inspected.stdout)["candidates"][0]["audition"]).exists())
        fresh = self.temp / "fresh.mid"
        regenerated = run_cli("preview", output, "-o", fresh, cwd=self.temp)
        self.assertEqual(regenerated.returncode, 0, regenerated.stderr)
        self.assertEqual(fresh.read_bytes(), files[1].read_bytes())

    def test_demo_cli(self):
        output = self.temp / "demo.json"
        result = run_cli("demo", "first", "-o", output, cwd=self.temp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(read_document(output)["notes"]), 132)

    @unittest.skipUnless(OPTIONS.checker and OPTIONS.device, "supply native checker/device paths for firmware integration")
    def test_raw_midi_to_device_parser_upload_and_restart(self):
        score = importer.read_score(SOURCE)
        class Port:
            def __init__(self, image):
                self.process = subprocess.Popen([OPTIONS.device, str(image)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            def write(self, data):
                self.process.stdin.write(data)
            def flush(self):
                self.process.stdin.flush()
            def readline(self, size):
                return self.process.stdout.readline(size)
            def close(self):
                self.process.stdin.close()
                self.process.wait(timeout=10)
                self.process.stdout.close()
                if self.process.returncode:
                    raise AssertionError("native device failed")
        image = self.temp / "flash.img"
        port = Port(image)
        try:
            for variant, expected in (("full", 572), ("first", 132)):
                document, report = demo_document(score, variant)
                paths = importer.emit_conversion(SOURCE, document, report, self.temp / (variant + ".json"))
                check = subprocess.run([OPTIONS.checker, str(paths[0])], capture_output=True, text=True, check=True)
                self.assertTrue(check.stdout.startswith(str(expected) + ","))
                status = upload_melody.fields(upload_melody.upload(port, paths[0].read_bytes()))
                self.assertEqual(status["notes"], str(expected))
        finally:
            port.close()
        port = Port(image)
        try:
            current = upload_melody.fields(upload_melody.request(port, "STATUS"))
            self.assertEqual(current["notes"], "132")
            self.assertEqual(current["crc"], status["crc"])
        finally:
            port.close()

if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *remaining])
