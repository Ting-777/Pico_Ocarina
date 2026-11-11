"""Chinese desktop interface for the existing MIDI converter."""
import importlib
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import midi_to_melody as engine
import midi_gui_model as model
from midi_gui_audio import MidiPlayer

ROOT = engine.ROOT
PRIVATE_DEPS = ROOT / ".deps/python"
POLYPHONY = {"遇到同时多音时提示": "error", "仅八度叠音取高音": "octave-highest"}
OVERLAP = {"遇到重叠时提示": "error", "缩短前音，留出40ms松键": "trim"}

class ConverterWindow:
    def __init__(self, root):
        self.root = root
        self.score = None
        self.rows = {}
        self.result = None
        self.busy = False
        self.closing = False
        self.updating = False
        self.events = queue.Queue()
        self.controls = []
        self.player = MidiPlayer()
        self.preview_directory = tempfile.TemporaryDirectory(prefix="pico-ocarina-")
        self.file = tk.StringVar(value="先打开一个MIDI文件，或用右侧示例试一次")
        self.title = tk.StringVar()
        self.transpose = tk.StringVar(value="0")
        self.speed = tk.StringVar(value="100")
        self.countdown = tk.StringVar(value="3")
        self.start = tk.StringVar()
        self.end = tk.StringVar()
        self.polyphony = tk.StringVar(value=next(iter(POLYPHONY)))
        self.overlap = tk.StringVar(value=next(iter(OVERLAP)))
        self.ignore_expression = tk.BooleanVar(value=False)
        self.folder = tk.StringVar(value=str(ROOT / "out/gui"))
        self.filename = tk.StringVar(value="my_song")
        self.hint = tk.StringVar(value="选中一行，再试听，确认它是你要的主旋律。轨道和通道编号从0开始。")
        self.result_text = tk.StringVar(value="完成选择后，点击“生成歌曲文件”。")
        self.status = tk.StringVar(value="就绪")
        self.audio_status = tk.StringVar()
        self._build()
        for variable in (self.title, self.transpose, self.speed, self.countdown, self.start, self.end,
                         self.polyphony, self.overlap, self.ignore_expression, self.folder, self.filename):
            variable.trace_add("write", self._changed)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.report_callback_exception = self._callback_error
        self._poll_id = self.root.after(80, self._poll)
        self._refresh()

    def _build(self):
        root = self.root
        root.title("Pico 陶笛 · MIDI 转换器")
        root.configure(background="#f3f6fa")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background="#f3f6fa")
        style.configure("TLabel", background="#f3f6fa", foreground="#213547")
        style.configure("Card.TFrame", background="white")
        style.configure("Card.TLabel", background="white")
        style.configure("Card.TCheckbutton", background="white")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"), foreground="#173b48")
        style.configure("Section.TLabel", background="white", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Hint.TLabel", foreground="#617582", font=("Microsoft YaHei UI", 9))
        style.configure("TButton", padding=(10, 5))
        style.configure("TNotebook.Tab", padding=(13, 6))
        style.configure("Accent.TButton", background="#167b80", foreground="white", font=("Microsoft YaHei UI", 11, "bold"), padding=(12, 9))
        style.map("Accent.TButton", background=[("disabled", "#91a9ad"), ("active", "#106268")])
        style.configure("Treeview", rowheight=28, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"), padding=(3, 6))
        style.map("Treeview", background=[("selected", "#d8eeef")], foreground=[("selected", "#123f45")])

        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="MIDI 转成陶笛歌曲", style="Title.TLabel").pack(side="left")
        self.full_button = self._button(header, "试用完整版", lambda: self.load_demo("full"))
        self.full_button.pack(side="right")
        self.first_button = self._button(header, "试用短版", lambda: self.load_demo("first"))
        self.first_button.pack(side="right", padx=7)
        self.open_button = self._button(header, "打开 MIDI…", self.choose_file)
        self.open_button.pack(side="right")
        ttk.Label(outer, textvariable=self.file, width=1, anchor="w",
                  style="Hint.TLabel").grid(row=1, column=0, sticky="ew", pady=(6, 10))

        body = ttk.Frame(outer)
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3, minsize=490)
        body.columnconfigure(1, weight=2, minsize=370)
        body.rowconfigure(0, weight=1)
        self.left = ttk.Frame(body)
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.left.columnconfigure(0, weight=1)
        self.left.rowconfigure(0, weight=1)
        self.right = ttk.Frame(body)
        self.right.grid(row=0, column=1, sticky="nsew")
        self.right.columnconfigure(0, weight=1)
        self.right.rowconfigure(0, weight=1)

        tracks = ttk.Frame(self.left, style="Card.TFrame", padding=8)
        tracks.grid(row=0, column=0, sticky="nsew")
        tracks.columnconfigure(0, weight=1)
        tracks.rowconfigure(1, weight=1)
        ttk.Label(tracks, text="1  选择主旋律", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 7))
        columns = ("track", "channel", "name", "notes", "range", "state")
        self.tree = ttk.Treeview(tracks, columns=columns, show="headings", selectmode="browse", height=5)
        for key, label, width, minimum in zip(columns,
                ("轨道", "通道", "轨道名称", "音符数", "音域", "检查"),
                (44, 44, 150, 56, 85, 160), (40, 40, 85, 50, 80, 90)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=minimum,
                             stretch=key in ("name", "state"),
                             anchor="w" if key in ("name", "state") else "center")
        self.tree.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(tracks, orient="vertical", command=self.tree.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        hscroll = ttk.Scrollbar(tracks, orient="horizontal", command=self.tree.xview)
        hscroll.grid(row=2, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=hscroll.set)
        self.tree.tag_configure("problem", foreground="#a65c18")
        self.tree.bind("<Button-1>", lambda event: "break" if self.busy else None)
        self.tree.bind("<Key>", lambda event: "break" if self.busy else None)
        self.tree.bind("<<TreeviewSelect>>", self._selected)
        self.tree.bind("<Double-1>", lambda event: self.audition())
        bottom = ttk.Frame(tracks, style="Card.TFrame")
        bottom.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.audition_button = self._button(bottom, "试听原轨", self.audition)
        self.audition_button.pack(side="left")
        self.stop_button = ttk.Button(bottom, text="停止试听", command=self.stop_audio)
        self.stop_button.pack(side="left", padx=6)
        ttk.Label(bottom, textvariable=self.audio_status, width=1,
                  style="Card.TLabel").pack(side="left", fill="x", expand=True, padx=5)
        self.hint_label = ttk.Label(tracks, textvariable=self.hint, style="Card.TLabel",
                                   width=1, wraplength=550, justify="left", anchor="nw")
        self.hint_label.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        result = ttk.Frame(self.left, style="Card.TFrame", padding=8)
        result.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        result.columnconfigure(0, weight=1)
        ttk.Label(result, text="3  转换结果", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.result_label = ttk.Label(result, textvariable=self.result_text, width=1,
                                     wraplength=550, justify="left", style="Card.TLabel")
        self.result_label.grid(row=1, column=0, sticky="ew", pady=(5, 8))
        actions = ttk.Frame(result, style="Card.TFrame")
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure((0, 1), weight=1, uniform="actions")
        self.preview_button = self._button(actions, "试听转换结果", self.preview_result)
        self.preview_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.folder_button = self._button(actions, "打开输出文件夹", self.open_folder)
        self.folder_button.grid(row=0, column=1, sticky="ew")
        self.copy_button = self._button(actions, "复制 JSON 路径", self.copy_result)
        self.copy_button.grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(5, 0))
        self.report_button = self._button(actions, "查看处理报告", self.open_report)
        self.report_button.grid(row=1, column=1, sticky="ew", pady=(5, 0))

        self.settings_tabs = ttk.Notebook(self.right)
        self.settings_tabs.grid(row=0, column=0, sticky="nsew")
        self.basic = ttk.Frame(self.settings_tabs, padding=10, style="Card.TFrame")
        self.advanced = ttk.Frame(self.settings_tabs, padding=10, style="Card.TFrame")
        self.settings_tabs.add(self.basic, text="2  调整歌曲")
        self.settings_tabs.add(self.advanced, text="片段与多音")
        basic = self.basic
        basic.columnconfigure((0, 1, 2), weight=1, uniform="fields")
        ttk.Label(basic, text="歌曲名称", style="Card.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        self._entry(basic, self.title, 1).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 12))
        for column, label, variable in ((0, "移调 / 半音", self.transpose),
                                        (1, "速度 / %", self.speed),
                                        (2, "倒数 / 秒", self.countdown)):
            ttk.Label(basic, text=label, style="Card.TLabel").grid(row=2, column=column, sticky="w", padx=(0, 6))
            self._entry(basic, variable, 5).grid(row=3, column=column, sticky="ew", padx=(0, 6), pady=(4, 0))
        ttk.Label(basic, text="移调 0 = 原调；+5 = 升5半音。\n速度 80% 更慢。不会自动折八度。",
                  style="Card.TLabel", justify="left").grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        advanced = self.advanced
        advanced.columnconfigure((0, 1), weight=1)
        for column, label, variable in ((0, "开始拍点", self.start), (1, "结束拍点", self.end)):
            ttk.Label(advanced, text=label, style="Card.TLabel").grid(row=0, column=column, sticky="w")
            self._entry(advanced, variable, 8).grid(row=1, column=column, sticky="ew", padx=(0, 6), pady=(3, 0))
        ttk.Label(advanced, text="留空为整轨；四分音符从0计数，非小节号。",
                  style="Card.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 9))
        ttk.Label(advanced, text="同时多音", style="Card.TLabel").grid(row=3, column=0, sticky="w")
        self._combo(advanced, self.polyphony, list(POLYPHONY), 21).grid(row=3, column=1, sticky="ew", pady=(0, 7))
        ttk.Label(advanced, text="连奏重叠", style="Card.TLabel").grid(row=4, column=0, sticky="w")
        self._combo(advanced, self.overlap, list(OVERLAP), 21).grid(row=4, column=1, sticky="ew")
        expressive = ttk.Checkbutton(advanced, text="忽略弯音 / 延音踏板（舍弃原效果）",
                                    variable=self.ignore_expression, style="Card.TCheckbutton")
        expressive.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.controls.append(expressive)

        save = ttk.Frame(self.right, padding=10, style="Card.TFrame")
        save.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        save.columnconfigure(1, weight=1)
        ttk.Label(save, text="保存到", style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._entry(save, self.folder, 1).grid(row=0, column=1, sticky="ew")
        self._button(save, "浏览…", self.choose_folder).grid(row=0, column=2, sticky="e", padx=(6, 0))
        ttk.Label(save, text="文件名", style="Card.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self._entry(save, self.filename, 1).grid(row=1, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(save, text="同时保存 JSON、试听 MIDI 和报告", style="Card.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.generate_button = self._button(self.right, "生成歌曲文件", self.generate, style="Accent.TButton")
        self.generate_button.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.grid(row=3, column=0, sticky="ew", pady=(10, 5))
        footer = ttk.Frame(outer)
        footer.grid(row=4, column=0, sticky="ew")
        self.install_button = ttk.Button(footer, text="安装转换组件", command=self.install_dependency)
        ttk.Label(footer, textvariable=self.status, width=1, style="Hint.TLabel").pack(side="left", fill="x", expand=True)
        try:
            engine.require_mido()
        except Exception:
            self.install_button.pack(side="right")
            self.status.set("首次使用：点击“安装转换组件”，组件只安装到本工程文件夹。")

        # Labels follow the available column width rather than enlarging the window.
        def wrap_left(event):
            width = max(220, event.width - 24)
            self.hint_label.configure(wraplength=width)
            self.result_label.configure(wraplength=width)
        self.left.bind("<Configure>", wrap_left)
        self._fit_window()

    def _fit_window(self):
        """Fit the client area inside the desktop work area, including taskbar space."""
        root = self.root
        left, top = 0, 0
        width, height = root.winfo_screenwidth(), root.winfo_screenheight()
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            area = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(area), 0):
                left, top = area.left, area.top
                width, height = area.right - left, area.bottom - top
        client_width = min(1180, width - 40)
        client_height = min(680, height - 72)
        root.minsize(min(940, client_width), min(580, client_height))
        x = left + (width - client_width) // 2
        y = top + max(0, (height - client_height - 40) // 2)
        root.geometry("%dx%d+%d+%d" % (client_width, client_height, x, y))

    def _button(self, parent, text, command, **kwargs):
        widget=ttk.Button(parent,text=text,command=command,**kwargs)
        self.controls.append(widget)
        return widget

    def _entry(self, parent, variable, width):
        widget=ttk.Entry(parent,textvariable=variable,width=width)
        self.controls.append(widget)
        return widget

    def _combo(self, parent, variable, values, width):
        widget=ttk.Combobox(parent,textvariable=variable,values=values,width=width,state="readonly")
        self.controls.append(widget)
        return widget

    def selection(self):
        selected=self.tree.selection()
        return self.rows.get(selected[0]) if selected else None

    def _refresh(self):
        for control in self.controls:
            control.state(["disabled"] if self.busy else ["!disabled"])
        row=self.selection()
        valid=not self.busy and self.score is not None and row is not None and not row["drum_channel"] and not row["errors"]
        self.generate_button.state(["!disabled"] if valid else ["disabled"])
        self.audition_button.state(["!disabled"] if valid else ["disabled"])
        for button in (self.preview_button,self.folder_button,self.copy_button,self.report_button):
            button.state(["!disabled"] if self.result and not self.busy else ["disabled"])
        self.install_button.state(["disabled"] if self.busy else ["!disabled"])
        self.tree.state(["disabled"] if self.busy else ["!disabled"])
        self.stop_button.state(["!disabled"] if self.player.opened else ["disabled"])

    def _changed(self, *args):
        if self.updating or self.busy:
            return
        if self.result:
            self.result=None
            self.result_text.set("参数已改动，请重新生成；已保存的文件仍在原位置。")
        self._refresh()

    def _selected(self, event=None):
        if self.busy or not self.score:
            return
        row=self.selection()
        if not row:
            self._refresh()
            return
        self.stop_audio()
        self.result=None
        self.result_text.set("已选择轨道 %d / 通道 %d，试听后确认主旋律。" % (row["track"],row["channel"]))
        options=row["transpose_options"]
        shift="整轨可移调：" + (("、".join("%+d" % n for n in options)) if options else "整轨音域太宽，可尝试截取片段")
        problems=[]
        if row["drum_channel"]: problems.append("GM鼓通道，不能作为陶笛旋律")
        if row["errors"]: problems.append("音符配对异常")
        if row["simultaneous_groups"]: problems.append("%d处同时多音，需要明确处理" % row["simultaneous_groups"])
        self.hint.set("；".join(problems+[shift])+"。片段的可用范围以生成时检查为准。")
        self.updating=True
        self.filename.set(self.score.source.stem[:48]+"_t%d_c%d"%(row["track"],row["channel"]))
        self.updating=False
        self._refresh()

    def _run(self, label, work, done):
        if self.busy:
            return
        self.busy=True
        self.status.set(label)
        self.progress.start(12)
        self._refresh()
        def worker():
            try:
                self.events.put((done,work(),None))
            except Exception as error:
                self.events.put((done,None,error))
        threading.Thread(target=worker,daemon=True).start()

    def _poll(self):
        try:
            done,result,error=self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy=False
            self.progress.stop()
            if error:
                self.status.set("未完成，请按提示调整后重试。")
                if self.score is None:
                    self.result_text.set("未能读取文件，请重新选择 MIDI。")
                if not self.closing:
                    messagebox.showerror("需要调整",str(error),parent=self.root)
            else:
                try:
                    done(result)
                except Exception as callback_error:
                    self._callback_error(type(callback_error), callback_error, callback_error.__traceback__)
            self._refresh()
            if self.closing:
                self._destroy()
                return
        if self.player.opened:
            if not self.player.playing():
                self.audio_status.set("试听结束")
                self._refresh()
        self._poll_id = self.root.after(100,self._poll)

    def choose_file(self):
        filename=filedialog.askopenfilename(parent=self.root,title="选择 MIDI 文件",
            filetypes=[("MIDI 文件","*.mid *.midi"),("所有文件","*.*")])
        if filename:
            self.load_file(filename)

    def load_demo(self, variant):
        source,digest,recipe=model.demo(variant)
        self.load_file(source,(variant,digest,recipe))

    def load_file(self, filename, preset=None):
        if self.busy:
            return
        self.stop_audio()
        self.score=None
        self.result=None
        self.rows={}
        self.tree.delete(*self.tree.get_children())
        self.file.set(str(filename))
        self.result_text.set("正在读取文件…")
        def read():
            score=engine.read_score(filename)
            if preset and score.sha256!=preset[1]:
                raise ValueError("示例MIDI已改变，无法套用已核验的示例设置")
            return score,engine.inspect_score(score)
        def loaded(value):
            self.score,inspection=value
            for row in inspection["candidates"]:
                iid="%d:%d"%(row["track"],row["channel"])
                self.rows[iid]=row
                pitches=row["range"]
                span=engine.note_name(pitches[0])+"–"+engine.note_name(pitches[1]) if pitches else "—"
                state=("鼓通道" if row["drum_channel"] else "配对异常" if row["errors"] else
                       "%d处同时多音"%row["simultaneous_groups"] if row["simultaneous_groups"] else "单音候选")
                self.tree.insert("", "end", iid=iid, values=(row["track"],row["channel"],row["name"],row["notes"],span,state),
                                 tags=("problem",) if row["errors"] or row["drum_channel"] else ())
            self.updating=True
            self.title.set(self.score.source.stem[:80])
            self.transpose.set("0"); self.speed.set("100"); self.countdown.set("3")
            self.start.set(""); self.end.set("")
            self.polyphony.set(next(iter(POLYPHONY))); self.overlap.set(next(iter(OVERLAP)))
            self.ignore_expression.set(False)
            self.updating=False
            self.hint.set("选中一行，再试听，确认它是你要的主旋律。轨道和通道编号从0开始。")
            self.result_text.set("读取完成，请选择一条旋律。")
            self.status.set("读取完成：%d个轨道/通道候选。" % len(self.rows))
            if preset:
                recipe=preset[2]
                iid="%d:%d"%(recipe["track"],recipe["channel"])
                self.tree.selection_set(iid); self.tree.see(iid)
                # Consume the queued selection event before applying preset fields.
                self.root.after_idle(lambda: self.apply_preset(preset[0],recipe))
        self._run("正在读取并检查 MIDI…",read,loaded)

    def apply_preset(self, variant, recipe):
        if self.busy or not self.score:
            return
        self._selected()
        form=model.form_for_demo(self.score,recipe)
        self.updating=True
        for var,value in ((self.title,form.title),(self.transpose,form.transpose),(self.speed,form.speed_percent),
                          (self.countdown,form.countdown_seconds),(self.start,form.start_beat),(self.end,form.end_beat)):
            var.set(value)
        self.polyphony.set(next(k for k,v in POLYPHONY.items() if v==form.polyphony))
        self.overlap.set(next(k for k,v in OVERLAP.items() if v==form.overlap))
        self.filename.set("queens_"+variant)
        self.updating=False
        self.result_text.set("示例设置已载入：整体升5半音，已明确选择八度叠音处理。点击“生成歌曲文件”即可。")
        self.status.set("已载入《皇后大道东》"+("短版" if variant=="first" else "完整版")+"。")
        self._refresh()

    def get_form(self):
        return model.Form(self.title.get(),self.transpose.get(),self.speed.get(),self.countdown.get(),
            self.start.get(),self.end.get(),POLYPHONY[self.polyphony.get()],OVERLAP[self.overlap.get()],self.ignore_expression.get())

    def generate(self):
        row=self.selection()
        if self.busy or not self.score or not row:
            return
        try:
            form=self.get_form()
            # Validate numbers before any file dialog or write.
            model.settings(self.score,row["track"],row["channel"],form)
            output=model.output_path(self.folder.get(),self.filename.get())
            existing=[file.name for file in model.output_files(output) if file.exists()]
            if existing and not messagebox.askyesno("替换已有文件？","将替换：\n"+"\n".join(existing)+"\n\n是否继续？",parent=self.root):
                return
        except Exception as error:
            messagebox.showerror("请检查设置",str(error),parent=self.root)
            return
        self.stop_audio()
        self.result=None
        score=self.score
        def convert():
            document,report=model.convert(score,row["track"],row["channel"],form)
            paths=engine.emit_conversion(score.source,document,report,output,force=bool(existing))
            return paths,document,report
        def complete(value):
            paths,document,report=value
            self.result=paths
            self.result_text.set(model.summary(document,report))
            self.status.set("已保存："+str(paths[0]))
        self._run("正在校验并生成歌曲、试听和处理报告…",convert,complete)

    def audition(self):
        row=self.selection()
        if self.busy or not self.score or not row or row["errors"] or row["drum_channel"]:
            return
        self.stop_audio()
        score=self.score
        def build():
            file=Path(self.preview_directory.name)/"original.mid"
            file.write_bytes(engine.audition_bytes(score,row["track"],row["channel"]))
            first=score.channels[(row["track"],row["channel"])].notes[0].on
            return file,int(score.tempo.at(first)/1000)
        self._run("正在准备原轨试听…",build,lambda value:self._play(value[0],value[1],"正在试听原轨（原音高，从首音开始）"))

    def preview_result(self):
        if self.result and not self.busy:
            self._play(self.result[1],0,"正在试听转换结果")

    def _play(self, file, start_ms, label):
        try:
            self.player.play(file,start_ms)
            self.audio_status.set(label)
            self.status.set(label)
        except Exception as error:
            self.audio_status.set("本机试听不可用")
            messagebox.showerror("试听未启动",str(error),parent=self.root)
        self._refresh()

    def stop_audio(self):
        try:
            self.player.stop()
        except RuntimeError:
            pass
        self.audio_status.set("")
        self._refresh()

    def choose_folder(self):
        value=filedialog.askdirectory(parent=self.root,initialdir=self.folder.get() if Path(self.folder.get()).is_dir() else ROOT,title="选择保存文件夹")
        if value:
            self.folder.set(value)

    def toggle_advanced(self):
        self.settings_tabs.select(self.advanced)

    def _open(self, file):
        try:
            if os.name!="nt":
                raise RuntimeError("文件位于："+str(file))
            os.startfile(str(file))
        except (OSError, RuntimeError) as error:
            messagebox.showerror("无法打开",str(error),parent=self.root)

    def open_folder(self):
        if self.result:
            self._open(self.result[0].parent)

    def open_report(self):
        if self.result:
            self._open(self.result[2])

    def copy_result(self):
        if self.result:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(self.result[0]))
            self.status.set("已复制 JSON 路径。")

    def install_dependency(self):
        if self.busy:
            return
        def install():
            PRIVATE_DEPS.mkdir(parents=True,exist_ok=True)
            completed=subprocess.run([sys.executable,"-m","pip","install","--target",str(PRIVATE_DEPS),
                "--upgrade","-r",str(ROOT/"tools/requirements-midi.txt"),"--disable-pip-version-check"],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors="replace",
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if completed.returncode:
                raise RuntimeError("组件安装未完成，请检查网络后重试。\n"+completed.stdout[-1800:])
            return True
        def installed(result):
            if str(PRIVATE_DEPS) not in sys.path:
                sys.path.insert(0,str(PRIVATE_DEPS))
            importlib.invalidate_caches()
            engine.require_mido()
            self.install_button.pack_forget()
            self.status.set("组件已安装，可以打开 MIDI 或试用示例。")
        self._run("正在安装转换组件到本工程（需要联网）…",install,installed)

    def _callback_error(self, kind, error, tb):
        folder=ROOT/"out/gui"
        folder.mkdir(parents=True,exist_ok=True)
        (folder/"gui_error.log").write_text("".join(traceback.format_exception(kind,error,tb)),encoding="utf-8")
        if not self.closing:
            messagebox.showerror("窗口遇到问题",str(error)+"\n详情已保存到 out/gui/gui_error.log",parent=self.root)

    def close(self):
        if self.busy:
            self.closing=True
            self.status.set("正在完成当前文件操作，随后自动关闭…")
        else:
            self._destroy()

    def _destroy(self):
        self.root.after_cancel(self._poll_id)
        self.stop_audio()
        self.preview_directory.cleanup()
        self.root.destroy()

def main():
    root=tk.Tk()
    ConverterWindow(root)
    root.mainloop()

if __name__=="__main__":
    main()
