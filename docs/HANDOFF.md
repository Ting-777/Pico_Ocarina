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

## 下一项建议任务

实现电脑端可配置的MIDI→标准演奏时间线工具。输入轨道、片段、调高、tempo比例、复音策略与指法profile；输出审计CSV、试听MIDI和设备中间格式。复用原文件第27小节低尾句与第51/59小节高变体做集成回归。此阶段不要重写USB描述符，也不要自动折八度。

完成后再实现设备歌曲加载与Windows上传，最终达到不重编译即可换曲。进入配置模式的手势、上传协议和Flash布局还没有被用户确认或实测，不应假设已经定案。

## 已验证与未验证

导入前v1.1两份UF2已完成RP2040编译、结构检查及嵌入歌曲表和CSV逐字节对应；native ASan/UBSan和MIDI逐音核验通过。初始仓库整理增加了可分目录构建的工程结构，其测试结果记录在`VALIDATION.md`。

未在真实Pico/主机/游戏上测试。遇到主机无响应时先区分USB识别、玩家分配、游戏输入与音乐指法，不要直接修改原曲音符来“修好”。

## 可直接交给Codex的提示词

> 阅读AGENTS.md、README和docs/HANDOFF.md。将本工程逐步开发为Windows可配置的陶笛播放器，最终支持不重新编译即可上传歌曲与配置。先实现电脑端通用MIDI导入、指法profile及统一时间线；保留现有示例的全部回归点，不自动折八度。先运行full/first的native测试，再按docs/CONFIGURABLE_DESIGN.md分阶段实施。完成每阶段后报告代码与实机各自的验证范围。
