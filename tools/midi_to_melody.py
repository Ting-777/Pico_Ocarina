"""Inspect MIDI tracks and convert one selected melody to the Pico melody-v1 JSON."""
import argparse
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile

from melody_format import MelodyError, PROFILE, RELEASE_US, encode_document, preview_bytes, read_document

ROOT = Path(__file__).resolve().parents[1]
MAX_MIDI_BYTES = 16 * 1024 * 1024
MAX_MIDI_EVENTS = 500000

def require_mido():
    try:
        import mido
        return mido
    except ImportError as error:
        raise MelodyError("请先运行 python -m pip install -r tools/requirements-midi.txt") from error

@dataclass(frozen=True)
class Note:
    on: int
    off: int
    pitch: int
    velocity: int
    source_index: int

@dataclass
class Channel:
    notes: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    messages: list = field(default_factory=list)
    programs: set = field(default_factory=set)

class TempoMap:
    def __init__(self, ppq, changes):
        self.ppq = ppq
        points = {0: 500000}
        seen = {}
        for tick, tempo in changes:
            if tempo <= 0:
                raise MelodyError("MIDI速度必须大于0")
            if tick in seen and seen[tick] != tempo:
                raise MelodyError("tick %d 有冲突的速度事件，不能猜测应使用哪一个" % tick)
            seen[tick] = tempo
            points[tick] = tempo
        self.ticks = sorted(points)
        self.tempos = [points[tick] for tick in self.ticks]
        self.numerators = [0]
        for index in range(1, len(self.ticks)):
            self.numerators.append(self.numerators[-1] +
                (self.ticks[index] - self.ticks[index - 1]) * self.tempos[index - 1])

    def at(self, tick):
        index = bisect_right(self.ticks, tick) - 1
        return Fraction(self.numerators[index] + (tick - self.ticks[index]) * self.tempos[index], self.ppq)

@dataclass
class Score:
    source: Path
    sha256: str
    midi_type: int
    ppq: int
    track_names: list
    track_ends: list
    channels: dict
    tempo: TempoMap

def read_score(source):
    mido = require_mido()
    source = Path(source)
    with source.open("rb") as file:
        raw = file.read(MAX_MIDI_BYTES + 1)
    if len(raw) > MAX_MIDI_BYTES:
        raise MelodyError("MIDI超过16MiB，请先拆分")
    try:
        midi = mido.MidiFile(file=io.BytesIO(raw), clip=False)
    except (EOFError, ValueError, KeyError, OSError) as error:
        raise MelodyError("无法解析MIDI: %s" % error) from error
    if midi.type not in (0, 1):
        raise MelodyError("第一版仅支持MIDI类型0/1；类型2的各轨互相独立，请先另存为类型0/1")
    if midi.ticks_per_beat <= 0:
        raise MelodyError("第一版不支持SMPTE时间制，请另存为PPQ时间制")
    channels, names, ends, changes = {}, [], [], []
    event_count = 0
    for track_index, track in enumerate(midi.tracks):
        names.append(track.name)
        active = {}
        tick = 0
        for order, message in enumerate(track):
            event_count += 1
            if event_count > MAX_MIDI_EVENTS:
                raise MelodyError("MIDI事件超过500000，请先拆分")
            tick += message.time
            if message.type == "set_tempo":
                changes.append((tick, message.tempo))
            if not hasattr(message, "channel"):
                continue
            key = (track_index, message.channel)
            channel = channels.setdefault(key, Channel())
            channel.messages.append((tick, message))
            if message.type == "program_change":
                channel.programs.add(message.program)
            if message.type not in ("note_on", "note_off"):
                continue
            pitch_key = (message.channel, message.note)
            if message.type == "note_on" and message.velocity:
                if pitch_key in active:
                    channel.errors.append("tick %d: 音高%d尚未结束就再次起音" % (tick, message.note))
                else:
                    active[pitch_key] = (tick, message.velocity, order)
            else:
                start = active.pop(pitch_key, None)
                if start is None:
                    channel.errors.append("tick %d: 音高%d没有对应起音" % (tick, message.note))
                elif start[0] >= tick:
                    channel.errors.append("tick %d: 音高%d时长不为正" % (tick, message.note))
                else:
                    channel.notes.append(Note(start[0], tick, message.note, start[1], start[2]))
        for (channel_index, pitch), start in active.items():
            channels[(track_index, channel_index)].errors.append("tick %d: 音高%d缺少结束事件" % (start[0], pitch))
        ends.append(tick)
    for channel in channels.values():
        channel.notes.sort(key=lambda note: (note.on, note.source_index))
    return Score(source, hashlib.sha256(raw).hexdigest(), midi.type, midi.ticks_per_beat,
                 names, ends, channels, TempoMap(midi.ticks_per_beat, changes))

