# Local Codex handoff

This repository is a standalone Raspberry Pi Pico/RP2040 USB controller firmware, not a GP2040-CE fork. Read `README.md`, `docs/HANDOFF.md`, and `docs/CONFIGURABLE_DESIGN.md` before substantial changes.

## Current user goal

The user explicitly requires TWO independent stages: (1) a PC program or AI-assisted process converts MIDI into a melody configuration file; (2) the Pico firmware itself loads/validates that file, maps its pitches to fingerings, schedules and sends controller input. Prioritize implementing stage2 using the proposed example files before investing in a generic importer or GUI. Saved songs must play with the PC disconnected and changing songs must not require rebuilding UF2. Preserve one-button continuous playback, independent stick/D-pad modifiers and source phrasing. Source 1.2-dev implements bounded runtime loading, upload and dual-slot storage; ARM GCC15.2 + SDK2.1.1 builds and development UF2 verification pass; real USB/Flash/Switch validation remains pending. Published v1.1 UF2 files do not implement these features. firmware/dev/ contains the explicitly unverified 1.2-dev test UF2 and its checksum; preserve the v1.1 baseline files. Read docs/RUNTIME_CONFIGURATION.md for the implemented protocol and validation boundaries.

## Keep these invariants

- Support the ordinary non-W Raspberry Pi Pico first.
- First source ending at bar27 is LOW: C5 A4 A4 G4 A4, or F5 D5 D5 C5 D5 after the uniform +5 transposition.
- Bars51/59 and bar91's upper voice are legitimate high variants; do not flatten all verses to one melody.
- Demo source has577 notes /572 onset times; only five lower simultaneous octave doubles are omitted.
- L3 means stick click; it is not a stick direction. Preserve separate D-pad and analog axes.
- Use absolute deadlines rather than sleeping through the song. Continue USB service and stop handling during playback.
- BOOTSEL sampling temporarily releases flash CS from SRAM with IRQs disabled. Do not add flash access inside that critical section or start a second core without addressing flash coordination.
- Never label simulator/software results as Switch 2 hardware validation.

Full image fingerings are documented in `docs/FULL_FINGERING_REFERENCE.md` and `profiles/oot_user_image_reference.json`: 19 pitches, 26 variants. The JSON remains a reference, not a dynamically loaded profile. Source 1.2-dev implements all19 pitches with one fixed variant per pitch (C6 variant1, zero-based; others variant0) and native reference checks. Real hardware validation of19 pitches/26 alternatives remains pending; published v1.1 implements10 pitches.

## Build and test

Native software tests require only Python3, CMake, and a host C++17 compiler:

    cmake -S . -B out/native-full -DOCARINA_HOST_TESTS=ON -DOCARINA_SONG_VARIANT=full
    cmake --build out/native-full --config Debug
    ctest --test-dir out/native-full -C Debug --output-on-failure

Repeat with a separate `out/native-first` directory and `OCARINA_SONG_VARIANT=first`. On Linux, `bash scripts/test.sh` runs both. `OCARINA_SANITIZERS=ON` adds ASan/UBSan on GCC/Clang; LSan may need disabling only inside ptraced/container runners.

Firmware: Pico SDK2.1.1 plus TinyUSB submodule, ARM GCC14.2.1 (validated), CMake and Ninja. Use `scripts/build.ps1` on Windows or `scripts/build.sh` on Linux; see `docs/BUILDING.md`.

Generated `song.h`, MIDI and CSV go under the build/output directory. Do not add them under `src/` or mutate tracked examples during builds. Keep `firmware/` binaries and checksums synchronized when intentionally updating a published baseline.

## Runtime configuration contract

Read `docs/MELODY_FILE_FORMAT.md` and `schemas/melody-v1.schema.json`. Proposed samples are `examples/queens_road_east/melody_full_v1_proposed.json` and `melody_first_v1_proposed.json`. They contain FINAL playback pitches and absolute on/off times in microseconds, not source MIDI or C++ code. The firmware must not transpose or shorten release times again. `metadata` is audit-only. Implement bounded device-side validation, playback from loaded events, full19-note profile, persistent storage and file upload; only then claim runtime configuration support. Source 1.2-dev validates and loads this contract. Published v1.1 UF2 files cannot load it. See docs/HANDOFF.md for the current implementation and next acceptance work.

## Scope of the initial import

Build scripts, host tests and documentation accompany v1.1. The initial v1.1 import had none of these. Source 1.2-dev now has the parser, dual-slot store, configuration-mode USB interface and upload CLI, covered by native tests and successful ARM builds, awaiting real hardware acceptance. tools/midi_to_melody.py now provides a first MIDI importer CLI (Mido1.3.3): inspect/audition, explicit track/channel and clip selection, exact tempo-map conversion, uniform transpose/speed, explicit octave-highest/overlap policies, JSON-derived preview and report. It supports PPQ SMF0/1, not automatic melody extraction or uploaded fingering profiles. A Python/Tkinter Windows GUI now wraps the same converter: launch with 启动转换器.cmd (陶笛转换器.pyw), with two columns and tabbed advanced settings. GUI output remains the same JSON contract; upload uses the existing separate CLI. Enable OCARINA_MIDI_TESTS after installing tools/requirements-midi.txt; the original native suite remains dependency-free by default. Implement them as incremental changes using the acceptance criteria in `docs/CONFIGURABLE_DESIGN.md`; preserve the demo regressions as integration fixtures.
