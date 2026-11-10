# 给本地Codex的开发交接

## 当前已具备

- 独立Pico工程，C++17 + Pico SDK + TinyUSB，无GP2040-CE依赖。
- 有线Pro HID初始化、校准回复和按键/摇杆报告的最小实现。
- 内置完整主旋律与第一次唱段两种构建目标，单按钮开始/停止，3秒倒数，非阻塞USB服务。
- 从原MIDI到解析JSON、生成事件、试听/原调对照的可追溯样例。
- 两种版本的host测试、MIDI逐音核验、编译脚本、预编译UF2和CI。

## 当前没有

任意MIDI导入器、运行时配置解析、歌曲持久存储、上传协议、Windows GUI、配置USB接口、真实硬件通过记录。配置化设计在`CONFIGURABLE_DESIGN.md`，不要将设计文档中的JSON误当作已有功能。

## 先执行

```powershell
git clone https://github.com/Ting-777/Pico_Ocarina.git
cd Pico_Ocarina
cmake -S . -B out/native-full -DOCARINA_HOST_TESTS=ON -DOCARINA_SONG_VARIANT=full
cmake --build out/native-full --config Debug
ctest --test-dir out/native-full -C Debug --output-on-failure
```

重复first版本测试，然后按`BUILDING.md`交叉编译。查看`src/player.h`、`src/main.cpp`与`tools/generate_song.py`中的硬编码参数，先提取接口和配置结构，保持示例输出不变。

完整用户图片已转录到`docs/FULL_FINGERING_REFERENCE.md`及`profiles/oot_user_image_reference.json`：包括19个音的26种按法、替代指法和报告编码。请先区分参考中的19音与当前代码实现的10音，不要声称加载JSON功能已经存在。

## 用户已明确的架构与下一项任务

必须分开：**MIDI→主旋律配置文件**在电脑端，**配置文件→实际手柄演奏**在Pico固件内部。第一步可以固定程序或AI辅助，但第二步不是生成C++头文件再重编译，而是固件的运行时功能。

先读`MELODY_FILE_FORMAT.md`和`schemas/melody-v1.schema.json`。仓库已提供完整/短版两个`melody_*_v1_proposed.json`样例，可直接作为开发输入，不必等通用MIDI导入器完成。

下一项优先实现：有界文件解析与语义校验、`LoadedSong`播放器、固件内置19音profile。之后实现配置模式、上传CLI和Flash原子保存，证明同一UF2可接收两个不同配置并断电保留，离开电脑仍可按BOOTSEL播放。已有UF2尚不支持这些文件，不能仅上传样例JSON就宣称功能完成。

再完善第一步的通用MIDI导入/AI辅助与GUI。电脑端生成最终演奏音高、绝对起音/松键时间；固件只按文件执行，不重复移调或再扣释放时间。试听与设备事件必须从同一文件派生。具体顺序见`CONFIGURABLE_DESIGN.md`。

## 已验证与未验证

导入前v1.1两份UF2已完成RP2040编译、结构检查及嵌入歌曲表和CSV逐字节对应；native ASan/UBSan和MIDI逐音核验通过。初始仓库整理增加了可分目录构建的工程结构，其测试结果记录在`VALIDATION.md`。

未在真实Pico/主机/游戏上测试。遇到主机无响应时先区分USB识别、玩家分配、游戏输入与音乐指法，不要直接修改原曲音符来“修好”。

## 可直接交给Codex的提示词

> 阅读AGENTS.md、README和docs/HANDOFF.md。将本工程逐步开发为Windows可配置的陶笛播放器，最终支持不重新编译即可上传歌曲与配置。优先实现固件内部读取主旋律配置文件、校验、19音指法映射和独立播放，再做文件上传及Flash保存；换曲不重新编译。第一步的MIDI转换可以固定程序或AI辅助，后做通用工具/GUI。保留现有示例回归，不自动折八度。先运行full/first的native测试，再按docs/CONFIGURABLE_DESIGN.md分阶段实施。完成每阶段后报告代码与实机各自的验证范围。