def note_name(pitch):
    return ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")[pitch % 12] + str(pitch // 12 - 1)

def shift_options(notes):
    if not notes:
        return []
    return list(range(71 - min(note.pitch for note in notes), 90 - max(note.pitch for note in notes)))

def inspect_score(score):
    rows = []
    for (track, channel_index), channel in sorted(score.channels.items()):
        if not channel.notes and not channel.errors:
            continue
        groups = defaultdict(list)
        maximum_off, overlaps = -1, 0
        for note in channel.notes:
            groups[note.on].append(note)
            overlaps += note.on < maximum_off
            maximum_off = max(maximum_off, note.off)
        pitches = [note.pitch for note in channel.notes]
        rows.append({
            "track": track, "channel": channel_index, "name": score.track_names[track],
            "programs": sorted(channel.programs), "notes": len(pitches),
            "range": [min(pitches), max(pitches)] if pitches else [],
            "simultaneous_groups": sum(len(group) > 1 for group in groups.values()),
            "overlapping_onsets": overlaps, "errors": channel.errors,
            "transpose_options": shift_options(channel.notes), "drum_channel": channel_index == 9,
            "pitch_bend_events": sum(message.type == "pitchwheel" and message.pitch != 0 for _, message in channel.messages),
            "sustain_events": sum(message.type == "control_change" and message.control == 64 and message.value >= 64
                                  for _, message in channel.messages),
        })
    return {"type": score.midi_type, "ppq": score.ppq, "tracks": len(score.track_names),
            "tempo_points": len(score.tempo.ticks), "source_sha256": score.sha256, "candidates": rows}

def audition_bytes(score, track, channel_index):
    """Unmodified channel audition, with the global tempo map from every track."""
    mido = require_mido()
    channel = score.channels[(track, channel_index)]
    if channel.errors:
        raise MelodyError("不能导出有配对错误的轨道试听")
    midi = mido.MidiFile(type=1, ticks_per_beat=score.ppq, charset="utf-8")
    conductor, voice = mido.MidiTrack(), mido.MidiTrack()
    midi.tracks.extend([conductor, voice])
    previous = 0
    for tick, tempo in zip(score.tempo.ticks, score.tempo.tempos):
        if tick > score.track_ends[track]:
            break
        conductor.append(mido.MetaMessage("set_tempo", tempo=tempo, time=tick - previous))
        previous = tick
    conductor.append(mido.MetaMessage("end_of_track", time=max(0, score.track_ends[track] - previous)))
    voice.append(mido.MetaMessage("track_name", name=score.track_names[track]))
    previous = 0
    for tick, message in channel.messages:
        voice.append(message.copy(time=tick - previous))
        previous = tick
    voice.append(mido.MetaMessage("end_of_track", time=score.track_ends[track] - previous))
    output = io.BytesIO()
    midi.save(file=output)
    return output.getvalue()

def _expression(channel, start, end):
    bend, pedal, found = 0, 0, set()
    initial_bend = initial_pedal = 0
    for tick, message in channel.messages:
        if tick >= end:
            break
        if message.type == "pitchwheel":
            bend = message.pitch
            if tick >= start and bend:
                found.add("pitch_bend")
        elif message.type == "control_change" and message.control == 64:
            pedal = message.value
            if tick >= start and pedal >= 64:
                found.add("sustain_pedal")
        if tick <= start:
            # Initial state matters even when the event precedes the selection.
            initial_bend, initial_pedal = bend, pedal
    if initial_bend:
        found.add("pitch_bend")
    if initial_pedal >= 64:
        found.add("sustain_pedal")
    return sorted(found)

