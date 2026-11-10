# 本次验证记录

日期：2026-11-10（香港时间）。范围：初始导入的v1.1独立Pico工程。以下为本地Linux执行结果；GitHub Actions的结果以仓库实际运行状态为准。

| 检查 | 结果 |
|---|---|
| full native：协议/播放器 | 通过，572音 |
| full native：原MIDI→JSON→试听逐音对应 | 通过，原577事件与JSON一致，572个单音起点保持来源 |
| first native：协议/播放器 | 通过，132音，第一遍低尾句 |
| first native：原MIDI→JSON→试听逐音对应 | 通过 |
| 两种工程的Pico/RP2040 Release编译 | 通过，无编译告警 |
| 两个UF2的结构、芯片族与内嵌歌曲表 | 通过，表与生成CSV完全一致 |
| 整理后的工程与先前v1.1预编译UF2 | 两种版本逐字节相同 |
| 生成CSV及两种MIDI与已交付样例 | 逐字节相同 |
| Bash脚本、Python语法、文档本地链接 | 通过 |
| Windows PowerShell脚本执行 | 未在Windows上运行 |
| Pico USB识别、玩家分配、BOOTSEL读取、Switch 2游戏演奏 | 未实机验证 |

原专用固件的native测试也通过ASan/UBSan，执行器处于ptrace环境时仅关闭LSan；仓库CI包含GCC/Clang sanitizer测试选项。不要把native测试通过当作物理协议或游戏指法已经验证。

本地工具：xPack Arm GNU GCC14.2.1-1.1、Pico SDK2.1.1、该SDK的TinyUSB子模块、CMake4.4.4、Ninja1.13.2、Python3.12.14。完整固件text32960 bytes、data0、bss3588；短版text27664 bytes、data0、bss3588。详见`firmware/SHA256SUMS_v1_1.txt`。
