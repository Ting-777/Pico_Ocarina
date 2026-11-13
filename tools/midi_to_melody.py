"""Inspect MIDI tracks and convert one selected melody to the Pico melody-v1 JSON."""
from i18n import tr
import argparse
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import heapq
import io
import json
import os
from pathlib import Path
import sys
import tempfile

from melody_format import (MelodyError, PROFILE, RELEASE_US, MAX_NOTES, MAX_DURATION,
    PREVIEW_PPQ, PREVIEW_TEMPO, PREVIEW_TICK_US, encode_document, preview_bytes, read_document)
from melody_timing import PLAYBACK_RELEASE_US, extend_release_gaps

ROOT = Path(__file__).resolve().parents[1]
MAX_MIDI_BYTES = 16 * 1024 * 1024
MAX_MIDI_EVENTS = 500000
TEMPO_DUPLICATE_TOLERANCE_DENOMINATOR = 1000  # At most 0.1% total spread.
AUTO_RANGE_MAX_NOTES = 2000  # Headroom for 64KiB JSON, timestamps and audit metadata.

def require_mido():
    try:
        import mido
        return mido
    except ImportError as error:
        raise MelodyError(tr("请先运行 python -m pip install -r tools/requirements-midi.txt")) from error

class ConversionIssue(MelodyError):
    def __init__(self, kind, message, **details):
        super().__init__(message)
        self.kind, self.details = kind, details

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
    def __init__(self, ppq, changes, conflict_policy="error"):
        if conflict_policy not in ("error", "first", "last", "fixed-120"):
            raise MelodyError(tr("不支持的速度冲突处理方式"))
        self.conflict_policy = conflict_policy
        self.ppq = ppq
        points = {0: 500000}
        grouped = defaultdict(list)
        for tick, tempo in changes:
            if tempo <= 0 and conflict_policy!="fixed-120":
                raise ConversionIssue("tempo_invalid", tr("MIDI速度必须大于0；可明确选择按120 BPM读取"))
            grouped[tick].append(tempo)
        self.adjustments = []
        for tick, tempos in sorted(grouped.items()):
            low, high = min(tempos), max(tempos)
            if conflict_policy=="fixed-120":
                if low!=500000 or high!=500000:
                    self.adjustments.append({"tick":tick,"events":len(tempos),"minimum_tempo":low,
                        "maximum_tempo":high,"selected_tempo":500000})
                continue
            conflict = (high - low) * TEMPO_DUPLICATE_TOLERANCE_DENOMINATOR > low
            if conflict and conflict_policy == "error":
                raise ConversionIssue("tempo", tr("tick %d 有冲突的速度事件，请选择采用第一条或最后一条速度") % tick,
                                      tick=tick, tempos=tempos)
            # Match ordered MIDI playback for near-identical simultaneous
            # events: the last event sets the tempo. Bound the whole group so
            # a chain of tiny differences cannot conceal a large conflict.
            points[tick] = tempos[0] if conflict and conflict_policy == "first" else tempos[-1]
            if high != low:
                self.adjustments.append({"tick": tick, "events": len(tempos),
                    "minimum_tempo": low, "maximum_tempo": high, "selected_tempo": points[tick]})
        self.ticks = sorted(points)
        self.tempos = [points[tick] for tick in self.ticks]
        self.numerators = [0]
        for index in range(1, len(self.ticks)):
            self.numerators.append(self.numerators[-1] +
                (self.ticks[index] - self.ticks[index - 1]) * self.tempos[index - 1])

    def at(self, tick):
        index = bisect_right(self.ticks, tick) - 1
        return Fraction(self.numerators[index] + (tick - self.ticks[index]) * self.tempos[index], self.ppq)

    def tick_at_us(self, us):
        scaled=Fraction(str(us))*self.ppq
        index=max(0,bisect_right(self.numerators,scaled)-1)
        return self.ticks[index]+(scaled-self.numerators[index])/self.tempos[index]

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

