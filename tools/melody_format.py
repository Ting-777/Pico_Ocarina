"""Melody-v1 desktop contract and MIDI preview derived from that contract."""
import io
import json
from fractions import Fraction
from pathlib import Path

PROFILE = "oot-user-image-reference-v1"
MAX_BYTES = 65536
MAX_NOTES = 4096
MAX_DURATION = 3600000000
RELEASE_US = 40000
PREVIEW_PPQ = 25000
PREVIEW_TEMPO = 500000
PREVIEW_TICK_US = 20

class MelodyError(ValueError):
    pass

def _integer(value, minimum, maximum, field):
    if type(value) is not int or not minimum <= value <= maximum:
        raise MelodyError("%s 必须是 %d–%d 的整数" % (field, minimum, maximum))

def validate_document(document):
    required = {"format", "schema_version", "fingering_profile", "countdown_us", "duration_us", "notes"}
    if not isinstance(document, dict) or not required <= document.keys():
        raise MelodyError("歌曲缺少必需字段")
    if document.keys() - required - {"title", "metadata"}:
        raise MelodyError("歌曲包含未知字段")
    if document["format"] != "pico-ocarina-melody":
        raise MelodyError("歌曲格式不支持")
    _integer(document["schema_version"], 1, 1, "schema_version")
    if document["fingering_profile"] != PROFILE:
        raise MelodyError("指法表不支持")
    _integer(document["countdown_us"], 0, 10000000, "countdown_us")
    _integer(document["duration_us"], 1, MAX_DURATION, "duration_us")
    if "title" in document and (not isinstance(document["title"], str) or len(document["title"]) > 80):
        raise MelodyError("标题最多80个字符")
    if "metadata" in document and not isinstance(document["metadata"], dict):
        raise MelodyError("metadata 必须是对象")
    def check_metadata(value, depth=0):
        if isinstance(value, (dict, list)):
            if depth >= 16:
                raise MelodyError("metadata 嵌套容器超过16层")
            children = value.values() if isinstance(value, dict) else value
            for child in children:
                check_metadata(child, depth + 1)
    if "metadata" in document:
        check_metadata(document["metadata"])
    notes = document["notes"]
    if not isinstance(notes, list) or not 1 <= len(notes) <= MAX_NOTES:
        raise MelodyError("音符数必须是1–4096")
    previous = None
    for index, note in enumerate(notes):
        if not isinstance(note, list) or len(note) != 3:
            raise MelodyError("第%d音不是[开始,结束,音高]" % index)
        on, off, pitch = note
        _integer(on, 0, MAX_DURATION, "第%d音开始" % index)
        _integer(off, 1, MAX_DURATION, "第%d音结束" % index)
        _integer(pitch, 71, 89, "第%d音音高" % index)
        if not on < off <= document["duration_us"]:
            raise MelodyError("第%d音起止时间越界" % index)
        if previous and on - previous[1] < RELEASE_US:
            raise MelodyError("第%d音之前不足40ms松键，或音符顺序/重叠错误" % index)
        previous = note
    return document

def encode_document(document):
    validate_document(document)
    try:
        data = (json.dumps(document, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, UnicodeError) as error:
        raise MelodyError("歌曲不是合法UTF-8 JSON: %s" % error) from error
    if len(data) > MAX_BYTES:
        raise MelodyError("歌曲文件超过64KiB，请缩短片段；4096音与文件大小上限同时生效")
    return data

def decode_document(data):
    """Validate the exact bytes that will be uploaded, without re-encoding them."""
    if not data or len(data) > MAX_BYTES:
        raise MelodyError("歌曲文件必须为1–65536字节")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise MelodyError("JSON字段重复: " + key)
            result[key] = value
        return result
    def invalid_constant(value):
        raise MelodyError("JSON不允许 " + value)
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise MelodyError("无法读取歌曲JSON: %s" % error) from error
    encode_document(document)
    return document

def read_document(path):
    with Path(path).open("rb") as file:
        return decode_document(file.read(MAX_BYTES + 1))

def preview_bytes(document):
    """Return preview bytes plus measured quantization error; never re-import MIDI."""
    encode_document(document)
    try:
        import mido
    except ImportError as error:
        raise MelodyError("请先运行 python -m pip install -r tools/requirements-midi.txt") from error
    midi = mido.MidiFile(type=0, ticks_per_beat=PREVIEW_PPQ, charset="utf-8")
    track = mido.MidiTrack()
    midi.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name=document.get("title", "Pico Ocarina")))
    track.append(mido.MetaMessage("set_tempo", tempo=PREVIEW_TEMPO))
    track.append(mido.Message("program_change", program=79, channel=0))
    events, max_error, minimum_ticks = [], 0, []
    for index, (on, off, pitch) in enumerate(document["notes"]):
        # round() on integer ratios through Fraction keeps tie handling explicit.
        on_tick, off_tick = round(Fraction(on, PREVIEW_TICK_US)), round(Fraction(off, PREVIEW_TICK_US))
        if off_tick <= on_tick:
            off_tick = on_tick + 1
            minimum_ticks.append(index)
        max_error = max(max_error, abs(on_tick * PREVIEW_TICK_US - on), abs(off_tick * PREVIEW_TICK_US - off))
        events.append((on_tick, 1, mido.Message("note_on", note=pitch, velocity=90, channel=0)))
        events.append((off_tick, 0, mido.Message("note_off", note=pitch, velocity=0, channel=0)))
    end = max(round(Fraction(document["duration_us"], PREVIEW_TICK_US)), max(item[0] for item in events))
    events.append((end, 2, mido.MetaMessage("end_of_track")))
    previous = 0
    for tick, _, message in sorted(events, key=lambda item: (item[0], item[1])):
        track.append(message.copy(time=tick - previous))
        previous = tick
    output = io.BytesIO()
    midi.save(file=output)
    return output.getvalue(), {
        "tick_us": PREVIEW_TICK_US, "max_event_error_us": max_error,
        "minimum_one_tick_notes": minimum_ticks,
        "includes_countdown": False,
    }
