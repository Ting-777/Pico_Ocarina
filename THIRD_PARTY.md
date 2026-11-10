# 来源与许可

本仓库新增程序、测试、构建脚本与文档采用根目录的MIT许可。该许可不替第三方作品授予未获授的权利。

| 来源 | 使用部分 | 许可/说明 |
|---|---|---|
| [GP2040-CE v0.7.12](https://github.com/OpenStickCommunity/GP2040-CE/tree/v0.7.12) | Switch Pro描述符、校准数据和USB协议处理的参考/改编 | MIT，见`third_party/LICENSE_GP2040.txt`；源文件保留原版权说明 |
| [Raspberry Pi pico-examples](https://github.com/raspberrypi/pico-examples/tree/master/picoboard/button) | 从RAM采样BOOTSEL/Flash CS的例程 | BSD-3-Clause，见`third_party/LICENSE_PICO_EXAMPLES.txt` |
| [TinyUSB](https://github.com/hathach/tinyusb) | 通过Pico SDK链接的USB栈 | MIT，见`third_party/LICENSE_TINYUSB.txt`；依赖源码未复制进仓库 |
| [Pico SDK 2.1.1](https://github.com/raspberrypi/pico-sdk/tree/2.1.1) | RP2040启动、标准库与硬件支持 | 外部依赖，遵循其仓库各文件许可 |

`examples/queens_road_east/`中的原MIDI由本项目用户提供，用于本次演奏、纠错与回归。相关歌曲及编曲数据不是本项目创作的通用代码；根目录MIT许可不表示将《皇后大道东》词曲、原MIDI或其他音乐权利重新许可。生成的试听、音符CSV和解析JSON同样保留其来源性质。

原游戏陶笛按键参考图由用户在会话中提供，本仓库没有复制该图片或游戏素材。当前程序的指法表只使用10个演奏音；新增参考文档/profile转录了图中的19个音和26套按法（Guide by Tiny Violet，button icons by Zacksly），尚未接入固件。协议兼容设备不是任天堂官方固件或授权产品；此说明仅用于正确识别项目来源。