def read_score(source, tempo_policy="error"):
    mido = require_mido()
    source = Path(source)
    with source.open("rb") as file:
        raw = file.read(MAX_MIDI_BYTES + 1)
    if len(raw) > MAX_MIDI_BYTES:
        raise MelodyError(tr("MIDI超过16MiB，请先拆分"))
    try:
        midi = mido.MidiFile(file=io.BytesIO(raw), clip=False)
    except (EOFError, ValueError, KeyError, OSError) as error:
        raise MelodyError(tr("无法解析MIDI: %s") % error) from error
    if midi.type not in (0, 1):
        raise MelodyError(tr("支持MIDI类型0/1；请将类型2文件另存为类型0/1"))
    if midi.ticks_per_beat <= 0:
        raise MelodyError(tr("请将SMPTE文件另存为PPQ时间制"))
    channels, names, ends, changes = {}, [], [], []
    event_count = 0
    for track_index, track in enumerate(midi.tracks):
        names.append(track.name)
        active = {}
        tick = 0
        for order, message in enumerate(track):
            event_count += 1
            if event_count > MAX_MIDI_EVENTS:
                raise MelodyError(tr("MIDI事件超过500000，请先拆分"))
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
                    channel.errors.append(tr("tick %d: 音高%d尚未结束就再次起音") % (tick, message.note))
                else:
                    active[pitch_key] = (tick, message.velocity, order)
            else:
                start = active.pop(pitch_key, None)
                if start is None:
                    channel.errors.append(tr("tick %d: 音高%d没有对应起音") % (tick, message.note))
                elif start[0] >= tick:
                    channel.errors.append(tr("tick %d: 音高%d时长不为正") % (tick, message.note))
                else:
                    channel.notes.append(Note(start[0], tick, message.note, start[1], start[2]))
        for (channel_index, pitch), start in active.items():
            channels[(track_index, channel_index)].errors.append(tr("tick %d: 音高%d缺少结束事件") % (start[0], pitch))
        ends.append(tick)
    for channel in channels.values():
        channel.notes.sort(key=lambda note: (note.on, note.source_index))
    return Score(source, hashlib.sha256(raw).hexdigest(), midi.type, midi.ticks_per_beat,
                 names, ends, channels, TempoMap(midi.ticks_per_beat, changes, tempo_policy))

def note_name(pitch):
    return ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")[pitch % 12] + str(pitch // 12 - 1)

def shift_options(notes):
    if not notes:
        return []
    return list(range(71 - min(note.pitch for note in notes), 90 - max(note.pitch for note in notes)))

def _select_active_voice(notes, policy):
    """Select the highest/lowest active source note at each event boundary."""
    events = defaultdict(list)
    for index, note in enumerate(notes):
        events[note.on].append((True, index))
        events[note.off].append((False, index))
    ticks = sorted(events)
    active, heap, selected = set(), [], []
    for position, tick in enumerate(ticks[:-1]):
        for starting, index in events[tick]:
            if starting:
                active.add(index)
                note = notes[index]
                priority = -note.pitch if policy == "highest" else note.pitch
                heapq.heappush(heap, (priority, note.source_index, index))
            else:
                active.discard(index)
        while heap and heap[0][2] not in active:
            heapq.heappop(heap)
        if not heap:
            continue
        note = notes[heap[0][2]]
        off = ticks[position + 1]
        # Ignore changes in discarded voices; retain actual repeated attacks.
        if selected and selected[-1].off == tick and selected[-1].source_index == note.source_index:
            previous = selected[-1]
            selected[-1] = Note(previous.on, off, note.pitch, note.velocity, note.source_index)
        else:
            selected.append(Note(tick, off, note.pitch, note.velocity, note.source_index))
    kept = defaultdict(list)
    for note in selected:
        kept[note.source_index].append([note.on, note.off])
    omitted, edits = [], []
    for note in notes:
        intervals = kept[note.source_index]
        if intervals != [[note.on, note.off]]:
            edits.append({"source_index": note.source_index, "pitch": note.pitch,
                          "original": [note.on, note.off], "retained": intervals})
        if not intervals:
            omitted.append({"source_index": note.source_index, "tick": note.on, "pitch": note.pitch,
                            "reason": "explicit_" + policy})
    return selected, omitted, {"policy": policy, "input_notes": len(notes),
        "output_segments": len(selected), "changed_notes": edits}

