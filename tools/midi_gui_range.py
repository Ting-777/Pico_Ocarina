"""Visual, audible MIDI range selection without manual beat arithmetic."""
from i18n import tr, localized_combo
from bisect import bisect_left
from math import ceil
import tkinter as tk
from tkinter import ttk
import midi_to_melody as engine


def clock_text(us):
    seconds = max(0, us / 1000000)
    return "%d:%04.1f" % (seconds // 60, seconds % 60)


class RangeDialog:
    def __init__(self, parent, score, row, choices, policy, start_tick, end_tick,
                 apply, preview, stop, position, pitch_min=None):
        self.score, self.row, self.choices = score, row, choices
        self.apply_callback, self.preview, self.stop, self.position = apply, preview, stop, position
        self.track, self.channel = row["track"], row["channel"]
        self.end_of_track = score.track_ends[self.track]
        self.total_us = float(score.tempo.at(self.end_of_track))
        self.start_tick, self.end_tick = start_tick, end_tick
        self.cursor_us = float(score.tempo.at(start_tick))
        self.view = (0, self.total_us)
        self.drag = None
        self.band_low = pitch_min
        self.updating_progress = False
        self.window = tk.Toplevel(parent)
        self.window.title(tr("拖动选择片段"))
        self.window.geometry("850x500")
        self.window.minsize(640, 400)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        outer = ttk.Frame(self.window, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        instructions = ttk.Label(outer, text=tr("左右拖蓝线选时间，松开后自动框住音符最多的18半音；绿框可上下拖动。\n框外音符会舍弃；点击定位或拖播放进度试听框内音符，按原速原音高。"),
                  justify="left", width=1, wraplength=790)
        instructions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.canvas = tk.Canvas(outer, height=190, background="#18212d", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda event: self.draw())
        self.canvas.bind("<Button-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.motion)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.info = tk.StringVar()
        info_label = ttk.Label(outer, textvariable=self.info, justify="left", width=1, wraplength=790)
        info_label.grid(row=2, column=0, sticky="ew", pady=8)
        outer.bind("<Configure>", lambda event: (
            instructions.configure(wraplength=max(200, event.width - 24)),
            info_label.configure(wraplength=max(200, event.width - 24))))
        mode = ttk.Frame(outer)
        mode.grid(row=3, column=0, sticky="ew")
        mode.columnconfigure(1, weight=1)
        ttk.Label(mode, text=tr("多音取舍")).grid(row=0, column=0, padx=(0, 8))
        self.policy = tk.StringVar(value=policy)
        self.policy_combo = localized_combo(mode, self.policy, list(choices), state="readonly", width=21)
        self.policy_combo.grid(row=0, column=1, sticky="w")
        self.policy_combo.bind("<<ComboboxSelected>>", lambda event: (self.stop(),self.analyze()), add=True)
        automatic=ttk.Menubutton(mode,text=tr("自动选择 ▾"))
        menu=tk.Menu(automatic,tearoff=False)
        menu.add_command(label=tr("音区：框住最多音符"),command=self.auto_band)
        menu.add_command(label=tr("时间：寻找可演奏片段"),command=self.auto_range)
        automatic.configure(menu=menu)
        automatic.grid(row=0,column=2,padx=6)
        ttk.Button(mode, text=tr("放大选区"), command=self.zoom).grid(row=0, column=3)
        ttk.Button(mode, text=tr("全曲"), command=self.full_view).grid(row=0, column=4, padx=(6, 0))
        progress = ttk.Frame(outer)
        progress.grid(row=4, column=0, sticky="ew", pady=10)
        progress.columnconfigure(1, weight=1)
        ttk.Label(progress, text=tr("播放位置")).grid(row=0, column=0, padx=(0, 8))
        self.progress = tk.DoubleVar(value=self.cursor_us / 1000000)
        self.scale = ttk.Scale(progress, from_=0, to=max(.001, self.total_us / 1000000),
                               variable=self.progress, command=self.seek)
        self.scale.grid(row=0, column=1, sticky="ew")
        self.scale.bind("<ButtonPress-1>", self.begin_seek)
        self.scale.bind("<ButtonRelease-1>", self.finish_seek)
        buttons = ttk.Frame(outer)
        buttons.grid(row=5, column=0, sticky="ew")
        ttk.Button(buttons, text=tr("试听选段"), command=self.play_selection).pack(side="left")
        ttk.Button(buttons, text=tr("从光标试听"), command=self.play_cursor).pack(side="left", padx=6)
        ttk.Button(buttons, text=tr("停止"), command=self.stop).pack(side="left")
        self.apply_button = ttk.Button(buttons, text=tr("使用此片段"), command=self.use, style="Accent.TButton")
        self.apply_button.pack(side="right")
        ttk.Button(buttons, text=tr("取消"), command=self.close).pack(side="right", padx=6)
        self.source_notes = score.channels[(self.track, self.channel)].notes
        pitches=[note.pitch for note in self.source_notes] or [71,89]
        self.pitch_axis=max(0,min(pitches)-18),min(127,max(pitches)+18)
        self.starts = sorted({0, *(note.on for note in self.source_notes)})
        self.ends = sorted({self.end_of_track, *(note.on for note in self.source_notes), *(note.off for note in self.source_notes)})
        self.start_times = [float(score.tempo.at(tick)) for tick in self.starts]
        self.end_times = [float(score.tempo.at(tick)) for tick in self.ends]
        self.analysis = None
        stride=max(1,(len(self.source_notes)+2999)//3000)
        self.plot = self.source_notes[::stride]
        self.analyze(recenter=self.band_low is None)
        self.poll_id = self.window.after(100, self.poll)

    def exists(self):
        try: return bool(self.window.winfo_exists())
        except tk.TclError: return False

    def selected_policy(self):
        return self.choices[self.policy.get()]

    def analyze(self, recenter=False):
        if not self.exists(): return
        if recenter:
            self.band_low=engine.suggest_pitch_window(self.score,self.track,self.channel,
                self.start_tick,self.end_tick,self.band_low)
        self.band_low=max(self.pitch_axis[0],min(self.pitch_axis[1]-18,self.band_low))
        self.analysis = engine.selection_info(self.score, self.track, self.channel,
            self.start_tick, self.end_tick, self.selected_policy(),self.band_low,self.band_low+18)
        raw=[note for note in self.source_notes if note.off>self.start_tick and note.on<self.end_tick]
        inside=sum(self.band_low<=note.pitch<=self.band_low+18 for note in raw)
        self.inside_count,self.outside_count=inside,len(raw)-inside
        options = self.analysis["transpose_options"]
        span = self.analysis["range"]
        times = tr("%s — %s，时长 %s") % (clock_text(self.score.tempo.at(self.start_tick)),
            clock_text(self.score.tempo.at(self.end_tick)), clock_text(self.score.tempo.at(self.end_tick) - self.score.tempo.at(self.start_tick)))
        if not span:
            text = tr("框内没有音符，请上下拖动绿框，或调整左右时间范围。")
        elif self.analysis["notes"]>4096:
            text = tr("所选范围超过4096音，请缩小范围或自动找片段。")
            options = []
        elif not options:
            text = tr("音域 %s–%s（跨度%d半音），超过18；请缩小范围或改选取高/低音。") % (engine.note_name(span[0]), engine.note_name(span[1]), span[1] - span[0])
        else:
            shift = min(options, key=lambda value: (abs(value), value))
            text = tr("框内%d音，排除%d音；多音取舍后%d音，建议整体移调 %+d 半音。") % (inside,len(raw)-inside,self.analysis["notes"],shift)
        self.info.set(times + tr("；18半音框 %s–%s\n") % (engine.note_name(self.band_low),engine.note_name(self.band_low+18)) + text)
        self.apply_button.state(["!disabled"] if options else ["disabled"])
        self.draw()

    def x(self, us):
        width = max(1, self.canvas.winfo_width() - 48)
        return 32 + width * (float(us) - self.view[0]) / max(1, self.view[1] - self.view[0])

    def at_x(self, x):
        width = max(1, self.canvas.winfo_width() - 48)
        return min(self.total_us, max(0, self.view[0] + (x - 32) / width * (self.view[1] - self.view[0])))

    def y(self, pitch):
        lo,hi=self.pitch_axis
        return 18+(hi-pitch)*max(25,self.canvas.winfo_height()-70)/max(1,hi-lo)

    def band_edges(self):
        return self.y(self.band_low+18.5),self.y(self.band_low-.5)

    def draw(self):
        if not self.exists(): return
        c = self.canvas; c.delete("all")
        height = max(80, c.winfo_height())
        left,right=self.x(self.score.tempo.at(self.start_tick)),self.x(self.score.tempo.at(self.end_tick))
        top,bottom=self.band_edges()
        c.create_rectangle(left,top,right,bottom,fill="#18403b",outline="#4ed6b0",width=2,tags="pitch_band")
        for note in self.plot:
            on, off = self.score.tempo.at(note.on), self.score.tempo.at(note.off)
            if off < self.view[0] or on > self.view[1]: continue
            y = self.y(note.pitch)
            a,b=max(32,self.x(on)),min(c.winfo_width()-16,self.x(off))+1
            c.create_rectangle(a,y-2,b,y+2,fill="#536572",outline="",tags="source_note")
            if self.band_low<=note.pitch<=self.band_low+18 and note.off>self.start_tick and note.on<self.end_tick:
                c.create_rectangle(max(a,left),y-2,min(b,right),y+2,fill="#d8f7eb",outline="",tags="kept_note")
        for pitch,label_y in ((self.band_low,bottom+9),(self.band_low+18,top-9)):
            c.create_text(min(c.winfo_width()-18,max(90,right-10)),label_y,text=engine.note_name(pitch),
                anchor="e",fill="#71f0c7",tags="pitch_label")
        for tick, label in ((self.start_tick, tr("开始")), (self.end_tick, tr("结束"))):
            x = self.x(self.score.tempo.at(tick))
            c.create_rectangle(x-5, 0, x+5, height-22, fill="#3c9bdc", outline="", tags=label)
            c.create_text(x, height-12, text=label, fill="white", tags=label)
        for index in range(5):
            us = self.view[0] + (self.view[1] - self.view[0]) * index / 4
            c.create_text(self.x(us), height-27, text=clock_text(us), fill="#a9bacd",
                          anchor="w" if index==0 else "e" if index==4 else "center")
        x = self.x(self.cursor_us)
        c.create_line(x, 0, x, height-30, fill="#ffb14e", width=2)

    def snap(self, us, end=False):
        times, ticks = (self.end_times, self.ends) if end else (self.start_times, self.starts)
        index = bisect_left(times, us)
        choices = [i for i in (index-1, index) if 0 <= i < len(times)]
        closest=min(choices,key=lambda i:abs(times[i]-us))
        tolerance=(self.view[1]-self.view[0])*8/max(1,self.canvas.winfo_width()-48)
        if abs(times[closest]-us)<=tolerance: return ticks[closest]
        return min(self.end_of_track,max(0,round(self.score.tempo.tick_at_us(us))))

    def press(self, event):
        left, right = self.x(self.score.tempo.at(self.start_tick)), self.x(self.score.tempo.at(self.end_tick))
        top,bottom=self.band_edges()
        self.drag = ("start" if abs(event.x-left) <= 12 else "end" if abs(event.x-right) <= 12 else
                     "band" if left<event.x<right and top-7<=event.y<=bottom+7 else "cursor")
        self.band_press_y,self.band_press_low=event.y,self.band_low
        self.stop()
        self.motion(event)

    def motion(self, event):
        us = self.at_x(event.x)
        if self.drag == "start": self.start_tick = min(self.snap(us), self.end_tick-1)
        elif self.drag == "end": self.end_tick = max(self.start_tick+1, self.snap(us, True))
        elif self.drag == "cursor":
            self.cursor_us = us
            self.progress.set(us / 1000000)
        elif self.drag in ("band","pitch"):
            if self.drag=="pitch" or abs(event.y-self.band_press_y)>=3:
                self.drag="pitch"
                step=(self.pitch_axis[1]-self.pitch_axis[0])/max(25,self.canvas.winfo_height()-70)
                self.band_low=max(self.pitch_axis[0],min(self.pitch_axis[1]-18,
                    self.band_press_low+round((self.band_press_y-event.y)*step)))
        self.draw()

    def release(self, event):
        cursor = self.drag in ("cursor","band")
        recenter = self.drag in ("start","end")
        if self.drag=="band":
            self.cursor_us=self.at_x(event.x)
            self.progress.set(self.cursor_us/1000000)
        self.drag = None
        self.analyze(recenter=recenter)
        if cursor: self.play_cursor()

    def seek(self, value):
        if not self.updating_progress:
            self.cursor_us = float(value) * 1000000
            self.draw()

    def begin_seek(self, event=None):
        self.drag="scale"
        self.stop()

    def finish_seek(self, event=None):
        self.drag=None
        self.play_cursor()

    def play_cursor(self):
        end = float(self.score.tempo.at(self.end_tick))
        start = max(float(self.score.tempo.at(self.start_tick)), self.cursor_us)
        if start >= end: start = float(self.score.tempo.at(self.start_tick))
        self.cursor_us = start
        self.progress.set(start/1000000)
        start_ms = int(start/1000)
        # Keep a positive sub-millisecond selection from becoming an empty
        # range when handing it to the millisecond-only Windows player.
        end_ms = max(start_ms+1, ceil(end/1000))
        self.preview(self.selected_policy(), start_ms, end_ms,self.band_low,self.band_low+18)

    def play_selection(self):
        self.cursor_us = float(self.score.tempo.at(self.start_tick))
        self.play_cursor()

    def zoom(self):
        start, end = float(self.score.tempo.at(self.start_tick)), float(self.score.tempo.at(self.end_tick))
        pad = max(1000, (end-start)*.08)
        self.view = (max(0, start-pad), min(self.total_us, end+pad))
        self.draw()

    def full_view(self):
        self.view = (0, self.total_us); self.draw()

    def auto_band(self):
        self.stop()
        self.analyze(recenter=True)

    def auto_range(self):
        self.stop()
        self.start_tick, self.end_tick, policy = engine.suggest_range(self.score, self.track, self.channel, self.selected_policy())
        self.policy.set(next(label for label, value in self.choices.items() if value == policy))
        self.cursor_us = float(self.score.tempo.at(self.start_tick))
        self.progress.set(self.cursor_us/1000000)
        self.analyze(recenter=True); self.zoom()

    def use(self):
        if not self.analysis or not self.analysis["transpose_options"]: return
        self.apply_callback(self.start_tick, self.end_tick, self.policy.get(), self.analysis["transpose_options"],
                            self.band_low,self.band_low+18)
        self.close()

    def poll(self):
        if not self.exists(): return
        try: position = self.position()
        except (RuntimeError, ValueError): position = None
        if position is not None and self.drag is None:
            self.cursor_us = position * 1000
            self.updating_progress = True; self.progress.set(position/1000); self.updating_progress = False
            self.draw()
        self.poll_id = self.window.after(100, self.poll)

    def close(self):
        if self.exists():
            self.window.after_cancel(self.poll_id)
            self.stop()
            self.window.destroy()