def convert_score(score, *, track, channel=None, start_tick=0, end_tick=None, transpose=0,
                  speed=Fraction(1), polyphony="error", overlap="error", ignore_expression=False,
                  title=None, countdown_us=3000000):
    if type(track) is not int or not 0 <= track < len(score.track_names):
        raise MelodyError("轨道不存在，请先inspect；轨道编号从0开始")
    candidates = [index for candidate_track, index in score.channels
                  if candidate_track == track and (score.channels[(track, index)].notes or score.channels[(track, index)].errors)]
    if channel is None:
        if len(candidates) != 1:
            raise MelodyError("此轨有%d个通道，请用--channel明确选择（从0开始）" % len(candidates))
        channel = candidates[0]
    if type(channel) is not int or not 0 <= channel <= 15:
        raise MelodyError("通道编号必须是0–15的整数")
    if (track, channel) not in score.channels:
        raise MelodyError("所选轨道/通道不存在")
    if channel == 9:
        raise MelodyError("第一版不将GM鼓通道9转换为陶笛旋律")
    selected = score.channels[(track, channel)]
    if selected.errors:
        raise MelodyError("音符配对错误: " + "; ".join(selected.errors[:3]))
    if end_tick is None:
        end_tick = score.track_ends[track]
    if type(start_tick) is not int or type(end_tick) is not int or not 0 <= start_tick < end_tick:
        raise MelodyError("片段要求 0 <= start < end，单位为tick")
    if end_tick > score.track_ends[track]:
        raise MelodyError("片段结束超过所选轨道结尾")
    speed = Fraction(str(speed)) if not isinstance(speed, Fraction) else speed
    if speed <= 0:
        raise MelodyError("速度倍率必须大于0")
    if polyphony not in ("error", "octave-highest") or overlap not in ("error", "trim"):
        raise MelodyError("不支持的复音或重叠处理规则")
    expression = _expression(selected, start_tick, end_tick)
    if expression and not ignore_expression:
        raise MelodyError("片段使用弯音或延音踏板，当前陶笛不支持；确认舍弃这些效果后使用--ignore-expression")
    groups, clipped = defaultdict(list), []
    for note in selected.notes:
        if note.off <= start_tick or note.on >= end_tick:
            continue
        on, off = max(note.on, start_tick), min(note.off, end_tick)
        if (on, off) != (note.on, note.off):
            clipped.append({"source_index": note.source_index, "original": [note.on, note.off],
                            "selected": [on, off], "pitch": note.pitch})
        groups[on].append(Note(on, off, note.pitch, note.velocity, note.source_index))
    if not groups:
        raise MelodyError("所选片段没有音符")
    notes, omitted = [], []
    for onset, group in sorted(groups.items()):
        if len(group) > 1:
            if polyphony == "error":
                raise MelodyError("tick %d 同时有多个音%s；请先选主旋律或明确处理规则" % (onset, [note.pitch for note in group]))
            if len({note.pitch % 12 for note in group}) != 1:
                raise MelodyError("tick %d 不是纯八度叠音，octave-highest不能处理这个和弦" % onset)
            chosen = max(group, key=lambda note: note.pitch)
            for note in group:
                if note is not chosen:
                    omitted.append({"source_index": note.source_index, "tick": onset, "pitch": note.pitch,
                                    "kept_pitch": chosen.pitch, "reason": "explicit_octave_highest"})
        else:
            chosen = group[0]
        notes.append(chosen)
    for previous, following in zip(notes, notes[1:]):
        if previous.off > following.on and overlap == "error":
            raise MelodyError("tick %d 与前音重叠；确认是连奏后可用--overlap trim，否则先分离声部" % following.on)
    options = shift_options(notes)
    if type(transpose) is not int or transpose not in options:
        suggestion = "%d..%d" % (options[0], options[-1]) if options else "无：所选旋律跨度超过18半音"
        raise MelodyError("移调后超出B4–F6；可用的整段移调范围为 " + suggestion + "。不会折八度或丢音")
    origin = score.tempo.at(start_tick)
    def time(tick):
        return round((score.tempo.at(tick) - origin) / speed)
    duration = time(end_tick)
    rows, shortened = [], []
    for index, note in enumerate(notes):
        on, original_off = time(note.on), time(note.off)
        next_on = time(notes[index + 1].on) if index + 1 < len(notes) else duration
        off = min(original_off, next_on - RELEASE_US)
        if off <= on:
            raise MelodyError("第%d音（源tick %d）容不下正音长和40ms松键；请降低速度或调整片段边界" % (index, note.on))
        rows.append([on, off, note.pitch + transpose])
        if off != original_off:
            shortened.append({"note_index": index, "source_index": note.source_index,
                              "original_off_us": original_off, "playback_off_us": off,
                              "shortened_us": original_off - off})
    title = score.source.stem[:80] if title is None else title
    document = {
        "format": "pico-ocarina-melody", "schema_version": 1, "title": title,
        "fingering_profile": PROFILE, "countdown_us": countdown_us, "duration_us": duration,
        "notes": rows,
        "metadata": {
            "source_sha256": score.sha256, "source_track": track, "source_channel": channel,
            "source_start_tick": start_tick, "source_end_tick": end_tick,
            "transpose_semitones_applied": transpose, "speed_applied": str(speed),
            "polyphony_policy": polyphony, "overlap_policy": overlap,
            "ignored_expression": expression if ignore_expression else [],
        },
    }
    encode_document(document)
    report = {
        "source_sha256": score.sha256, "track": track, "channel": channel,
        "track_name": score.track_names[track], "source_notes_in_selection": sum(map(len, groups.values())),
        "output_notes": len(rows), "duration_us": duration, "countdown_us": countdown_us,
        "uniform_transpose_options": options, "settings": document["metadata"],
        "omitted_notes": omitted, "clipped_notes": clipped, "shortened_notes": shortened,
        "ignored_expression": expression if ignore_expression else [],
    }
    return document, report

