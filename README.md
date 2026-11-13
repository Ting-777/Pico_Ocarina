# Pico Ocarina

**English** · [简体中文](README.zh-CN.md) · [日本語](README.ja.md)

Use a **Raspberry Pi Pico (RP2040)** as a wired controller to automatically play ocarina songs in **The Legend of Zelda: Ocarina of Time** on **Nintendo Switch 2**. Songs are stored on the board.

Includes firmware, a Windows song manager and MIDI conversion tools. The built-in song is **Auld Lang Syne**: 56 notes, 42.8 seconds and a separate 3-second count-in.

## Quick start

1. [Download the firmware](firmware/Pico_Ocarina.uf2). Hold BOOTSEL while connecting the Pico to your PC, then copy the UF2 to the RPI-RP2 drive.
2. Connect the Pico to the Switch 2 and open the game's ocarina screen. Tap BOOTSEL to start or stop playback.
3. To change songs, open [Launch.cmd](Launch.cmd), load a JSON song or convert a MIDI, then upload it to the Pico.

See [Getting started](docs/GettingStarted.md) for wiring and upload instructions.

## Controls

| Action | Function |
|---|---|
| Tap BOOTSEL | Start or stop playback |
| Hold BOOTSEL for about 1 second while idle | Send L+R twice, then A, to complete controller recognition |
| Power on with GP21 connected to GND | Enter PC configuration mode for song upload |
| Optional button between GP22 and GND | Same playback controls as BOOTSEL |

## Song manager

- **English, Japanese and Simplified Chinese.** Choose Language in the window; your selection is saved. The first launch follows your system language, with English as the fallback.
- Select a MIDI track/channel, choose the highest or lowest voice, and preview it.
- Drag time handles and an 18-semitone pitch window to choose a passage.
- Export song JSON, preview MIDI and a conversion report, or load an existing JSON directly.
- Upload through a serial port and verify the saved song by reading it back.

On Windows, install Python 3.9 or newer with Tcl/Tk. Open [Launch.cmd](Launch.cmd) or [PicoOcarina.pyw](PicoOcarina.pyw). Components can be installed from the window or with:

```powershell
python -m pip install -r tools/requirements-gui.txt
```

The GUI language does not alter loaded JSON files, song pitches, timing or uploaded bytes. Built-in MIDI preview uses Windows; exported MIDI files can be opened in another player.

## Documentation

- [Getting started](docs/GettingStarted.md): flashing, playback, upload and troubleshooting.
- [MIDI conversion and song format](docs/MIDIConversion.md): voice selection, CLI options and JSON fields.
- [Building](docs/Building.md): firmware and desktop validator builds.
- [Third-party notices](THIRD_PARTY.md). Project code is licensed under [MIT](LICENSE).
