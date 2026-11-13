# Getting started

**English** · [简体中文](../开始使用.md) · [日本語](GettingStarted.ja.md)

## Flash the firmware

Use a standard Raspberry Pi Pico (RP2040) and a USB data cable.

1. Hold BOOTSEL while connecting the Pico to your PC.
2. Copy [Pico_Ocarina.uf2](../firmware/Pico_Ocarina.uf2) to the RPI-RP2 drive.
3. The Pico restarts automatically. The file checksum is in [SHA256SUMS.txt](../firmware/SHA256SUMS.txt).

## Play on the Switch

1. Connect the Pico to a Switch USB port and open the game's ocarina screen.
2. To register the wired controller, hold BOOTSEL for about 1 second while idle. The Pico sends L+R for 0.5 seconds, releases for 1 second, repeats L+R, releases for 1 second, then sends A for 0.5 seconds.
3. Tap BOOTSEL to start playback; tap again to stop. Another press also cancels controller registration.

The built-in song is Auld Lang Syne, with a 3-second count-in. LED states: slow blink while waiting for connection, steady when idle, fast blink during count-in, medium blink during playback.

## Open the song manager

Install Python 3.9 or newer with Tcl/Tk, then open [Launch.cmd](../Launch.cmd) or [PicoOcarina.pyw](../PicoOcarina.pyw). Install components from the window or run:

```powershell
python -m pip install -r tools/requirements-gui.txt
```

Choose **English**, **日本語** or **简体中文** in the window's language selector. Switching keeps the loaded song and conversion settings. Your language selection is saved for the next launch.

## Upload a song

1. Unplug the Pico. Connect **GP21 to GND**, then reconnect it to your PC.
2. Click **Load JSON…** to load a song, or **Open MIDI…** to convert a MIDI.
3. Open **Upload to Pico**, refresh/select the serial port, then click **Upload song to Pico**.
4. After the saved song is verified, unplug the Pico and remove the GP21 jumper. Connect it to the Switch to play.

A saved song takes priority over the built-in song. Reflashing preserves saved songs. To restore the default, load [the default song JSON](../songs/auld_lang_syne_playback.json) and upload it again.

Command-line upload and status:

```powershell
python tools/upload_melody.py song.json --port COM5
python tools/upload_melody.py --port COM5 --status
```

## Convert a MIDI

1. Open the MIDI and select its melody track/channel. Preview it to check the voice.
2. For chords, choose **Keep highest notes** or **Keep lowest notes**.
3. Click **Select a passage…**. Drag the blue handles to choose time and the green window to choose pitches. The pitch window spans 18 semitones and can be moved vertically.
4. Click **Use selection**, adjust the title, transpose, speed and count-in, then **Export song**.
5. Preview the result, then upload it.

The pitch window automatically fits the most source notes in the selected time range; notes outside it are excluded. The playable range is MIDI 71–89 (B4–F6). Export uses 120 ms release gaps by default. See [MIDI conversion](MIDIConversion.md) for options and file format.

## Wiring

| Pico pin | Connection |
|---|---|
| GP21 | Connect to GND before power-on for configuration mode |
| GP22 | Optional button to GND |
| GP25 | Built-in LED |
| BOOTSEL | Built-in button |

## Troubleshooting

**The window does not open:** use Python 3.9 or newer with Tcl/Tk and install `tools/requirements-gui.txt`.

**No serial port:** reconnect with GP21 grounded, use a data cable, close other apps using the port, then refresh.

**The old song still plays after flashing:** upload the desired JSON; the saved song has priority.

**MIDI range or polyphony errors:** use the pitch window, voice selection and transposition, then preview. For complex arrangements, extract a monophonic melody MIDI first.
