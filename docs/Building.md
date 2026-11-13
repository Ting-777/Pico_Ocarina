# Building from source

## Requirements

- Python 3.9 or newer.
- CMake 3.18 or newer and Ninja.
- Arm GNU Toolchain: put `arm-none-eabi-gcc` on PATH, or set `PICO_TOOLCHAIN_PATH` to the toolchain root.
- Pico SDK 2.1.1 with its TinyUSB submodule.

From the project root:

```powershell
git clone --depth 1 --branch 2.1.1 https://github.com/raspberrypi/pico-sdk.git .deps/pico-sdk
git -C .deps/pico-sdk submodule update --init --depth 1 lib/tinyusb
```

## Firmware

Windows:

```powershell
.\scripts\build.ps1 -PicoSdkPath .deps/pico-sdk
```

Linux / macOS:

```bash
export PICO_SDK_PATH="$PWD/.deps/pico-sdk"
bash scripts/build.sh
```

The output is `build/pico/pico_ocarina.uf2`. The project includes an RP2040 UF2 packer.

The built-in song comes from [auld_lang_syne_playback.json](../songs/auld_lang_syne_playback.json). Upload JSON to change songs. To change the built-in fallback, replace that file and rebuild.

## Desktop validator

With a C++17 compiler, CMake and Ninja:

```powershell
cmake -S . -B build/tools -G Ninja -DOCARINA_HOST_TOOLS=ON
cmake --build build/tools
./build/tools/melody_check songs/auld_lang_syne_playback.json
```

`melody_check` prints the note count, duration and count-in. Add `--events` to list notes and mapped controller inputs.

## GUI translations

The UI supports `en`, `ja` and `zh_CN`. Translations are stored in `tools/locales/en.json` and `tools/locales/ja.json`; Simplified Chinese uses the source messages. Keep formatting placeholders such as `%d` and `%s` in the same order.

```powershell
python tools/check_locales.py
```

`PICO_OCARINA_LANG` can select a session language. `PICO_OCARINA_SETTINGS` can select a settings file. Otherwise the app saves the language under the user's application configuration directory.

GitHub Actions builds the firmware and validator for `main`, `prod` and `prod-multi-lang`. Download the UF2 and checksum from the completed build's artifacts.
