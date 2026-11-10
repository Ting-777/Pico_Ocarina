"""Compare the compiled 19-pitch profile with the original image transcription."""
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
reference = json.loads((root / "profiles/oot_user_image_reference.json").read_text(encoding="utf-8"))
notes = reference["notes"]
document = {
    "format": "pico-ocarina-melody", "schema_version": 1,
    "fingering_profile": "oot-user-image-reference-v1",
    "countdown_us": 0, "duration_us": 1900000,
    "notes": [[i * 100000, i * 100000 + 60000, n["midi_pitch"]] for i, n in enumerate(notes)]
}
with tempfile.TemporaryDirectory() as directory:
    config = Path(directory) / "all-pitches.json"
    config.write_text(json.dumps(document), encoding="utf-8")
    run = subprocess.run([sys.argv[1], str(config), "--events"], text=True, capture_output=True, check=True)
rows = list(csv.reader(io.StringIO(run.stdout)))
assert rows[0] == ["19", "1900000", "0"]
for note, row in zip(notes, rows[1:]):
    variant = note["v1_1_variant_index"] if note["implemented_in_v1_1"] else 0
    state = note["variants"][variant]["control_state"]
    actual = list(map(int, row))
    expected = [state[k] for k in ("right", "shared", "left", "lx", "ly", "rx", "ry")]
    assert actual[2] == note["midi_pitch"] and actual[3:] == expected, (note, row)
assert len(rows) == 20
print("PASS: all 19 compiled fingerings match image JSON, preserving v1.1 variants")
