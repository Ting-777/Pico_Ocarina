"""GUI form adapter; musical decisions stay in midi_to_melody."""
from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import re
import midi_to_melody as engine
from melody_format import MelodyError

@dataclass(frozen=True)
class Form:
    title: str = ""
    transpose: str = "0"
    speed_percent: str = "100"
    countdown_seconds: str = "3"
    start_beat: str = ""
    end_beat: str = ""
    polyphony: str = "error"
    overlap: str = "error"
    ignore_expression: bool = False

def number(text, label):
    try:
        return Fraction(str(text).strip())
    except (ValueError, ZeroDivisionError, TypeError) as error:
        raise MelodyError(label + "请输入数字，例如100、80或0.5") from error

def beat_tick(text, ppq, label):
    if not str(text).strip():
        return None
    value = number(text, label) * ppq
    if value < 0 or value.denominator != 1:
        raise MelodyError(label + "必须是非负、落在MIDI刻度上的拍点；按四分音符从0计数")
    return int(value)

def settings(score, track, channel, form):
    value = str(form.transpose).strip()
    if not re.fullmatch(r"[+-]?\d+", value, flags=re.ASCII):
        raise MelodyError("整体移调请输入整数，例如0、+5或-12")
    speed = number(form.speed_percent, "速度") / 100
    if speed <= 0:
        raise MelodyError("速度必须大于0%；80%表示放慢到原速度的80%")
    countdown = number(form.countdown_seconds, "倒数") * 1000000
    if countdown.denominator != 1 or not 0 <= countdown <= 10000000:
        raise MelodyError("倒数须为0–10秒")
    return dict(track=track, channel=channel, title=form.title.strip() or score.source.stem[:80],
        transpose=int(value), speed=speed, countdown_us=int(countdown),
        start_tick=beat_tick(form.start_beat, score.ppq, "开始拍点") or 0,
        end_tick=beat_tick(form.end_beat, score.ppq, "结束拍点"),
        polyphony=form.polyphony, overlap=form.overlap, ignore_expression=form.ignore_expression)

def convert(score, track, channel, form):
    return engine.convert_score(score, **settings(score, track, channel, form))

def output_path(folder, name):
    name = name.strip()
    if name.lower().endswith(".json"):
        name = name[:-5]
    if (not name or len(name) > 120 or name in (".", "..") or
            any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name) or name.endswith((" ", "."))):
        raise MelodyError("文件名请使用普通文字，不要包含路径或特殊符号")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1,10)} | {"LPT%d" % i for i in range(1,10)}
    if name.split(".")[0].upper() in reserved:
        raise MelodyError("这个文件名是Windows保留名称，请换一个")
    if not str(folder).strip():
        raise MelodyError("请选择保存文件夹")
    return Path(folder).expanduser().resolve() / (name + ".json")

def output_files(output):
    return output, output.with_suffix(".preview.mid"), output.with_suffix(".report.json")

def demo(variant):
    folder = engine.ROOT / "examples/queens_road_east"
    recipe = json.loads((folder / "import_recipe.json").read_text(encoding="utf-8"))
    return folder / "source.mid", recipe["source_sha256"], dict(recipe["variants"][variant])

def form_for_demo(score, recipe):
    return Form(title=recipe["title"], transpose=str(recipe["transpose"]),
        speed_percent=str(Fraction(recipe["speed"]) * 100),
        countdown_seconds=str(Fraction(recipe["countdown_us"],1000000)),
        start_beat=str(Fraction(recipe["start_tick"],score.ppq)),
        end_beat=str(Fraction(recipe["end_tick"],score.ppq)),
        polyphony=recipe["polyphony"], overlap=recipe["overlap"])

def summary(document, report):
    seconds = document["duration_us"] / 1000000
    return ("已生成 %d 个音 · %d分%04.1f秒 · 整体移调 %+d 半音\n"
            "明确省略的八度叠音：%d 个；为松键缩短的音：%d 个。\n"
            "上传 .json 文件；试听和详细报告也保存在同一文件夹。" %
            (len(document["notes"]), seconds // 60, seconds % 60,
             document["metadata"]["transpose_semitones_applied"],
             len(report["omitted_notes"]), len(report["shortened_notes"])))