def write_bundle(payloads, source=None, force=False):
    targets = [Path(file).resolve() for file, _ in payloads]
    if len(set(targets)) != len(targets) or (source is not None and Path(source).resolve() in targets):
        raise MelodyError("输出文件不可重名，也不能覆盖源文件")
    if not force and any(target.exists() for target in targets):
        raise MelodyError("输出文件已存在；换一个输出名，或用--force明确覆盖")
    staged = []
    try:
        for target, (_, data) in zip(targets, payloads):
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as file:
                staged.append((Path(file.name), target))
                file.write(data)
        for temporary, target in staged:
            os.replace(temporary, target)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)

def emit_conversion(source, document, report, output, force=False):
    output = Path(output)
    data = encode_document(document)
    preview, preview_info = preview_bytes(document)
    preview_path, report_path = output.with_suffix(".preview.mid"), output.with_suffix(".report.json")
    report = dict(report, melody_sha256=hashlib.sha256(data).hexdigest(), melody_bytes=len(data),
                  preview_sha256=hashlib.sha256(preview).hexdigest(), preview=preview_info)
    report_bytes = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    write_bundle([(output, data), (preview_path, preview), (report_path, report_bytes)], source, force)
    return output, preview_path, report_path

def _tick(args, score, prefix):
    tick = getattr(args, prefix + "_tick")
    beat = getattr(args, prefix + "_beat")
    if tick is not None:
        return tick
    if beat is None:
        return 0 if prefix == "start" else None
    value = beat * score.ppq
    if value.denominator != 1:
        raise MelodyError("拍点不在MIDI tick网格上；beat按从0开始的四分音符计数")
    return int(value)

def positive_fraction(value):
    try:
        number = Fraction(value)
        if number <= 0:
            raise ValueError()
        return number
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError("请输入大于0的数，例如1、0.8或3/2")

def beat_fraction(value):
    try:
        result = Fraction(value)
        if result < 0:
            raise ValueError()
        return result
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError("拍点必须是非负数字")