def pitch_filter_bounds(pitch_min=None, pitch_max=None):
    if pitch_min is None and pitch_max is None:
        return None
    if (type(pitch_min) is not int or type(pitch_max) is not int or
            not 0 <= pitch_min <= pitch_max <= 127):
        raise MelodyError(tr("音域框上下限须为0–127的整数，且下限不能大于上限"))
    return pitch_min, pitch_max

def selection_notes(score, track, channel, start_tick=0, end_tick=None, polyphony="error",
                    pitch_min=None, pitch_max=None):
    """Untransposed tick events for the visual selector and its audition."""
    end_tick = score.track_ends[track] if end_tick is None else end_tick
    bounds = pitch_filter_bounds(pitch_min, pitch_max)
    notes = [Note(max(note.on, start_tick), min(note.off, end_tick), note.pitch, note.velocity, note.source_index)
             for note in score.channels[(track, channel)].notes if note.off > start_tick and note.on < end_tick
             and (bounds is None or bounds[0] <= note.pitch <= bounds[1])]
    if polyphony in ("highest", "lowest") and notes:
        notes = _select_active_voice(notes, polyphony)[0]
    return notes

def selection_info(score, track, channel, start_tick=0, end_tick=None, polyphony="error",
                   pitch_min=None, pitch_max=None):
    notes = selection_notes(score, track, channel, start_tick, end_tick, polyphony, pitch_min, pitch_max)
    pitches = [note.pitch for note in notes]
    return {"notes": len(notes), "range": [min(pitches), max(pitches)] if pitches else None,
            "transpose_options": shift_options(notes)}

def suggest_pitch_window(score, track, channel, start_tick=0, end_tick=None, preferred=None):
    """Most source notes in 19 consecutive pitches; held time breaks ties."""
    notes = selection_notes(score, track, channel, start_tick, end_tick)
    if not notes:
        return min(109, max(0, 71 if preferred is None else preferred))
    counts, durations = [0]*128, [0]*128
    for note in notes:
        counts[note.pitch] += 1
        durations[note.pitch] += note.off-note.on
    center = sum(note.pitch for note in notes)/len(notes)-9
    preferred = center if preferred is None else preferred
    return max(range(110), key=lambda low: (sum(counts[low:low+19]),
        sum(durations[low:low+19]), -abs(low-preferred), -abs(low-center), low))

def suggest_range(score, track, channel, polyphony="highest"):
    """Find a long contiguous interval within pitch, count and time limits."""
    from collections import deque
    policy = polyphony if polyphony in ("highest", "lowest") else "highest"
    notes = selection_notes(score, track, channel, polyphony=policy)
    if not notes:
        raise MelodyError(tr("所选轨道没有可选音符"))
    low, high = deque(), deque()
    left, best = 0, (0, notes[0].off, notes[0].on)
    for right, note in enumerate(notes):
        while low and notes[low[-1]].pitch >= note.pitch: low.pop()
        while high and notes[high[-1]].pitch <= note.pitch: high.pop()
        low.append(right); high.append(right)
        def estimated():
            return float(score.tempo.at(note.off)-score.tempo.at(notes[left].on))+(right-left)*PLAYBACK_RELEASE_US
        while notes[high[0]].pitch - notes[low[0]].pitch > 18 or right-left+1 > min(MAX_NOTES,AUTO_RANGE_MAX_NOTES) or (estimated()>MAX_DURATION-5000 and left<right):
            left += 1
            while low[0] < left: low.popleft()
            while high[0] < left: high.popleft()
        end=note.off
        if estimated()>MAX_DURATION-5000:
            end=min(end,int(score.tempo.tick_at_us(score.tempo.at(note.on)+MAX_DURATION-5000)))
        length = float(score.tempo.at(end)-score.tempo.at(notes[left].on))
        if length > best[0]: best = (length, end, notes[left].on)
    return best[2], best[1], policy

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
            "tempo_points": len(score.tempo.ticks), "source_sha256": score.sha256, "candidates": rows,
            "tempo_adjustments": score.tempo.adjustments}

