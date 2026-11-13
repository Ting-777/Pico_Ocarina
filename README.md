# Pico Ocarina

用 **Raspberry Pi Pico（RP2040）** 模拟Switch有线手柄，自动演奏陶笛。歌曲保存在板上，播放时连接Switch即可。

包含固件、Windows歌曲管理器和MIDI转换工具。默认歌曲为《友谊地久天长》，56音、42.8秒，播放前倒数3秒。

## 快速开始

1. [下载固件](firmware/Pico_Ocarina.uf2)，按住BOOTSEL连接电脑，将UF2拖入RPI-RP2磁盘。
2. 将Pico连接Switch，进入陶笛演奏界面，短按BOOTSEL开始；再次短按停止。
3. 换歌时双击 [启动转换器.cmd](启动转换器.cmd)，加载JSON或转换MIDI，再上传到Pico。

详细步骤见 [开始使用](开始使用.md)。

## 按键

| 操作 | 功能 |
|---|---|
| 短按BOOTSEL | 开始或停止播放 |
| 待机长按BOOTSEL约1秒 | 两次L+R，再按A，完成手柄识别流程 |
| 连接GP21与GND后上电 | 进入电脑配置模式，上传歌曲 |
| GP22接按钮至GND | 可选外接播放按钮，与BOOTSEL功能相同 |

## 歌曲管理器

- 打开MIDI，选择轨道和通道，支持取最高音或最低音。
- 拖动时间范围和18半音音域框，定位试听、调整音区。
- 生成JSON、试听MIDI和处理报告，或直接加载已有JSON。
- 选择串口上传歌曲，并读取板上保存状态。

Windows需安装Python 3.9或更新版本，并包含Tcl/Tk。依赖可在窗口中安装，也可运行：

```powershell
python -m pip install -r tools/requirements-gui.txt
```

## 文档

- [开始使用](开始使用.md)：刷入、播放、上传和常见问题。
- [MIDI转换与歌曲格式](docs/MIDI转换.md)：选声部、命令行和JSON字段。
- [构建](docs/构建.md)：从源码生成UF2和桌面校验工具。
- [第三方许可](THIRD_PARTY.md)。项目代码采用 [MIT许可](LICENSE)。