def main(argv=None):
    parser = argparse.ArgumentParser(description="MIDI选轨、检查和转换为Pico歌曲JSON；轨道/通道均从0开始")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="列出轨道/通道，并可导出原轨试听")
    inspect.add_argument("input", type=Path)
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--audition-dir", type=Path)
    inspect.add_argument("--force", action="store_true")
    convert = commands.add_parser("convert", help="明确选择旋律后转换")
    convert.add_argument("input", type=Path)
    convert.add_argument("--track", type=int, required=True)
    convert.add_argument("--channel", type=int, choices=range(16))
    for prefix in ("start", "end"):
        group = convert.add_mutually_exclusive_group()
        group.add_argument("--" + prefix + "-tick", type=int)
        group.add_argument("--" + prefix + "-beat", type=beat_fraction)
    convert.add_argument("--transpose", type=int, default=0)
    convert.add_argument("--speed", type=positive_fraction, default=Fraction(1))
    convert.add_argument("--polyphony", choices=("error", "octave-highest"), default="error")
    convert.add_argument("--overlap", choices=("error", "trim"), default="error")
    convert.add_argument("--ignore-expression", action="store_true")
    convert.add_argument("--title")
    convert.add_argument("--countdown-us", type=int, default=3000000)
    convert.add_argument("-o", "--output", type=Path, required=True)
    convert.add_argument("--force", action="store_true")
    demo = commands.add_parser("demo", help="按已核验的示例方案直接转换原始MIDI")
    demo.add_argument("variant", choices=("full", "first"))
    demo.add_argument("-o", "--output", type=Path)
    demo.add_argument("--force", action="store_true")
    preview = commands.add_parser("preview", help="只从最终JSON重新生成试听MIDI")
    preview.add_argument("input", type=Path)
    preview.add_argument("-o", "--output", type=Path, required=True)
    preview.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "preview":
            data, info = preview_bytes(read_document(args.input))
            write_bundle([(args.output, data)], args.input, args.force)
            print("试听已生成: %s；最大时间量化误差 %d 微秒" % (args.output, info["max_event_error_us"]))
            return 0
        if args.command == "demo":
            folder = ROOT / "examples/queens_road_east"
            recipe = json.loads((folder / "import_recipe.json").read_text(encoding="utf-8"))
            source = folder / "source.mid"
            score = read_score(source)
            if score.sha256 != recipe["source_sha256"]:
                raise MelodyError("示例源MIDI摘要不符，请先检查原文件")
            settings = dict(recipe["variants"][args.variant])
            settings["speed"] = Fraction(settings["speed"])
            document, report = convert_score(score, **settings)
            output = args.output or ROOT / "out/converted" / ("queens_" + args.variant + ".json")
        else:
            source = args.input
            score = read_score(source)
            if args.command == "inspect":
                result = inspect_score(score)
                if args.audition_dir:
                    payloads = []
                    for row in result["candidates"]:
                        if row["errors"]:
                            row["audition_skipped"] = "音符配对错误"
                            continue
                        target = args.audition_dir / ("track_%d_channel_%d.mid" % (row["track"], row["channel"]))
                        payloads.append((target, audition_bytes(score, row["track"], row["channel"])))
                        row["audition"] = str(target)
                    write_bundle(payloads, source, args.force)
                if args.json:
                    print(json.dumps(result, ensure_ascii=True))
                else:
                    print("MIDI类型%d，PPQ=%d，%d条轨，%d个速度点；轨道/通道从0开始" %
                          (result["type"], result["ppq"], result["tracks"], result["tempo_points"]))
                    print("轨道 通道 音数 音域 同起音组 重叠起音 配对错误 名称")
                    for row in result["candidates"]:
                        pitches = row["range"]
                        span = note_name(pitches[0]) + ".." + note_name(pitches[1]) if pitches else "-"
                        print("%4d %4d %4d %-10s %8d %8d %8d %s%s" %
                              (row["track"], row["channel"], row["notes"], span, row["simultaneous_groups"],
                               row["overlapping_onsets"], len(row["errors"]),
                               json.dumps(row["name"], ensure_ascii=False), " [GM鼓]" if row["drum_channel"] else ""))
                    if args.audition_dir:
                        print("原轨试听目录: " + str(args.audition_dir))
                return 0
            document, report = convert_score(score, track=args.track, channel=args.channel,
                start_tick=_tick(args, score, "start"), end_tick=_tick(args, score, "end"),
                transpose=args.transpose, speed=args.speed, polyphony=args.polyphony, overlap=args.overlap,
                ignore_expression=args.ignore_expression, title=args.title, countdown_us=args.countdown_us)
            output = args.output
        paths = emit_conversion(source, document, report, output, args.force)
        print("转换完成：%d音，%.4f秒；整体移调%+d半音；省略%d个明确选择的八度叠音" %
              (len(document["notes"]), document["duration_us"] / 1000000,
               document["metadata"]["transpose_semitones_applied"], len(report["omitted_notes"])))
        for label, target in zip(("上传歌曲", "试听MIDI", "处理报告"), paths):
            print(label + ": " + str(target))
        return 0
    except (MelodyError, OSError, EOFError, ValueError) as error:
        print("转换失败: " + str(error), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
