# 给本地 Codex 的开发交接

## 当前状态（2026-11-10）

上游基线 9f117b5，开发分支 `feature/configurable-player`。firmware根目录的v1.1 UF2和校验和保持原样；firmware/dev新增1.2-dev测试UF2及SHA256，供GitHub下载，新源码标为1.2-dev。

必须保持两步解耦：电脑/AI把 MIDI 转为最终音高和绝对 on/off 的 JSON；Pico 固件内部校验、查指法和独立调度。不能把重新生成 C++ 数组编译或 Windows 实时发音符当作换曲方案。

已完成设计阶段1–3的代码和 native 验证：

- `src/melody.*`：无堆分配、有界、两遍 JSON 解析；完整语义校验；拒绝不破坏旧 LoadedSong；metadata 用16层固定状态栈。
- `src/player.h`：只读取 SongView/LoadedSong，64位绝对时间、倒数、休止、单次、停止、中立；不重复移调/扣40ms/折八度。
- `src/fingering.h`：固定19音profile，C6沿用v1.1按法2，其余按法1；与图片参考JSON逐项核对。26套替代按法仍是参考，不等于全部已验证。
- `src/song_store.*`：文件/头CRC、版本/长度、双槽、最后写头提交、冷启动验证和回退。
- `src/pico_song_flash.*`：普通2MiB Pico最后136KiB歌曲分区，配置模式限定写入；单核关中断，擦写间服务USB。
- `src/upload_session.*`：BEGIN/DATA/VALIDATE/COMMIT/STATUS/ABORT，256字节分块、重复块确认、有界行恢复。
- `src/configuration.cpp`、USB描述符：上电GP21接地进入仅CDC配置模式，播放模式只枚举原Pro HID；BOOTSEL/GP22短按播放/停止保留。待机长按1秒已按用户要求改为两次L+R再A，完整时序见ARCHITECTURE.md。
- `tools/upload_melody.py`：Windows/pyserial CLI，设备校验后提交并回读摘要。
- full/first内置演示仍作为无保存歌曲时的明确fallback，也通过同一个JSON解析器加载。构建变体不限制后续上传的歌曲。

## 验证边界

首先运行了原 full/first native 测试，各2/2通过。本机GCC16新增匿名typedef警告，基线阶段临时降为提示；随后给3个结构体加名，恢复严格 -Werror 测试通过。

新增后 full/first 各6/6通过：原协议/MIDI核验、加载与边界、19音参考、288种中断写入模拟、实际上传CLI连接native设备进程、两首歌换曲和进程重启持久化。详情见 `VALIDATION.md`。

**本轮长按更新的full/first已完成Arm GNU14.2.Rel1（GCC14.2.1）+ SDK2.1.1交叉编译；两份开发UF2逐块核验通过；没有实机通过记录。** v1.1基线保持原样；开发测试UF2及SHA256另置firmware/dev。当前构建目录为out/bootsel/pico-full和out/bootsel/pico-first；旧out/pico-full和out/pico-first属于此前GCC15.2构建。UF2是本地开发测试版，不能把构建通过称为Windows串口或Switch验证。

## 下一项工作

1. 复现已通过的ARM构建：本轮本机编译器在out/deps/bin（Arm GNU14.2.Rel1/GCC14.2.1，PICO_TOOLCHAIN_PATH指向out/deps），SDK在out/deps/pico-sdk-2.1.1，TinyUSB沿用固定86ad6e56c1700e85f1c5678607a762cfe3aa2f47。两份ELF及分区断言通过，主RAM静态132044字节、4KiB核心0栈；尚待板上水位验证。
2. 按 `RUNTIME_CONFIGURATION.md` 用真实Pico验证GP21配置模式、CDC和上传；同一UF2接收full/first、STATUS、断电保留、坏包/中止/断连与真实掉电回退。
3. Switch/游戏验证USB识别、玩家分配、19音确定按法、独立D-pad/摇杆、重复音与停止回中；保留第一遍低尾句和后续高变体。没有设备时明确记录未验证，继续可做的软件工作。
4. MIDI导入首版CLI已按用户“试下”实现，见下面记录；之后扩展更多真实MIDI案例、GUI或AI选轨建议。实机通过后再更新正式发布固件。

## 继续前阅读/执行

阅读AGENTS.md、README、CONFIGURABLE_DESIGN.md、MELODY_FILE_FORMAT.md和RUNTIME_CONFIGURATION.md。运行full/first native：

```powershell
cmake -S . -B out/bootsel/native-full -DOCARINA_HOST_TESTS=ON -DOCARINA_SONG_VARIANT=full
cmake --build out/bootsel/native-full --config Debug
ctest --test-dir out/bootsel/native-full -C Debug --output-on-failure
# first使用out/bootsel/native-first，变体改为first
```

本轮本机测试工具在out/deps，未写入全局PATH；native编译器在out/deps/w64devkit/bin（GCC16.2.0），ARM编译器在out/deps/bin。当前工作目录已迁到C:/Users/htkys/Documents/pico_ocarina/pico_ocarina；旧out/native-*和out/pico-*缓存仍包含原机器绝对路径，不能直接复用，本轮另建out/bootsel。测试TEMP/TMP也指向工程内独立目录。构建输出与依赖均忽略，不要把它们提交成源码或声称已发布。


## MIDI转换首版（2026-11-10历史记录）

新增tools/midi_to_melody.py（inspect/convert/demo/preview）、tools/melody_format.py、固定依赖tools/requirements-midi.txt和examples/queens_road_east/import_recipe.json。转换器直接读取原MIDI，不依赖source_voice.json或现成歌曲JSON；后二者仅作为独立测试基准。

试运行 `python tools/midi_to_melody.py demo first --force`，输出out/converted/queens_first.json及同名preview.mid、report.json。full同理。两份notes、duration、countdown与原样例完全一致；原轨577事件和5处八度叠音也逐项核验。

首版范围：PPQ SMF0/1、显式轨道/通道选择、片段、完整tempo map、整体移调和速度；冲突默认拒绝，八度取高和连奏截短须显式选项，弯音/CC64踏板默认拒绝。没有自动主旋律抽取或GUI。所有桌面变换都发生在JSON生成前，Pico继续按文件执行。

16项转换测试通过；开启OCARINA_MIDI_TESTS后的full/first各7/7通过，包括新生成文件进入现有C++解析器与上传协议，并在native设备进程重启后回读。真实USB/Flash/Switch仍未验证；本次未修改C++固件或测试UF2。这一轮转换器改动已完成本地提交，准备推送feature/configurable-player。上传暂因GitHub连接服务无法访问、本机Git未登录而受阻；连接恢复后继续推送。远端CI尚未运行本轮提交。

## BOOTSEL长按更新（2026-11-10）

待机长按1秒：L+R半秒 → 全松1秒 → L+R半秒 → 全松1秒 → A半秒 → 全松。src/controller_join.h提供非阻塞序列；长按松开不会启动歌曲，持续按住只执行一次，序列中再次按按钮、USB断连/挂起/协议未就绪均取消。BOOTSEL与GP22等效。

新增controller_join回归；开启MIDI测试的full/first各8/8通过，保留原歌曲和上传回归。新固件/校验和已同步到firmware/dev，当前SHA与内存见RUNTIME_CONFIGURATION.md、VALIDATION.md。没有刷写真实设备。上文MIDI转换段落的“未修改固件/UF2”及上传受阻状态是前一轮历史记录；2026-11-11用户已要求将此前MIDI提交与本次固件修改一并上传到现有feature/configurable-player分支。
