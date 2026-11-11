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

## 完整指法文档补充

已对照用户图片转录19个音、26套按法，检查MIDI音高71–89连续覆盖、按钮/摇杆编码，并将现有10音的默认方案逐个与实际C++ `fingering()`输出比对。此补充仅增加文档和参考JSON，未修改播放器或UF2，未新增实机通过记录。

## 运行时配置规划补充

新增v1文件契约草案、JSON Schema及两份配置样例。样例逐音取自已核验CSV：完整572音、短版132音；检查文件小于64KiB、起止顺序、至少40ms释放、总时长及音域约束。它们是固件下一阶段的输入样例，当前固件没有配置读取/上传/存储实现，本次未更改UF2或声称新增实机能力。


## 2026-11-10：配置化源码1.2-dev，Windows native

测试环境：Windows、Python3.9.0、CMake4.4.4、Ninja1.13.2、MinGW GCC16.1.0；Debug，C++17，-Wall -Wextra -Werror，assert开启。本次没有运行ASan/UBSan，不沿用历史结果作为新代码的sanitizer证据。

按用户要求先测原基线：full和first各2/2通过。首次严格编译遇GCC16的non-c-typedef-for-linkage警告，基线验证时暂降为警告；随后为3个已有结构体加名（无字段/字节布局变化），恢复严格编译通过。

阶段1：两个JSON样例加载后事件逐项等于原生成表，572/132个音；测试格式/版本/profile/未知及重复字段、长度、UTF-8/转义、非整数、越界、乱序、重叠、40ms释放、metadata深度、截断和2000次确定性字节变异；失败保留旧歌。metadata不执行移调字段。

阶段2：LoadedSong绝对调度，逐个on/off前后微秒边界、倒数、64位时钟、停止/结束回中；19音完整ControlState与参考JSON逐项一致，C6保留原按法。原低尾句与高变体、577→572主旋律、MIDI逐音和独立D-pad/摇杆回归保持通过。

阶段3：288种擦除/写页中断模拟（含部分页与头记录）均恢复到旧歌或完整新歌；损坏头/文件CRC回退，64KiB文件保存成功。实际Python上传函数对同一个native设备程序先上传full再上传first，错误文件保持旧摘要，进程退出重启后Flash镜像回读一致。行接收覆盖超长、非法控制字节、分片、重发、偏移、CRC、VALIDATE/COMMIT状态。

最终测试项（full/first各6/6）：

- store_upload
- windows_cli_protocol
- melody_loading_playback
- full_profile_reference
- protocol_player
- midi_source_correspondence

这证明的是设备逻辑和CLI协议的软件行为；模拟器不模拟USB枚举、Flash电气特性或Switch游戏帧采样。full/first的ARM交叉编译、分区链接与测试UF2核验随后通过；仍未验证真实Windows串口、真实Flash掉电、19音实机或完整游戏演奏。`firmware/`中v1.1发布文件及校验和未修改。

交叉编译：官方291MiB工具链下载超时后，补充扫描找到现有devkitARM GCC15.2.0；使用它和Pico SDK2.1.1、固定TinyUSB完成两种构建。下一项为RUNTIME_CONFIGURATION.md实机清单；阶段4未验收，阶段5/6留待之后。


ARM Release 构建实测结果：

| 变体 | BIN字节 | UF2字节 | Flash末地址 |
|---|---:|---:|---|
| full | 90396 | 181248 | 0x1001611C |
| first | 66020 | 132096 | 0x100101E4 |

两种构建主RAM静态区相同：ram_vector_table=192、data=10144、bss=121832，共132168字节；初始heap段2048字节，核心0栈4096字节，StackBottom=0x20041000、StackTop=0x20042000。Flash末地址均远低于歌曲区0x101DE000。元数据解析已改成16字节显式状态栈，无递归；这些是链接/编译证据，不是运行栈水位或USB实测。

本地PICO_NO_PICOTOOL=ON构建ELF/BIN，再用Microsoft官方uf2conv.py仅转换，family ID来自SDK boot/uf2.h。测试UF2逐块验证所有头字段、地址不跨歌曲区、重组等于BIN及内嵌JSON原文。SHA-256和使用边界见RUNTIME_CONFIGURATION.md。没有自动刷板，没有修改firmware根目录的v1.1发布UF2。上传GitHub时，将full开发测试UF2及独立SHA256复制到firmware/dev，二进制与本地核验版本一致。


## MIDI转换首版（本地）

开始开发前重跑原full/first，各6/6通过。Mido1.3.3安装在工程私有.deps/python（本次解析依赖packaging26.3），Python3.9.0；不更改全局Python包。

16项MIDI测试全部通过：原MIDI人声577事件与独立source_voice基准一致；full/first的572/132个最终事件及duration/countdown与现有JSON完全一致；仅显式省略full中的5个低八度叠音，第一遍低尾句和后续高变体保留。

覆盖其他轨道的速度事件、跨变速点长音、片段截取、整体速度缩放、有理数最终舍入、类型0多通道、velocity=0结束、纯八度和普通和弦区分、显式连奏截短、拒绝折八度、速度不足40ms时拒绝/减速后成功、配对异常、片段开始前的踏板/弯音状态、类型2/SMPTE/冲突速度拒绝、文件覆盖保护、从其他工作目录调用、轨道试听与JSON重生试听。

新生成的两份JSON已进入真实C++ melody_check校验器，再经现有Python上传器传入native设备进程；同一程序先full再first，进程重启后回读132音及CRC一致。没有连接真实设备。两份试听MIDI从最终JSON生成，经Mido独立播放时间解码逐音核对，最大事件时间差10µs；该数值不表示游戏实际输入或发声精度。

CMake增加可选OCARINA_MIDI_TESTS，默认OFF以保留原host测试无第三方依赖的用法；CI配置为安装固定Mido并开启。开启后本机full/first各7/7通过。CI新配置尚未远端运行；本次没有修改C++固件和UF2，也没有替换既有示例JSON/CSV/MIDI。

输出为out/converted/queens_full.json、queens_first.json及对应.preview.mid/.report.json；这些生成物只保留在输出目录。示例导入方案另存为import_recipe.json，锁定源MIDI SHA256和明确的轨道/片段/移调规则。