def audition_bytes(score, track, channel_index, polyphony=None):
    """Unmodified channel audition, with the global tempo map from every track."""
    mido = require_mido()
    channel = score.channels[(track, channel_index)]
    if channel.errors:
        raise MelodyError(tr("不能导出有配对错误的轨道试听"))
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
    messages = channel.messages
    if polyphony in ("highest", "lowest"):
        messages = [(tick, message) for tick, message in messages if message.type not in ("note_on", "note_off")]
        for note in selection_notes(score, track, channel_index, polyphony=polyphony):
            messages.extend([(note.on, mido.Message("note_on", note=note.pitch, velocity=note.velocity, channel=channel_index)),
                             (note.off, mido.Message("note_off", note=note.pitch, velocity=0, channel=channel_index))])
        messages.sort(key=lambda item: (item[0], 0 if item[1].type == "note_off" else 1))
    for tick, message in messages:
        voice.append(message.copy(time=tick - previous))
        previous = tick
    voice.append(mido.MetaMessage("end_of_track", time=score.track_ends[track] - previous))
    output = io.BytesIO()
    midi.save(file=output)
    return output.getvalue()

def range_audition_bytes(score, track, channel_index, start_us, end_us, polyphony="error",
                         pitch_min=None, pitch_max=None):
    """Audition a clipped range from zero, including a note held at the cursor."""
    if not 0 <= start_us < end_us:
        raise MelodyError(tr("试听范围必须有正时长"))
    mido = require_mido()
    midi = mido.MidiFile(type=0, ticks_per_beat=PREVIEW_PPQ)
    voice = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=PREVIEW_TEMPO)])
    midi.tracks.append(voice)
    events, initial = [], {}
    for tick, message in score.channels[(track, channel_index)].messages:
        if message.type in ("note_on", "note_off"): continue
        when = score.tempo.at(tick)
        if when >= end_us: continue
        if when < start_us:
            key = (message.type, getattr(message, "control", None), getattr(message, "note", None))
            initial[key] = (when, message)
        else:
            events.append((round((when-start_us)/PREVIEW_TICK_US),0,message))
    for _, message in sorted(initial.values(), key=lambda item:item[0]):
        voice.append(message.copy(time=0))
    for note in selection_notes(score, track, channel_index, polyphony=polyphony,
                                pitch_min=pitch_min, pitch_max=pitch_max):
        on, off = max(start_us, score.tempo.at(note.on)), min(end_us, score.tempo.at(note.off))
        if on >= off: continue
        a, b = round((on-start_us)/PREVIEW_TICK_US), round((off-start_us)/PREVIEW_TICK_US)
        events.extend([(a,2,mido.Message("note_on",channel=channel_index,note=note.pitch,velocity=note.velocity)),
                       (max(a+1,b),1,mido.Message("note_off",channel=channel_index,note=note.pitch,velocity=0))])
    end = max(round(Fraction(end_us-start_us,PREVIEW_TICK_US)), max((item[0] for item in events),default=0))
    events.append((end,3,mido.MetaMessage("end_of_track")))
    previous = 0
    for tick, _, message in sorted(events,key=lambda item:(item[0],item[1])):
        voice.append(message.copy(time=tick-previous)); previous=tick
    output=io.BytesIO(); midi.save(file=output)
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
                  title=None, countdown_us=3000000, release_us=PLAYBACK_RELEASE_US, valid_notes_only=False,
                  pitch_min=None, pitch_max=None):
    if type(track) is not int or not 0 <= track < len(score.track_names):
        raise MelodyError(tr("轨道不存在，请先inspect；轨道编号从0开始"))
    candidates = [index for candidate_track, index in score.channels
                  if candidate_track == track and (score.channels[(track, index)].notes or score.channels[(track, index)].errors)]
    if channel is None:
        if len(candidates) != 1:
            raise MelodyError(tr("此轨有%d个通道，请用--channel明确选择（从0开始）") % len(candidates))
        channel = candidates[0]
    if type(channel) is not int or not 0 <= channel <= 15:
        raise MelodyError(tr("通道编号必须是0–15的整数"))
    if (track, channel) not in score.channels:
        raise MelodyError(tr("所选轨道/通道不存在"))
    if channel == 9:
        raise MelodyError(tr("请选择旋律通道；通道9为GM鼓通道"))
    selected = score.channels[(track, channel)]
    if selected.errors and not valid_notes_only:
        raise ConversionIssue("pairing", tr("音符配对错误: ") + "; ".join(selected.errors[:3]) + tr("。可只转换已完整配对的音符。"))
    if end_tick is None:
        end_tick = score.track_ends[track]
    if type(start_tick) is not int or type(end_tick) is not int or not 0 <= start_tick < end_tick:
        raise MelodyError(tr("片段要求 0 <= start < end，单位为tick"))
    if end_tick > score.track_ends[track]:
        raise MelodyError(tr("片段结束超过所选轨道结尾"))
    speed = Fraction(str(speed)) if not isinstance(speed, Fraction) else speed
    if speed <= 0:
        raise MelodyError(tr("速度倍率必须大于0"))
    if polyphony not in ("error", "octave-highest", "highest", "lowest") or overlap not in ("error", "trim"):
        raise MelodyError(tr("不支持的复音或重叠处理规则"))
    expression = _expression(selected, start_tick, end_tick)
    if expression and not ignore_expression:
        raise ConversionIssue("expression", tr("片段含弯音或延音踏板，可选择忽略这些效果后生成"))
    bounds = pitch_filter_bounds(pitch_min, pitch_max)
    groups, clipped, pitch_excluded = defaultdict(list), [], []
    source_count = 0
    for note in selected.notes:
        if note.off <= start_tick or note.on >= end_tick:
            continue
        on, off = max(note.on, start_tick), min(note.off, end_tick)
        source_count += 1
        if bounds is not None and not bounds[0] <= note.pitch <= bounds[1]:
            pitch_excluded.append({"source_index":note.source_index,"pitch":note.pitch,
                                   "on_tick":on,"off_tick":off})
            continue
        if (on, off) != (note.on, note.off):
            clipped.append({"source_index": note.source_index, "original": [note.on, note.off],
                            "selected": [on, off], "pitch": note.pitch})
        groups[on].append(Note(on, off, note.pitch, note.velocity, note.source_index))
    if not groups:
        if bounds is not None:
            raise ConversionIssue("pitch_filter", tr("音域框内没有音符，请上下拖动音域框或调整左右范围"))
        raise MelodyError(tr("所选片段没有音符"))
    notes, omitted = [], []
    selection = None
    select_active = polyphony in ("highest", "lowest")
    if select_active:
        source_notes = [note for _, group in sorted(groups.items()) for note in group]
        notes, omitted, selection = _select_active_voice(source_notes, polyphony)
    for onset, group in ([] if select_active else sorted(groups.items())):
        if len(group) > 1:
            if polyphony == "error":
                raise ConversionIssue("polyphony", tr("tick %d 同时有多个音，可选择全部取最高音或最低音") % onset)
            if len({note.pitch % 12 for note in group}) != 1:
                raise ConversionIssue("polyphony", tr("tick %d 不是纯八度叠音，请改用全部取最高音或最低音") % onset)
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
            raise ConversionIssue("overlap", tr("tick %d 与前音重叠，可取最高/最低音，或缩短重叠部分") % following.on)
    options = shift_options(notes)
    if type(transpose) is not int or transpose not in options:
        suggestion = "%d..%d" % (options[0], options[-1]) if options else tr("无：所选旋律跨度超过18半音")
        raise ConversionIssue("transpose" if options else "range", tr("移调后超出B4–F6；可用的整段移调范围为 ") + suggestion,
                              options=options)
    # Anchor the selected melody to its first retained note, not the beginning
    # of the track/selection. Subtract exact tempo-map time before rounding.
    origin = score.tempo.at(notes[0].on)
    leading_rest_removed_us = round((origin - score.tempo.at(start_tick)) / speed)
    def time(tick):
        return round((score.tempo.at(tick) - origin) / speed)
    duration = time(end_tick)
    rows, shortened, selection_shifts = [], [], []
    inserted_rest = 0
    for index, note in enumerate(notes):
        on, original_off = time(note.on), time(note.off)
        if select_active:
            if index:
                gap = on - time(notes[index - 1].off)
                inserted_rest += max(0, RELEASE_US - gap)
            on += inserted_rest
            original_off += inserted_rest
            off = original_off
        else:
            next_on = time(notes[index + 1].on) if index + 1 < len(notes) else duration
            off = min(original_off, next_on - RELEASE_US)
        selection_shifts.append(inserted_rest)
        if off <= on:
            raise ConversionIssue("timing", tr("第%d音（源tick %d）容不下正音长和40ms松键，可保留音长并增加间隔，或放慢速度") % (index, note.on))
        rows.append([on, off, note.pitch + transpose])
        if off != original_off:
            shortened.append({"note_index": index, "source_index": note.source_index,
                              "original_off_us": original_off, "playback_off_us": off,
                              "shortened_us": original_off - off})
    title = score.source.stem[:80] if title is None else title
    if len(rows)>MAX_NOTES or duration+inserted_rest>MAX_DURATION:
        raise ConversionIssue("capacity", tr("所选片段超过4096音或60分钟上限，请拖动选择较短片段"))
    document = {
        "format": "pico-ocarina-melody", "schema_version": 1, "title": title,
        "fingering_profile": PROFILE, "countdown_us": countdown_us, "duration_us": duration + inserted_rest,
        "notes": rows,
        "metadata": {
            "source_sha256": score.sha256, "source_track": track, "source_channel": channel,
            "source_start_tick": start_tick, "source_end_tick": end_tick,
            "source_first_note_tick": notes[0].on, "leading_rest_removed_us": leading_rest_removed_us,
            "transpose_semitones_applied": transpose, "speed_applied": str(speed),
            "polyphony_policy": polyphony, "overlap_policy": overlap,
            "ignored_expression": expression if ignore_expression else [],
        },
    }
    if score.tempo.adjustments:
        document["metadata"]["tempo_resolution"] = {"policy": "near_duplicate_last_event" if score.tempo.conflict_policy=="error" else "explicit_"+score.tempo.conflict_policy,
            "positions": len(score.tempo.adjustments)}
    if selected.errors:
        document["metadata"]["valid_notes_only"] = True
        document["metadata"]["source_pairing_errors"] = len(selected.errors)
    if bounds is not None:
        document["metadata"]["source_pitch_filter"] = {"minimum":bounds[0],"maximum":bounds[1],
            "excluded_notes":len(pitch_excluded)}
    document, timing = extend_release_gaps(document, release_us)
    timing["added_rest_us"] += inserted_rest
    timing["shifts_us"] = [shift + earlier for shift, earlier in zip(timing["shifts_us"], selection_shifts)]
    timing["shifted_notes"] = sum(shift > 0 for shift in timing["shifts_us"])
    document["metadata"].update(minimum_release_us=release_us, added_rest_us=timing["added_rest_us"])
    for entry in shortened:
        shift = timing["shifts_us"][entry["note_index"]]
        entry["original_off_us"] += shift
        entry["playback_off_us"] += shift
    encode_document(document)
    report = {
        "source_sha256": score.sha256, "track": track, "channel": channel,
        "track_name": score.track_names[track], "source_notes_in_selection": source_count,
        "output_notes": len(rows), "duration_us": document["duration_us"], "countdown_us": countdown_us,
        "leading_rest_removed_us": leading_rest_removed_us,
        "tempo_adjustments": score.tempo.adjustments,
        "uniform_transpose_options": options, "settings": document["metadata"],
        "omitted_notes": omitted, "clipped_notes": clipped, "shortened_notes": shortened,
        "ignored_expression": expression if ignore_expression else [], "release_timing": timing,
        "polyphony_selection": selection,
        "source_pairing_errors": selected.errors if valid_notes_only else [],
        "pitch_filter": {"minimum":bounds[0],"maximum":bounds[1],"excluded_notes":pitch_excluded}
                        if bounds is not None else None,
    }
    return document, report

