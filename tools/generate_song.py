"""Embed the final default-song JSON without changing its pitches or timing."""
import argparse
import csv
from pathlib import Path
from melody_format import read_document

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="Validate and embed the default melody JSON.")
    parser.add_argument("--source", type=Path, default=ROOT / "songs/auld_lang_syne_playback.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "out/generated/default")
    args = parser.parse_args()
    song = read_document(args.source)
    raw = args.source.read_bytes()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    header = '#pragma once\n#include "melody.h"\n'
    header += 'constexpr uint32_t SONG_DURATION_US=%d;\n' % song["duration_us"]
    header += 'constexpr uint32_t SONG_COUNTDOWN_US=%d;\n' % song["countdown_us"]
    header += 'constexpr SongNote SONG[]={\n'
    header += ''.join(' {%d,%d,%d},\n' % tuple(note) for note in song["notes"])
    header += '};\nconstexpr unsigned SONG_COUNT=sizeof(SONG)/sizeof(SONG[0]);\n'
    (output / "song.h").write_text(header, encoding="utf-8")
    (output / "fallback_melody.h").write_text(
        '#pragma once\nconstexpr unsigned char FALLBACK_MELODY[]={' +
        ','.join(str(byte) for byte in raw) + '};\n', encoding="utf-8")
    with (output / "default_song_notes.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["onset_us", "note_off_us", "playback_MIDI_pitch"])
        writer.writerows(song["notes"])
    print("Embedded %d notes; duration %.1f s; countdown %.1f s" %
          (len(song["notes"]), song["duration_us"] / 1000000, song["countdown_us"] / 1000000))


if __name__ == "__main__":
    main()
