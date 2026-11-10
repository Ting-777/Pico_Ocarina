# Pico Ocarina

在普通 **Raspberry Pi Pico（RP2040，非 Pico W / Pico 2）** 上模拟有线 Switch Pro 手柄，自动发送陶笛演奏所需的按键、左摇杆和十字键。

当前基线为 **v1.1 专用播放固件**，内置《皇后大道东》示例。已通过交叉编译、软件测试与逐音 MIDI 核验；**尚未在真实 Pico + Switch 2 + 游戏上验证**，不能将软件测试通过视为实机兼容性已确认。

## 直接使用

无需编译、无需配置 GP2040-CE 宏，也不用依次短接 GPIO。

| 文件 | 内容 |
|---|---|
| [完整版 UF2](firmware/Pico_Ocarina_FullMelody_F_v1_1.uf2) | 原 MIDI 人声主旋律完整播放一次，572个单音起点，约3分48秒 |
| [第一遍短版 UF2](firmware/Pico_Ocarina_FirstVerse_F_v1_1.uf2) | 第一次完整唱段，132个音，约49秒 |
| [完整 F 调试听](examples/queens_road_east/preview_full_F_v1_1.mid) | 对应完整版的实际演奏谱，不含3秒倒数 |
| [原调 C 主旋律对照](examples/queens_road_east/reference_full_original_C_v1_1.mid) | 保留原调及原始音长的单音对照，无伴奏 |

按住 BOOTSEL 插入 Windows 电脑，将所选 UF2 拖进 `RPI-RP2` 磁盘。之后接到 Switch 2 底座，用原手柄进入陶笛自由演奏界面；待 Pico LED 常亮，**短按 BOOTSEL → 倒数3秒 → 播放一遍**，再次按下可停止。

刷入前备份原 GP2040-CE 配置。详细的手柄分配、状态灯及恢复步骤见 [刷写与实机检查](docs/FLASHING_AND_HARDWARE.md)。声音来自游戏，Pico本身不合成音频。

## 旋律准确性

示例来自本项目用户提供的 [原始 MIDI](examples/queens_road_east/source.mid)，使用第2号轨（从0计数）的 `Voice (Sax)`，不是伴奏轨。

- 统一升5个半音至 F 调，使全曲落在图示陶笛的 C5–F6 范围内；**不单独折八度**。
- 第一遍“却汇聚成就”尾句原为 `C5 A4 A4 G4 A4`，播放为 `F5 D5 D5 C5 D5`。
- 原第51/59小节及第91小节高声部本来就是高八度变体，保留为 `F6 D6 D6 C6 D6`。
- 原轨577个音符中有5组同时发声的八度双音。单只陶笛取该小节高声部，省略5个低八度叠音，得到572个单音起点。
- 保留起音时间、各遍差异、重复与中间休止；相邻音间至少留40ms松键，确保同音重触发。

v1.0 曾错误地把第二遍高音唱段作为“第一遍”试听；本仓库只保留已纠正的 v1.1 基线。详见 [音符来源与回归点](docs/MUSIC_AND_PROVENANCE.md)。

## 完整指法参考

用户图片中的 **19个音、26种按法** 已整理到 [完整指法文档](docs/FULL_FINGERING_REFERENCE.md) 和 [机器可读JSON](profiles/oot_user_image_reference.json)，包含所有替代按法及原生Pro报告的按钮位/摇杆坐标。当前固件仍只实现示例用到的10个音；参考JSON尚未接入播放器。

## 本地开发

依赖与 Windows PowerShell 操作见 [构建文档](docs/BUILDING.md)。

```powershell
# 已安装 Git、Python 3、CMake、Ninja、Arm GNU 工具链，并设置 SDK 路径
.\scripts\build.ps1 -Variant full -PicoSdkPath C:\Dev\pico-sdk
.\scripts\build.ps1 -Variant first -PicoSdkPath C:\Dev\pico-sdk
```

两种版本在不同构建目录生成，不会覆盖源码或互相修改歌曲表。输出为 `build/full/pico_ocarina.uf2` 或 `build/first/pico_ocarina.uf2`。

不需要 Pico SDK 或 ARM 编译器的桌面测试：

```powershell
cmake -S . -B out/native -DOCARINA_HOST_TESTS=ON -DOCARINA_SONG_VARIANT=full
cmake --build out/native --config Debug
ctest --test-dir out/native -C Debug --output-on-failure
```

## 给本地 Codex

先读 [AGENTS.md](AGENTS.md) 和 [开发交接](docs/HANDOFF.md)。后续目标是：**在 Windows 上导入 MIDI、选择主旋律轨、调整调高/速度/指法，并将歌曲及配置上传到 Pico，日常换曲不必重新编译固件**。

这部分尚未实现；现有的 `full/first` 是构建时示例选择，不等于已经具备运行时配置。推荐方案和验收条件见 [配置化开发设计](docs/CONFIGURABLE_DESIGN.md)。

## 工程目录

| 路径 | 作用 |
|---|---|
| `src/main.cpp` | Pico USB任务、BOOTSEL/GP22去抖、开始/停止、LED |
| `src/player.h` | 绝对时间调度、MIDI音高到手柄状态的指法映射 |
| `src/pro_controller.*` | 有线Pro手柄初始化与输入报告；不依赖GP2040-CE工程 |
| `tools/` | 示例歌曲表、试听生成与独立MIDI核验 |
| `examples/queens_road_east/` | 原MIDI、解析人声轨、逐音表、试听和原调对照 |
| `profiles/` | 完整用户图片指法参考；尚未由固件加载 |
| `tests/` | 可在桌面运行的协议与演奏回归测试 |
| `firmware/` | 已编译v1.1 UF2与SHA-256 |
| `docs/` | 构建、硬件检查、来源、架构与接手计划 |

新增代码采用 MIT 许可；第三方来源与许可见 [THIRD_PARTY.md](THIRD_PARTY.md)。示例歌曲数据的代码许可范围见该文件说明。