def write_bundle(payloads, source=None, force=False):
    targets = [Path(file).resolve() for file, _ in payloads]
    if len(set(targets)) != len(targets) or (source is not None and Path(source).resolve() in targets):
        raise MelodyError(tr("输出文件不可重名，也不能覆盖源文件"))
    if not force and any(target.exists() for target in targets):
        raise MelodyError(tr("输出文件已存在；换一个输出名，或用--force明确覆盖"))
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
        raise MelodyError(tr("拍点不在MIDI tick网格上；beat按从0开始的四分音符计数"))
    return int(value)

def positive_fraction(value):
    try:
        number = Fraction(value)
        if number <= 0:
            raise ValueError()
        return number
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError(tr("请输入大于0的数，例如1、0.8或3/2"))

def beat_fraction(value):
    try:
        result = Fraction(value)
        if result < 0:
            raise ValueError()
        return result
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError(tr("拍点必须是非负数字"))

def main(argv=None):
    parser = argparse.ArgumentParser(description=tr("MIDI选轨、检查和转换为Pico歌曲JSON；轨道/通道均从0开始"))
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help=tr("列出轨道/通道，并可导出原轨试听"))
    inspect.add_argument("input", type=Path)
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--audition-dir", type=Path)
    inspect.add_argument("--force", action="store_true")
    inspect.add_argument("--tempo-policy", choices=("error", "first", "last", "fixed-120"), default="error")
    convert = commands.add_parser("convert", help=tr("明确选择旋律后转换"))
    convert.add_argument("input", type=Path)
    convert.add_argument("--track", type=int, required=True)
    convert.add_argument("--channel", type=int, choices=range(16))
    for prefix in ("start", "end"):
        group = convert.add_mutually_exclusive_group()
        group.add_argument("--" + prefix + "-tick", type=int)
        group.add_argument("--" + prefix + "-beat", type=beat_fraction)
    convert.add_argument("--transpose", type=int, default=0)
    convert.add_argument("--pitch-min", type=int, help=tr("明确排除音域框外音符：MIDI音高下限，含边界"))
    convert.add_argument("--pitch-max", type=int, help=tr("MIDI音高上限，须与--pitch-min同时填写"))
    convert.add_argument("--speed", type=positive_fraction, default=Fraction(1))
    convert.add_argument("--polyphony", choices=("error", "octave-highest", "highest", "lowest"), default="error")
    convert.add_argument("--overlap", choices=("error", "trim"), default="error")
    convert.add_argument("--ignore-expression", action="store_true")
    convert.add_argument("--valid-notes-only", action="store_true",help=tr("明确丢弃配对异常，只转换完整音符"))
    convert.add_argument("--title")
    convert.add_argument("--countdown-us", type=int, default=3000000)
    convert.add_argument("--release-us", type=int, default=PLAYBACK_RELEASE_US,
                         help=tr("音间松键，默认120000微秒；保持每音长度并延后后续音"))
    convert.add_argument("-o", "--output", type=Path, required=True)
    convert.add_argument("--force", action="store_true")
    convert.add_argument("--tempo-policy", choices=("error", "first", "last", "fixed-120"), default="error")
    preview = commands.add_parser("preview", help=tr("只从最终JSON重新生成试听MIDI"))
    preview.add_argument("input", type=Path)
    preview.add_argument("-o", "--output", type=Path, required=True)
    preview.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "preview":
            data, info = preview_bytes(read_document(args.input))
            write_bundle([(args.output, data)], args.input, args.force)
            print(tr("试听已生成: %s；最大时间量化误差 %d 微秒") % (args.output, info["max_event_error_us"]))
            return 0
        source = args.input
        score = read_score(source, args.tempo_policy)
        if args.command == "inspect":
            result = inspect_score(score)
            if args.audition_dir:
                payloads = []
                for row in result["candidates"]:
                    if row["errors"]:
                        row["audition_skipped"] = tr("音符配对错误")
                        continue
                    target = args.audition_dir / ("track_%d_channel_%d.mid" % (row["track"], row["channel"]))
                    payloads.append((target, audition_bytes(score, row["track"], row["channel"])))
                    row["audition"] = str(target)
                write_bundle(payloads, source, args.force)
            if args.json:
                print(json.dumps(result, ensure_ascii=True))
            else:
                print(tr("MIDI类型%d，PPQ=%d，%d条轨，%d个速度点；轨道/通道从0开始") %
                      (result["type"], result["ppq"], result["tracks"], result["tempo_points"]))
                print(tr("轨道 通道 音数 音域 同起音组 重叠起音 配对错误 名称"))
                for row in result["candidates"]:
                    pitches = row["range"]
                    span = note_name(pitches[0]) + ".." + note_name(pitches[1]) if pitches else "-"
                    print("%4d %4d %4d %-10s %8d %8d %8d %s%s" %
                          (row["track"], row["channel"], row["notes"], span, row["simultaneous_groups"],
                           row["overlapping_onsets"], len(row["errors"]),
                           json.dumps(row["name"], ensure_ascii=False), tr(" [GM鼓]") if row["drum_channel"] else ""))
                if args.audition_dir:
                    print(tr("原轨试听目录: ") + str(args.audition_dir))
            return 0
        document, report = convert_score(score, track=args.track, channel=args.channel,
            start_tick=_tick(args, score, "start"), end_tick=_tick(args, score, "end"),
            transpose=args.transpose, speed=args.speed, polyphony=args.polyphony, overlap=args.overlap,
            ignore_expression=args.ignore_expression, title=args.title, countdown_us=args.countdown_us,
            release_us=args.release_us,valid_notes_only=args.valid_notes_only,
            pitch_min=args.pitch_min,pitch_max=args.pitch_max)
        output = args.output
        paths = emit_conversion(source, document, report, output, args.force)
        selection=report["polyphony_selection"]
        changed=len(selection["changed_notes"]) if selection else len(report["omitted_notes"])
        print(tr("转换完成：%d音，%.4f秒；整体移调%+d半音；多音取舍涉及%d个源音") %
              (len(document["notes"]), document["duration_us"] / 1000000,
               document["metadata"]["transpose_semitones_applied"], changed))
        if report["pitch_filter"]:
            print(tr("音域框 %s..%s，明确排除%d个源音；明细见处理报告。") %
                (note_name(args.pitch_min),note_name(args.pitch_max),len(report["pitch_filter"]["excluded_notes"])))
        print(tr("音间松键%d毫秒，新增休止%.3f秒。") %
              (args.release_us // 1000, report["release_timing"]["added_rest_us"] / 1000000))
        for label, target in zip((tr("上传歌曲"), tr("试听MIDI"), tr("处理报告")), paths):
            print(label + ": " + str(target))
        return 0
    except (MelodyError, OSError, EOFError, ValueError) as error:
        print(tr("转换失败: ") + str(error), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
