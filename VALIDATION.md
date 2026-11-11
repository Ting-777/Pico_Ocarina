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

## 2026-11-10：BOOTSEL长按换手柄流程

待机长按约1秒后，改为L+R按住500ms → 全松1000ms → L+R按住500ms → 全松1000ms → A按住500ms → 全松。整个序列使用64位绝对起点非阻塞定位，持续服务USB；再次按下按钮、断连、USB挂起或协议未就绪时取消。BOOTSEL和GP22等效，持续按住只触发一次，长按松开不播放。

本机Windows、Python3.12.0、w64devkit2.11.0（GCC16.2.0）、CMake4.4.4、Ninja1.13.2；Debug严格告警、assert启用、OCARINA_MIDI_TESTS=ON。full/first各8/8通过，输出位于out/bootsel/native-full和native-first。新增controller_join检查微秒边界、两次独立L+R、A的正确按钮位、全程摇杆中立、实际8ms报告顺序、所有步骤取消/重启、跨32位微秒时钟和延迟循环不补发旧步骤；原歌曲/指法/上传/存储/MIDI回归保持通过。这里的取消测试调用序列stop接口，不模拟真实USB挂起或实体按键采样。

首次MIDI测试因系统临时目录的文件替换权限失败；将TEMP/TMP指向工程内独立临时目录后，两套完整测试均通过，没有修改导入器代码。本轮未运行ASan/UBSan，也没有真实Pico或游戏验收。

固件使用SDK2.1.1、Arm GNU14.2.Rel1（GCC14.2.1），full/first Release构建及歌曲分区断言均通过。官方编译器压缩包SHA256与Arm提供值一致；编译器在受限执行环境中出现Windows系统DLL加载错误，在正常Windows环境完成构建。继续使用PICO_NO_PICOTOOL=ON及uf2conv.py的--convert模式，没有刷写设备。

| 变体 | BIN字节 | UF2字节 | Flash末地址 |
|---|---:|---:|---|
| full | 91336 | 182784 | 0x100164C8 |
| first | 66960 | 134144 | 0x10010590 |

两种构建ram_vector_table=192、data=10064、bss=121788，共132044字节，另有2048字节heap和4096字节核心0栈；StackBottom/Top仍为0x20041000/0x20042000。相对此前GCC15.2产物，变化也包含本轮工具链和路径差异，不应将尺寸差异全部归因于按键逻辑。

两份新UF2逐块通过magic、RP2040 family、标志、地址/序号/块数、歌曲分区边界、重组等于BIN、内嵌JSON原文检查。out/bootsel/pico-full的UF2已复制到firmware/dev并更新SHA256SUMS.txt；full SHA256为2639269f465a4842b126d343b0e6429f9df20de604018cab54f9b7072b688e74，first为7d5421159cbd08a1aa7f6b4c58b5004a88216374fd073f30ead2efced750b3e9。两份v1.1基线仍与原校验和一致。待实机确认游戏中的首次识别、再次L+R加入及A确认。

## 2026-11-11：Python转换窗口及小屏布局

Windows、Python3.9、Tk8.6.9、Mido1.3.3；先重跑full/first各8/8，再重新配置构建，加入可选GUI表单测试后各9/9通过。原演示、19音、上传/重启存储及控制器序列回归保持通过。

- `test_midi_gui_model.py`：6项通过。两示例572/132音及标题、时长、倒数与独立样例一致，输出通过C++解析器；数字/拍点精度、非法输入与Windows文件名、无隐式折八度/复音处理、MCI生命周期均覆盖。
- `test_midi_gui_window.py`：5项通过。实际Tk事件循环检查两示例按钮到输出文件、参数变动后结果失效、输入错误/取消覆盖、坏文件清除旧选择、后台任务期间界面响应；完整示例生成后遍历所有已显示控件，1180×680、1080×620、940×580下两个页签均位于父容器内，轨道区保留可见高度。
- 本机1536×864屏幕，默认客户区1180×680，工作区适配已执行。Windows MCI对含中文路径的生成试听文件真实启动，状态返回playing，停止后关闭。没有人工听音确认。
- 窗口截图工具初始化两次均报 `trusted Node process exited unexpectedly`；布局证据来自实际Tk几何与交互测试，没有完成截图目视验收。其他缩放比例、多显示器和不同Windows MIDI设备尚待使用反馈。

默认无依赖native用法不变；GUI核心测试仅在 `OCARINA_MIDI_TESTS=ON` 时加入，真实窗口测试单独运行以适配无桌面的CI。没有修改C++固件、UF2或原有音乐样例，也没有Pico/USB/Flash/Switch新增实机验证。

### CMD入口实测修复（2026-11-11）

用户反馈启动CMD乱码/拆行报错后，将批处理改为ASCII内容、CRLF换行，调用ASCII命名的共享Python启动器；中文PYW入口保留为别名。Git属性明确CMD使用CRLF。

通过系统cmd.exe从 `out/launcher check 中文` 运行根目录启动CMD，实际退出码0、诊断输出0字节；新pythonw进程建立预期标题窗口，窗口句柄非零、Responding=True，未生成启动错误日志。两个PYW入口通过语法检查。没有更改转换或固件代码，未重复此前已通过的音乐/固件回归；未新增实机验证。
