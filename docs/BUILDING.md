# 构建、测试与复现

## 环境

已验证环境：Pico SDK2.1.1、其TinyUSB子模块、xPack Arm GNU GCC14.2.1-1.1、CMake4.4.4、Ninja1.13.2、Python3.12、C++17。源码要求CMake至少3.18，Python工具只使用标准库；其他版本组合需自行验证。

Windows需要可从终端找到 `git`、`python`、`cmake`、`ninja`，以及 `arm-none-eabi-gcc`。工具链不在PATH时可传其根目录。下载来源：

- Pico SDK：[Raspberry Pi官方仓库](https://github.com/raspberrypi/pico-sdk/tree/2.1.1)
- 本次验证的工具链：[xPack14.2.1-1.1](https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/tag/v14.2.1-1.1)
- Pico SDK提供的是开发库，编译器、Git、Python、CMake、Ninja需要分别可用。

## Windows PowerShell

```powershell
git clone https://github.com/Ting-777/Pico_Ocarina.git
cd Pico_Ocarina
git clone --depth 1 --branch 2.1.1 https://github.com/raspberrypi/pico-sdk.git C:\Dev\pico-sdk
git -C C:\Dev\pico-sdk submodule update --init --depth 1 lib/tinyusb

.\scripts\build.ps1 -Variant full -PicoSdkPath C:\Dev\pico-sdk -ToolchainPath C:\Dev\xpack-arm-none-eabi-gcc-14.2.1-1.1
.\scripts\build.ps1 -Variant first -PicoSdkPath C:\Dev\pico-sdk -ToolchainPath C:\Dev\xpack-arm-none-eabi-gcc-14.2.1-1.1
```

示例路径按实际安装位置修改。`ToolchainPath`应是含`bin/arm-none-eabi-gcc`的工具链根目录，不是gcc可执行文件本身。若本机PowerShell策略阻止脚本，可以直接执行下面等价命令，不必修改全局执行策略：

```powershell
cmake -S . -B build/full -G Ninja -DCMAKE_BUILD_TYPE=Release -DPICO_BOARD=pico -DOCARINA_SONG_VARIANT=full -DPICO_SDK_PATH=C:/Dev/pico-sdk -DPICO_TOOLCHAIN_PATH=C:/Dev/xpack-arm-none-eabi-gcc-14.2.1-1.1
cmake --build build/full --parallel
```

本工程直接生成 `build/full/pico_ocarina.uf2`；`first`则为 `build/first/pico_ocarina.uf2`。数据源是 `examples/queens_road_east/source_voice.json`。CMake自动调用生成器，将`generated/song.h`、CSV、试听及原调MIDI放到对应构建目录，不改动版本库中的例子。

## Linux

```bash
export PICO_SDK_PATH=/absolute/path/to/pico-sdk
# 可选；不设置时编译器需已在PATH内
export PICO_TOOLCHAIN_PATH=/absolute/path/to/arm-toolchain
bash scripts/build.sh full
bash scripts/build.sh first
```

首次配置时，SDK2.1.1可能自动下载并构建picotool，必须能够联网访问GitHub；缺少host工具导致的失败不能通过省略UF2转换掩盖。原v1.1发布UF2使用picotool2.3.2-develop转换。1.2-dev本地测试构建使用现有devkitARM GCC15.2，测试UF2的仅转换及逐块核验过程见RUNTIME_CONFIGURATION.md；正常构建仍建议使用SDK的picotool输出。SDK2.1.1的自动获取脚本跟随picotool develop，因此目前未做到所有工具依赖的完整锁定；严格的逐字节可复现构建是后续任务。

## 不连接硬件的测试

```powershell
cmake -S . -B out/native-full -DOCARINA_HOST_TESTS=ON -DOCARINA_SONG_VARIANT=full
cmake --build out/native-full --config Debug
ctest --test-dir out/native-full -C Debug --output-on-failure

cmake -S . -B out/native-first -DOCARINA_HOST_TESTS=ON -DOCARINA_SONG_VARIANT=first
cmake --build out/native-first --config Debug
ctest --test-dir out/native-first -C Debug --output-on-failure
```

`OCARINA_HOST_TESTS=ON`不引入Pico SDK，也不需要ARM工具链。在有Ninja的Linux/macOS上也可以运行 `bash scripts/test.sh`。GCC/Clang可加 `-DOCARINA_SANITIZERS=ON`；在ptrace沙箱中LSan无法工作时仅为该次运行设置 `ASAN_OPTIONS=detect_leaks=0`，正常环境不需要关闭。

CTest包括：

1. `protocol_player`：USB初始化应答、校准数据、截断命令、音符顺序、停止、第一遍低尾句及后续高音变体、十字键/左摇杆独立状态。
2. `midi_source_correspondence`：先直接读取原始MIDI第2号轨，核对全部577个解析事件；再逐音验证原调对照，以及F调演奏版的统一+5半音和相同起音。

测试内的assert在Release host构建中也保持启用，避免“测试被优化掉”的假通过。它们不验证USB电气行为、实际主机协议接受程度、BOOTSEL硬件读取或游戏音高。

## 单独生成与核验示例

```powershell
python tools/generate_song.py --variant full
python tools/verify_midi.py --variant full
python tools/generate_song.py --variant first
python tools/verify_midi.py --variant first
```

默认写入 `out/generated/full` 和 `out/generated/first`。可用 `--output-dir`指定输出目录。生成器的 `--source`只接受本项目解析JSON结构；目前不是通用MIDI导入器。1.2-dev已支持上传合法主旋律JSON换曲；通用MIDI→配置仍需后续实现轨道选择、速度图和音域策略，详见RUNTIME_CONFIGURATION.md。

## CI与预编译文件

GitHub Actions分别跑两种示例的native测试和Pico交叉编译，并上传UF2/MIDI/CSV。CI使用Ubuntu提供的ARM工具链，版本可能与本次本地14.2.1不同；不要要求不同工具链产物SHA相同。

`firmware/`是已构建的v1.1基线，SHA-256保存在同目录。构建路径、工具版本或元数据变化可改变二进制；这不等于歌曲数据改变。需要逐音/逐状态核验时，以源MIDI、生成CSV及回归测试为准。
