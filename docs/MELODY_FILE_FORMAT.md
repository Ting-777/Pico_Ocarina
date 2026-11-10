# 主旋律文件v1：电脑与固件之间的契约

1.2-dev源码已实现此接口的板内校验与加载；发布v1.1 UF2不支持。验证边界与上传说明见 [运行时配置](RUNTIME_CONFIGURATION.md)。JSON Schema见 [melody-v1.schema.json](../schemas/melody-v1.schema.json)。

## 字段

| 字段 | 类型/约束 | 板子如何处理 |
|---|---|---|
| format | 固定`pico-ocarina-melody` | 不符则拒绝 |
| schema_version | 整数1 | 未支持版本拒绝 |
| title | 可选UTF-8字符串，最多80个字符 | 显示/审计；固件需限制UTF-8字节缓冲区，不影响演奏 |
| fingering_profile | 固定`oot-user-image-reference-v1`（v1 MVP） | 选择固件内置指法表；不是要读取电脑JSON路径 |
| countdown_us | 整数0–10000000 | 按钮触发后的倒数，文件时间线不包括这段 |
| duration_us | 整数1–3600000000 | 整首总时长，可包含尾部休止 |
| notes | 1–4096个三元组 | 每项`[on_us, off_us, pitch]` |
| metadata | 可选对象 | 来源审计，不作为演奏指令 |

开始/松键时间是整数微秒；音高是整数MIDI71–89（B4–F6）。文件UTF-8字节数不超过65536。设备端要求非负十进制整数字面量，不接受小数、指数、负数或字符串强制转换。metadata对象最多16层嵌套容器；JSON不带BOM。未知顶层字段由v1拒绝，避免AI拼错字段后悄悄失效；`metadata`中允许扩展审计字段。

## 固件必须额外执行的语义校验

Schema只能校验结构和单字段范围，以下跨字段条件必须在板子内部检查，不能只相信电脑端：

1. 每个音`0 <= on_us < off_us <= duration_us`，所有时间和数量在有界整数范围内。
2. 事件严格按起音时间排序；每对相邻音满足`previous.off_us + 40000 <= next.on_us`。v1默认要求至少40ms释放间隔，明确保证单音化；不接受同时发声或重叠。
3. 每个pitch在当前profile中必须存在。补齐19音前，不能仅因位于71–89就把缺失音当成静音继续播放。
4. 文件中的pitch和on/off已完成电脑端的移调、变速、松键处理。固件不重复修改；不允许单音折八度、clamp或丢音。
5. 错误应带字段/音符索引及原因；新文件完整校验和持久化提交成功之前，上一份有效文件保持可用。

若某首曲的节奏快到无法容纳按住加40ms释放时间，第一步需降低速度或明确提示不可演奏，不能由固件静默缩短/跳过音符。

## 实际样例

- [完整示例](../examples/queens_road_east/melody_full_v1_proposed.json)：572音，227.7968秒。
- [第一遍短版](../examples/queens_road_east/melody_first_v1_proposed.json)：132音，48.8136秒。

这些文件从已核验的演奏CSV构造，pitch已统一升5半音到F调；`metadata.transpose_semitones_applied=5`只是记录，不要求板子再加5。第一遍尾句必须为F5 D5 D5 C5 D5。

## 播放语义

用户触发时记下绝对原点`now + countdown_us`。每次主循环根据当前位置读取事件：音内按住对应指法；off后至下一on为中立；到duration结束；任何时刻停止则立即回中并释放按键。继续服务USB，不通过整首阻塞sleep实现。

板子根据profile在内部执行pitch→ControlState→USB输入报告。首次MVP只单次播放，不必提供循环、实时变速或任意USB包执行功能。配置文件不能指定任意Flash地址或未经限制的USB报告字节。

文件、传输协议与Flash容器是三层：JSON是用户可见的歌曲；USB协议负责分块、长度和校验；Flash容器负责有效标志与原子保存。不要把CRC误当作JSON已经合法，也不要把收到最后一包误当作已安全激活。
