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
- `src/configuration.cpp`、USB描述符：上电GP21接地进入仅CDC配置模式，播放模式只枚举原Pro HID；BOOTSEL/GP22原操作保留。
- `tools/upload_melody.py`：Windows/pyserial CLI，设备校验后提交并回读摘要。
- full/first内置演示仍作为无保存歌曲时的明确fallback，也通过同一个JSON解析器加载。构建变体不限制后续上传的歌曲。

## 验证边界

首先运行了原 full/first native 测试，各2/2通过。本机GCC16新增匿名typedef警告，基线阶段临时降为提示；随后给3个结构体加名，恢复严格 -Werror 测试通过。

新增后 full/first 各6/6通过：原协议/MIDI核验、加载与边界、19音参考、288种中断写入模拟、实际上传CLI连接native设备进程、两首歌换曲和进程重启持久化。详情见 `VALIDATION.md`。

**新源码full/first已完成ARM GCC15.2（devkitARM）+ SDK2.1.1交叉编译；两份开发UF2逐块核验通过；没有实机通过记录。** v1.1基线保持原样；开发测试UF2及SHA256另置firmware/dev。构建目录为out/pico-full和out/pico-first，UF2是本地开发测试版，不能把构建通过称为Windows串口或Switch验证。

## 下一项工作

1. 复现已通过的ARM构建：本机现有编译器C:/msys64/opt/devkitpro/devkitARM（GCC15.2.0），SDK在out/deps/pico-sdk-2.1.1，TinyUSB固定86ad6e56c1700e85f1c5678607a762cfe3aa2f47。两份ELF及分区断言通过，主RAM静态132168字节、4KiB核心0栈；尚待板上水位验证。
2. 按 `RUNTIME_CONFIGURATION.md` 用真实Pico验证GP21配置模式、CDC和上传；同一UF2接收full/first、STATUS、断电保留、坏包/中止/断连与真实掉电回退。
3. Switch/游戏验证USB识别、玩家分配、19音确定按法、独立D-pad/摇杆、重复音与停止回中；保留第一遍低尾句和后续高变体。没有设备时明确记录未验证，继续可做的软件工作。
4. 通过这些后再更新发布UF2/校验和；随后实现通用MIDI导入、同一文件派生试听、GUI或AI辅助。不要提前投入大型界面。

## 继续前阅读/执行

阅读AGENTS.md、README、CONFIGURABLE_DESIGN.md、MELODY_FILE_FORMAT.md和RUNTIME_CONFIGURATION.md。运行full/first native：

```powershell
cmake -S . -B out/native-full -DOCARINA_HOST_TESTS=ON -DOCARINA_SONG_VARIANT=full
cmake --build out/native-full --config Debug
ctest --test-dir out/native-full -C Debug --output-on-failure
# 另建 out/native-first，变体改为first
```

本机测试工具在out/deps，未写入全局PATH；MinGW编译器在C:/msys64/mingw64/bin，ARM编译器在C:/msys64/opt/devkitpro/devkitARM/bin。构建输出与依赖均忽略，不要把它们提交成源码或声称已发布。
