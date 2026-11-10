# Local Codex handoff

This repository is a standalone Raspberry Pi Pico/RP2040 USB controller firmware, not a GP2040-CE fork. Read `README.md`, `docs/HANDOFF.md`, and `docs/CONFIGURABLE_DESIGN.md` before substantial changes.

## Current user goal

Develop a configurable ocarina player usable from Windows. Preserve one-button continuous playback, independent left-stick and D-pad modifiers, source MIDI phrasing, and no per-note octave folding. Eventually allow song/config uploads without recompilation. The configurable UI/upload/storage features are planned, not already implemented.

## Keep these invariants

- Support the ordinary non-W Raspberry Pi Pico first.
- First source ending at bar27 is LOW: C5 A4 A4 G4 A4, or F5 D5 D5 C5 D5 after the uniform +5 transposition.
- Bars51/59 and bar91's upper voice are legitimate high variants; do not flatten all verses to one melody.
- Demo source has577 notes /572 onset times; only five lower simultaneous octave doubles are omitted.
- L3 means stick click; it is not a stick direction. Preserve separate D-pad and analog axes.
- Use absolute deadlines rather than sleeping through the song. Continue USB service and stop handling during playback.
- BOOTSEL sampling temporarily releases flash CS from SRAM with IRQs disabled. Do not add flash access inside that critical section or start a second core without addressing flash coordination.
- Never label simulator/software results as Switch 2 hardware validation.

Full image fingerings are documented in `docs/FULL_FINGERING_REFERENCE.md` and `profiles/oot_user_image_reference.json`: 19 pitches, 26 variants. The JSON is reference-only; the current C++ table still implements10 pitches. Preserve that distinction until the profile is actually integrated and validated.

## Build and test

Native software tests require only Python3, CMake, and a host C++17 compiler:

    cmake -S . -B out/native-full -DOCARINA_HOST_TESTS=ON -DOCARINA_SONG_VARIANT=full
    cmake --build out/native-full --config Debug
    ctest --test-dir out/native-full -C Debug --output-on-failure

Repeat with a separate `out/native-first` directory and `OCARINA_SONG_VARIANT=first`. On Linux, `bash scripts/test.sh` runs both. `OCARINA_SANITIZERS=ON` adds ASan/UBSan on GCC/Clang; LSan may need disabling only inside ptraced/container runners.

Firmware: Pico SDK2.1.1 plus TinyUSB submodule, ARM GCC14.2.1 (validated), CMake and Ninja. Use `scripts/build.ps1` on Windows or `scripts/build.sh` on Linux; see `docs/BUILDING.md`.

Generated `song.h`, MIDI and CSV go under the build/output directory. Do not add them under `src/` or mutate tracked examples during builds. Keep `firmware/` binaries and checksums synchronized when intentionally updating a published baseline.

## Scope of the initial import

Build scripts, host tests and documentation accompany v1.1. There is no arbitrary-MIDI importer, runtime config parser, persistent song store, Windows GUI, or configuration USB interface yet. Implement them as incremental changes using the acceptance criteria in `docs/CONFIGURABLE_DESIGN.md`; preserve the demo regressions as integration fixtures.
