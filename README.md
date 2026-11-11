# Pico Ocarina

用普通 **Raspberry Pi Pico（RP2040）** 模拟有线手柄，让游戏里的陶笛自动演奏。歌曲保存在 Pico 上；换歌时连接 Windows 上传，播放时连接 Switch。

**从这里开始：[使用说明：刷入 → 上传歌曲 → 播放](开始使用.md)**

已经编译好的测试固件：[下载 Pico_Ocarina_Configurable_v1_2_dev.uf2](firmware/dev/Pico_Ocarina_Configurable_v1_2_dev.uf2)。首次使用直接刷入，不需要先搭建编译环境。

## 现在可以怎么用

1. **第一次**：按住 BOOTSEL 接电脑，把上述 UF2 拖进 RPI-RP2 磁盘。
2. **试播**：不接跳线，接 Switch，进入陶笛自由演奏界面，短按 BOOTSEL。内置《皇后大道东》完整版。
3. **以后换歌**：断电时连接 GP21–GND，接 Windows 上传 JSON 歌曲文件；上传后断电取下跳线，再接 Switch 播放。详细针脚、COM 号和可复制命令见 [使用说明](开始使用.md)。

切换有线手柄：待机长按 BOOTSEL 约 1 秒，自动按 **L+R → 松开等 1 秒 → L+R → 松开等 1 秒 → A**；每次按住半秒，结束后全部松开。完成后短按播放，执行中再次按可中止。

**转换自己的 MIDI：双击 [启动转换器.cmd](启动转换器.cmd)**，在窗口里选轨、试听、调整并生成 JSON。首次可点“试用短版”→“生成歌曲文件”。需要 Python 3.9 或更新版本；详细步骤见 [MIDI转换步骤](开始使用.md#把-midi-转成歌曲文件)。

**这是开发测试版：软件测试、编译及固件文件检查已通过；真实 Pico、Windows USB 和 Switch 游戏尚未实测。** `firmware/dev/` 是支持上传换歌的新测试版；`firmware/` 根目录的 v1.1 只能播放内置歌曲。

## 开发资料

| 要做什么 | 看哪份 |
|---|---|
| 编译、运行测试 | [构建说明](docs/BUILDING.md) |
| 继续开发 | [开发交接](docs/HANDOFF.md)、[开发阶段设计](docs/CONFIGURABLE_DESIGN.md) |
| 了解歌曲文件格式 | [文件格式](docs/MELODY_FILE_FORMAT.md) |
| 查上传协议、保存结构和内存数据 | [开发参考](docs/RUNTIME_CONFIGURATION.md) |
| 查哪些测试做过、哪些没做 | [验证记录](VALIDATION.md) |
| 核对主旋律和指法 | [旋律来源](docs/MUSIC_AND_PROVENANCE.md)、[指法参考](docs/FULL_FINGERING_REFERENCE.md) |

新增代码采用 MIT 许可；第三方来源及示例歌曲数据说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。
