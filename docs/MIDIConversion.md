# MIDI conversion and song format

## Select the melody

Tracks and channels are numbered from 0. Preview the voices and choose the theme melody. Track selection, highest/lowest voice selection and the pitch window help separate it from bass, inner harmonies and arpeggios.

Highest/lowest selects the currently sounding voice. The pitch window fits the most source notes and can be moved vertically. For complex arrangements, extract the melody by phrase into a monophonic MIDI first. Preserve melody rests, held notes and genuine repeated attacks.

## Command line

```powershell
python tools/midi_to_melody.py inspect song.mid --audition-dir out/auditions
python tools/midi_to_melody.py convert song.mid --track 0 --channel 0 --polyphony highest --transpose 0 -o out/song.json
python tools/midi_to_melody.py preview out/song.json -o out/song.preview.mid
```

Choose the track, channel and transpose for your file. Conversion writes song JSON, preview MIDI and a report.

| Option | Function |
|---|---|
| `--polyphony highest` / `lowest` | Keep the highest or lowest active voice |
| `--pitch-min` / `--pitch-max` | Filter source MIDI pitches, inclusive bounds 0–127; use both options |
| `--start-tick` / `--end-tick` | Select a source tick range |
| `--start-beat` / `--end-beat` | Select a range in quarter-note beats, starting at 0 |
| `--transpose` | Transpose the whole passage in semitones |
| `--speed` | Speed multiplier; default 1, 0.8 means 80% of source speed |
| `--countdown-us` | Separate count-in; default 3000000 microseconds |
| `--release-us` | Release gap; default 120000 microseconds |
| `--ignore-expression` | Ignore pitch bend and sustain |
| `--valid-notes-only` | Use complete note pairs only |
| `--tempo-policy first` / `last` / `fixed-120` | Resolve conflicting tempos or use a fixed 120 BPM |
| `--force` | Replace existing output |

Supports PPQ MIDI types 0 and 1. Run `python tools/midi_to_melody.py convert --help` for all options.

## Pitch and time

The playable range is MIDI 71–89 (B4–F6), spanning 18 semitones. For melody bounds `pmin` and `pmax`, the whole-passage transpose `k` must satisfy:

```text
71 - pmin <= k <= 89 - pmax
```

For wider melodies, select a narrower pitch range, split by phrase, or prepare a separate octave-adapted arrangement. The report records voice selection, trimming and timing changes.

Export starts the first retained note at 0, keeps internal rests and uses a separate count-in. Added rests provide 120 ms release gaps by default. For an extracted monophonic MIDI, `--polyphony highest` preserves selected note lengths and delays subsequent notes.

## JSON format

```json
{
  "format": "pico-ocarina-melody",
  "schema_version": 1,
  "title": "My song",
  "fingering_profile": "oot-user-image-reference-v1",
  "countdown_us": 3000000,
  "duration_us": 1200000,
  "notes": [[0, 500000, 72], [620000, 1120000, 74]]
}
```

| Field | Constraint |
|---|---|
| `format` | `pico-ocarina-melody` |
| `schema_version` | Integer 1 |
| `fingering_profile` | `oot-user-image-reference-v1` |
| `countdown_us` | Integer microseconds, 0–10000000 |
| `duration_us` | Integer microseconds, 1–3600000000; covers all notes |
| `notes` | 1–4096 `[on_us, off_us, pitch]` entries; integer pitches 71–89 |
| `title` | Optional, at most 80 characters |
| `metadata` | Optional object for provenance and conversion settings; at most 16 nested levels |

Each note satisfies `0 <= on_us < off_us <= duration_us`; notes are ordered by onset. The format requires at least 40000 microseconds between notes; conversion defaults to 120000. Files use UTF-8 JSON without a BOM, at most 65536 bytes, with integer literals for time and pitch.

Pitches and times in the JSON are the final playback values. The Pico plays `notes` directly. See [melody-v1.schema.json](../schemas/melody-v1.schema.json).
