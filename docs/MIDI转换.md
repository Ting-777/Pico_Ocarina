# MIDI转换与歌曲格式

## 选择旋律

轨道和通道从0编号。先试听各声部，选出连续的主题旋律；低音、和弦内声与分解伴奏可通过选轨、取高/低和音域框筛选。

“取最高/最低音”按当前发声的音选择声部。绿框按源音符数量定位，可手动上下拖动。复杂编配可按乐句提取主旋律并另存为单音MIDI，再用转换器生成JSON。提取时保留旋律休止、长音和真正的同音重复。

## 命令行

```powershell
python tools/midi_to_melody.py inspect song.mid --audition-dir out/auditions
python tools/midi_to_melody.py convert song.mid --track 0 --channel 0 --polyphony highest --transpose 0 -o out/song.json
python tools/midi_to_melody.py preview out/song.json -o out/song.preview.mid
```

按文件实际情况填写轨道、通道和移调。输出包括歌曲JSON、试听MIDI和处理报告。

| 参数 | 功能 |
|---|---|
| `--polyphony highest` / `lowest` | 取最高音或最低音 |
| `--pitch-min` / `--pitch-max` | 原MIDI音高筛选，0–127，含两端，两个参数一起使用 |
| `--start-tick` / `--end-tick` | 选择原曲tick范围 |
| `--start-beat` / `--end-beat` | 按从0计的四分音符拍点选段 |
| `--transpose` | 整体移调，单位半音 |
| `--speed` | 速度倍率，默认1，0.8表示原速的80% |
| `--countdown-us` | 独立倒数，默认3000000微秒 |
| `--release-us` | 音间释放，默认120000微秒 |
| `--ignore-expression` | 忽略弯音和踏板效果 |
| `--valid-notes-only` | 只使用完整配对的音符 |
| `--tempo-policy first` / `last` / `fixed-120` | 处理冲突速度，或按固定120 BPM读取 |
| `--force` | 覆盖已有输出 |

支持PPQ时间制的MIDI类型0/1。查看完整参数可运行 `python tools/midi_to_melody.py convert --help`。

## 音域与时间

可演奏音域为MIDI71–89（B4–F6），跨度18半音。旋律最低音为`pmin`、最高音为`pmax`时，整体移调量`k`满足：

```text
71 - pmin <= k <= 89 - pmax
```

跨度超过18半音时，可缩小音区、分段，或另存经过八度适配的编曲。处理报告记录选音、裁切和时间调整，便于对照试听。

导出以第一个保留音为0，保留内部休止；倒数独立计算。默认增加休止，使相邻音之间留出120毫秒释放。使用自行提取的单音MIDI时，`--polyphony highest`保留所选音长并顺延后续音。

## JSON格式

```json
{
  "format": "pico-ocarina-melody",
  "schema_version": 1,
  "title": "我的歌曲",
  "fingering_profile": "oot-user-image-reference-v1",
  "countdown_us": 3000000,
  "duration_us": 1200000,
  "notes": [[0, 500000, 72], [620000, 1120000, 74]]
}
```

| 字段 | 约束 |
|---|---|
| `format` | 固定为`pico-ocarina-melody` |
| `schema_version` | 整数1 |
| `fingering_profile` | 固定为`oot-user-image-reference-v1` |
| `countdown_us` | 0–10000000的整数微秒 |
| `duration_us` | 1–3600000000的整数微秒，覆盖所有音符 |
| `notes` | 1–4096个`[on_us, off_us, pitch]`，音高为整数71–89 |
| `title` | 可选，最多80个字符 |
| `metadata` | 可选对象，记录来源和转换参数，最多16层嵌套 |

每个音满足`0 <= on_us < off_us <= duration_us`，按起音排序。格式要求相邻音至少40000微秒间隔，转换器默认使用120000。文件为无BOM的UTF-8 JSON，最多65536字节，时间和音高使用整数字面量。

JSON中的音高和时间是最终演奏值，Pico直接播放`notes`。结构定义见 [melody-v1.schema.json](../schemas/melody-v1.schema.json)。
