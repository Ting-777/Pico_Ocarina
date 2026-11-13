"""Desktop song manager for the MIDI converter and Pico uploader."""
from i18n import tr, LANGUAGES, get_language, set_language, ui_font, localized_combo
import importlib
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import traceback
from fractions import Fraction
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import midi_to_melody as engine
import midi_gui_model as model
import midi_gui_device as device
from midi_gui_audio import MidiPlayer
from midi_gui_range import RangeDialog
from melody_format import preview_bytes

ROOT = engine.ROOT
PRIVATE_DEPS = ROOT / ".deps/python"
POLYPHONY = {"遇到同时多音时提示": "error", "全部取最高音": "highest",
             "全部取最低音": "lowest", "仅八度叠音取高音": "octave-highest"}
OVERLAP = {"遇到重叠时提示": "error", "缩短前音，留出40ms松键": "trim"}

class ConverterWindow:
    def __init__(self, root):
        self.root = root
        self.score = None
        self.rows = {}
        self.result = None
        self.range_dialog = None
        self.recovery_dialog = None
        self._range_cache = None
        self._range_offset_ms = 0
        self._range_pending = None
        self._audio_generation = 0
        self.valid_notes_only = False
        self.operation = None
        self.song = None
        self.song_kind = None
        self.uploading = False
        self.loading_song = False
        self.port_choices = {}
        self.busy = False
        self.closing = False
        self.updating = False
        self._rebuilding_language = False
        self.events = queue.Queue()
        self.controls = []
        self.player = MidiPlayer()
        self.preview_directory = tempfile.TemporaryDirectory(prefix="pico-ocarina-")
        self.file = tk.StringVar(value=tr("打开 MIDI 进行转换，或加载已有 JSON 后直接上传。"))
        self.port = tk.StringVar()
        self.upload_status = tk.StringVar(value=tr("先加载 JSON，或生成歌曲文件，再选择串口上传。"))
        self.title = tk.StringVar()
        self.transpose = tk.StringVar(value="0")
        self.speed = tk.StringVar(value="100")
        self.countdown = tk.StringVar(value="3")
        self.start = tk.StringVar()
        self.end = tk.StringVar()
        self.pitch_min = tk.StringVar()
        self.pitch_max = tk.StringVar()
        self.pitch_hint = tk.StringVar(value=tr("空拍点 = 整轨"))
        self.polyphony = tk.StringVar(value=next(iter(POLYPHONY)))
        self.overlap = tk.StringVar(value=next(iter(OVERLAP)))
        self.ignore_expression = tk.BooleanVar(value=False)
        self.folder = tk.StringVar(value=str(ROOT / "out/gui"))
        self.filename = tk.StringVar(value="my_song")
        self.hint = tk.StringVar(value=tr("选中一行，再试听，确认它是你要的主旋律。轨道和通道编号从0开始。"))
        self.result_text = tk.StringVar(value=tr("完成选择后，点击“生成歌曲文件”。"))
        self.status = tk.StringVar(value=tr("就绪"))
        self.audio_status = tk.StringVar()
        self._build()
        for variable in (self.title, self.transpose, self.speed, self.countdown, self.start, self.end,
                         self.polyphony, self.overlap, self.ignore_expression, self.folder, self.filename,
                         self.pitch_min,self.pitch_max):
            variable.trace_add("write", self._changed)
        self.port.trace_add("write", self._port_changed)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.report_callback_exception = self._callback_error
        self._poll_id = self.root.after(80, self._poll)
        self._refresh()

    def _build(self):
        root = self.root
        root.title(tr("Pico 陶笛 · 歌曲管理器"))
        root.tk.call("::msgcat::mclocale", "zh_cn" if get_language() == "zh_CN" else get_language())
        root.configure(background="#f3f6fa")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=(ui_font(), 10))
        style.configure("TFrame", background="#f3f6fa")
        style.configure("TLabel", background="#f3f6fa", foreground="#213547")
        style.configure("Card.TFrame", background="white")
        style.configure("Card.TLabel", background="white")
        style.configure("Card.TCheckbutton", background="white")
        style.configure("Title.TLabel", font=(ui_font(), 18, "bold"), foreground="#173b48")
        style.configure("Section.TLabel", background="white", font=(ui_font(), 10, "bold"))
        style.configure("Hint.TLabel", foreground="#617582", font=(ui_font(), 9))
        style.configure("TButton", padding=(10, 5))
        style.configure("TNotebook.Tab", padding=(13, 6))
        style.configure("Accent.TButton", background="#167b80", foreground="white", font=(ui_font(), 11, "bold"), padding=(12, 9))
        style.map("Accent.TButton", background=[("disabled", "#91a9ad"), ("active", "#106268")])
        style.configure("Treeview", rowheight=28, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=(ui_font(), 9, "bold"), padding=(3, 6))
        style.map("Treeview", background=[("selected", "#d8eeef")], foreground=[("selected", "#123f45")])

        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text=tr("陶笛歌曲 · 转换与上传"), style="Title.TLabel").pack(side="left")
        self.open_button = self._button(header, tr("打开 MIDI…"), self.choose_file)
        self.open_button.pack(side="right")
        self.json_button = self._button(header, tr("加载 JSON…"), self.choose_json)
        self.json_button.pack(side="right", padx=7)
        self.language = tk.StringVar(value=LANGUAGES[get_language()])
        self.language_combo = ttk.Combobox(header, textvariable=self.language,
            values=list(LANGUAGES.values()), state="readonly", width=11)
        self.language_combo.pack(side="right", padx=(8, 12))
        self.language_combo.bind("<<ComboboxSelected>>", self._change_language)
        self.controls.append(self.language_combo)
        # Keep the selector discoverable regardless of the current UI language.
        ttk.Label(header, text="Language", style="Hint.TLabel").pack(side="right")
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
        ttk.Label(tracks, text=tr("选择主旋律"), style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 7))
        columns = ("track", "channel", "name", "notes", "range", "state")
        self.tree = ttk.Treeview(tracks, columns=columns, show="headings", selectmode="browse", height=5)
        for key, label, width, minimum in zip(columns,
                (tr("轨道"), tr("通道"), tr("轨道名称"), tr("音符数"), tr("音域"), tr("检查")),
                (52, 68, 150, 56, 85, 160), (48, 64, 85, 50, 80, 90)):
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
        self.audition_button = self._button(bottom, tr("试听原轨"), self.audition)
        self.audition_button.pack(side="left")
        self.range_button = self._button(bottom, tr("拖动选择片段…"), self.open_range)
        self.range_button.pack(side="left", padx=6)
        self.stop_button = ttk.Button(bottom, text=tr("停止试听"), command=self.stop_audio)
        self.stop_button.pack(side="left", padx=6)
        ttk.Label(bottom, textvariable=self.audio_status, width=1,
                  style="Card.TLabel").pack(side="left", fill="x", expand=True, padx=5)
        self.hint_label = ttk.Label(tracks, textvariable=self.hint, style="Card.TLabel",
                                   width=1, wraplength=550, justify="left", anchor="nw")
        self.hint_label.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        result = ttk.Frame(self.left, style="Card.TFrame", padding=8)
        result.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        result.columnconfigure(0, weight=1)
        ttk.Label(result, text=tr("当前歌曲"), style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.result_label = ttk.Label(result, textvariable=self.result_text, width=1,
                                     wraplength=550, justify="left", style="Card.TLabel")
        self.result_label.grid(row=1, column=0, sticky="ew", pady=(5, 8))
        actions = ttk.Frame(result, style="Card.TFrame")
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure((0, 1), weight=1, uniform="actions")
        self.preview_button = self._button(actions, tr("试听当前歌曲"), self.preview_result)
        self.preview_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.folder_button = self._button(actions, tr("打开输出文件夹"), self.open_folder)
        self.folder_button.grid(row=0, column=1, sticky="ew")
        self.copy_button = self._button(actions, tr("复制 JSON 路径"), self.copy_result)
        self.copy_button.grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(5, 0))
        self.report_button = self._button(actions, tr("查看处理报告"), self.open_report)
        self.report_button.grid(row=1, column=1, sticky="ew", pady=(5, 0))

        midi_controls_start = len(self.controls)
        self.settings_tabs = ttk.Notebook(self.right)
        self.settings_tabs.grid(row=0, column=0, sticky="nsew")
        self.basic = ttk.Frame(self.settings_tabs, padding=10, style="Card.TFrame")
        self.advanced = ttk.Frame(self.settings_tabs, padding=10, style="Card.TFrame")
        self.settings_tabs.add(self.basic, text=tr("调整歌曲"))
        self.settings_tabs.add(self.advanced, text=tr("片段与多音"))
        basic = self.basic
        basic.columnconfigure((0, 1, 2), weight=1, uniform="fields")
        ttk.Label(basic, text=tr("歌曲名称"), style="Card.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        self._entry(basic, self.title, 1).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 12))
        for column, label, variable in ((0, tr("移调 / 半音"), self.transpose),
                                        (1, tr("速度 / %"), self.speed),
                                        (2, tr("倒数 / 秒"), self.countdown)):
            ttk.Label(basic, text=label, style="Card.TLabel").grid(row=2, column=column, sticky="w", padx=(0, 6))
            self._entry(basic, variable, 5).grid(row=3, column=column, sticky="ew", padx=(0, 6), pady=(4, 0))
        timing_hint = ttk.Label(basic, text=tr("移调 +5 = 升5半音；速度80%更慢。\n音间隔至少120毫秒，保持音长并顺延。"),
                  style="Card.TLabel", justify="left", width=1, wraplength=330)
        timing_hint.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        basic.bind("<Configure>", lambda event: timing_hint.configure(wraplength=max(200, event.width - 24)))

        advanced = self.advanced
        advanced.columnconfigure((0, 1), weight=1)
        for column, label, variable in ((0, tr("开始拍点"), self.start), (1, tr("结束拍点"), self.end)):
            ttk.Label(advanced, text=label, style="Card.TLabel").grid(row=0, column=column, sticky="w")
            self._entry(advanced, variable, 8).grid(row=1, column=column, sticky="ew", padx=(0, 6), pady=(3, 0))
        band_status=ttk.Frame(advanced,style="Card.TFrame")
        band_status.grid(row=2,column=0,columnspan=2,sticky="ew",pady=(5,9))
        band_status.columnconfigure(0,weight=1)
        ttk.Label(band_status,textvariable=self.pitch_hint,style="Card.TLabel").grid(row=0,column=0,sticky="w")
        self.clear_pitch_button=self._button(band_status,tr("取消音域框"),self.clear_pitch_filter)
        self.clear_pitch_button.grid(row=0,column=1,sticky="e")
        ttk.Label(advanced, text=tr("同时多音"), style="Card.TLabel").grid(row=3, column=0, sticky="w")
        self._combo(advanced, self.polyphony, list(POLYPHONY), 21).grid(row=3, column=1, sticky="ew", pady=(0, 7))
        ttk.Label(advanced, text=tr("连奏重叠"), style="Card.TLabel").grid(row=4, column=0, sticky="w")
        self._combo(advanced, self.overlap, list(OVERLAP), 21).grid(row=4, column=1, sticky="ew")
        expressive = ttk.Checkbutton(advanced, text=tr("忽略弯音 / 延音踏板（舍弃原效果）"),
                                    variable=self.ignore_expression, style="Card.TCheckbutton")
        expressive.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.controls.append(expressive)

        save = ttk.Frame(self.right, padding=10, style="Card.TFrame")
        self.save_panel = save
        save.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        save.columnconfigure(1, weight=1)
        ttk.Label(save, text=tr("保存到"), style="Section.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self._entry(save, self.folder, 1).grid(row=0, column=1, sticky="ew")
        self._button(save, tr("浏览…"), self.choose_folder).grid(row=0, column=2, sticky="e", padx=(6, 0))
        ttk.Label(save, text=tr("文件名"), style="Card.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self._entry(save, self.filename, 1).grid(row=1, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(save, text=tr("同时保存 JSON、试听 MIDI 和报告"), style="Card.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.generate_button = self._button(self.right, tr("生成歌曲文件"), self.generate, style="Accent.TButton")
        self.generate_button.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.midi_controls = self.controls[midi_controls_start:]
        self._build_upload_panel()
        self.settings_tabs.bind("<<NotebookTabChanged>>", self._tab_changed)

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.grid(row=3, column=0, sticky="ew", pady=(10, 5))
        footer = ttk.Frame(outer)
        footer.grid(row=4, column=0, sticky="ew")
        self.install_button = ttk.Button(footer, text=tr("安装所需组件"), command=self.install_dependency)
        ttk.Label(footer, textvariable=self.status, width=1, style="Hint.TLabel").pack(side="left", fill="x", expand=True)
        try:
            engine.require_mido()
            device.require_serial()
        except Exception:
            self.install_button.pack(side="right")
            self.status.set(tr("可点击“安装所需组件”；JSON加载不需要转换组件。"))

        # Labels follow the available column width rather than enlarging the window.
        def wrap_left(event):
            width = max(220, event.width - 24)
            self.hint_label.configure(wraplength=width)
            self.result_label.configure(wraplength=width)
        self.left.bind("<Configure>", wrap_left)
        self._fit_window()

    def _build_upload_panel(self):
        self.upload_tab = ttk.Frame(self.settings_tabs, padding=10, style="Card.TFrame")
        self.settings_tabs.add(self.upload_tab, text=tr("上传到 Pico"))
        self.upload_tab.columnconfigure(0, weight=1)
        wiring = ttk.Label(self.upload_tab, text=tr("断电连接 GP21–GND，再接电脑并选择串口。\n完成后断电取下跳线，再接 Switch。"),
                           width=1, style="Card.TLabel", justify="left")
        wiring.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        ports = ttk.Frame(self.upload_tab, style="Card.TFrame")
        ports.grid(row=1, column=0, sticky="ew")
        ports.columnconfigure(0, weight=1)
        self.port_combo = ttk.Combobox(ports, textvariable=self.port, width=1)
        self.port_combo.grid(row=0, column=0, sticky="ew")
        self.controls.append(self.port_combo)
        self.refresh_ports_button = self._button(ports, tr("刷新串口"), self.refresh_ports)
        self.refresh_ports_button.grid(row=0, column=1, padx=(6, 0))
        self.upload_button = self._button(self.upload_tab, tr("上传当前歌曲到 Pico"), self.upload_song,
                                         style="Accent.TButton")
        self.upload_button.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.device_status_button = self._button(self.upload_tab, tr("读取设备状态"), self.read_device_status)
        self.device_status_button.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        state = ttk.Label(self.upload_tab, textvariable=self.upload_status, width=1,
                          style="Card.TLabel", justify="left")
        state.grid(row=4, column=0, sticky="ew", pady=(7, 0))
        def wrap(event):
            wiring.configure(wraplength=max(220, event.width - 24))
            state.configure(wraplength=max(220, event.width - 24))
        self.upload_tab.bind("<Configure>", wrap)

    def _tab_changed(self, event=None):
        if self.settings_tabs.select() == str(self.upload_tab):
            self.save_panel.grid_remove()
            self.generate_button.grid_remove()
        else:
            self.save_panel.grid()
            self.generate_button.grid()

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
        widget=localized_combo(parent,variable,values,width=width,state="readonly")
        self.controls.append(widget)
        return widget

    def _change_language(self, event=None):
        if self.busy:
            return
        language = next(code for code, name in LANGUAGES.items() if name == self.language.get())
        if language == get_language():
            return
        selection = self.tree.selection()
        tab = self.settings_tabs.index(self.settings_tabs.select())
        geometry = self.root.geometry()
        port = self.selected_port()
        choices = list(self.port_choices.values())
        self._rebuilding_language = True
        self.updating = True
        self._dismiss_range()
        self.stop_audio()
        set_language(language)
        # Parsing errors are cached in a score. Refresh their language only
        # when the source bytes still match the loaded score.
        if self.score and any(channel.errors for channel in self.score.channels.values()):
            try:
                score = engine.read_score(self.score.source, self.score.tempo.conflict_policy)
                if score.sha256 == self.score.sha256:
                    self.score = score
                    self.rows = {"%d:%d" % (row["track"], row["channel"]): row
                                 for row in engine.inspect_score(score)["candidates"]}
            except (OSError, ValueError):
                pass
        for child in self.root.winfo_children():
            child.destroy()
        self.controls = []
        self._build()
        self._render_rows()
        if selection and selection[0] in self.rows:
            self.tree.selection_set(selection[0])
            self.tree.focus(selection[0])
        self.port_choices = {choice.label: choice for choice in choices}
        self.port_combo.configure(values=list(self.port_choices))
        chosen = next((choice for choice in choices if choice.device == port), None)
        self.port.set(chosen.label if chosen else port)
        if self.song:
            self.result_text.set(device.song_summary(self.song))
            self.upload_status.set(tr("歌曲已就绪，刷新串口或填写 COM 编号后上传。"))
        else:
            self.result_text.set(tr("读取完成，请选择一条旋律。") if self.score else tr("完成选择后，点击“生成歌曲文件”。"))
            self.upload_status.set(tr("先加载 JSON，或生成歌曲文件，再选择串口上传。"))
        if not self.score and not self.song:
            self.file.set(tr("打开 MIDI 进行转换，或加载已有 JSON 后直接上传。"))
        self.hint.set(tr("JSON已加载，可直接试听或上传。") if self.song_kind == "json" else
                      tr("选中一行，再试听，确认它是你要的主旋律。轨道和通道编号从0开始。"))
        row = self.selection()
        if row and self.score:
            self._selection_hint(row)
            if not self.song:
                self.result_text.set(tr("已选择轨道 %d / 通道 %d，试听后确认主旋律。") %
                                     (row["track"], row["channel"]))
        self.status.set(tr("就绪"))
        self.settings_tabs.select(tab)
        self.root.geometry(geometry)
        self.updating = False
        self._refresh()
        self.root.after_idle(lambda: setattr(self, "_rebuilding_language", False))

    def _render_rows(self):
        for iid, row in self.rows.items():
            pitches = row["range"]
            span = engine.note_name(pitches[0]) + "–" + engine.note_name(pitches[1]) if pitches else "—"
            state = (tr("鼓通道") if row["drum_channel"] else tr("配对异常") if row["errors"] else
                     tr("%d处同时多音") % row["simultaneous_groups"] if row["simultaneous_groups"] else tr("单音候选"))
            self.tree.insert("", "end", iid=iid,
                values=(row["track"], row["channel"], row["name"], row["notes"], span, state),
                tags=("problem",) if row["errors"] or row["drum_channel"] else ())

    def selection(self):
        selected=self.tree.selection()
        return self.rows.get(selected[0]) if selected else None

    def _refresh(self):
        for control in self.controls:
            control.state(["disabled"] if self.busy else ["!disabled"])
        if self.score is None:
            for control in self.midi_controls:
                control.state(["disabled"])
        row=self.selection()
        valid=not self.busy and self.score is not None and row is not None and not row["drum_channel"] and bool(row["notes"])
        self.generate_button.state(["!disabled"] if valid else ["disabled"])
        self.audition_button.state(["!disabled"] if valid and not row["errors"] else ["disabled"])
        self.range_button.state(["!disabled"] if valid else ["disabled"])
        for button in (self.folder_button,self.copy_button):
            button.state(["!disabled"] if self.result and not self.busy else ["disabled"])
        self.preview_button.state(["!disabled"] if self.song and not self.busy else ["disabled"])
        self.report_button.state(["!disabled"] if self.result and self.result[2] and not self.busy else ["disabled"])
        port = bool(self.selected_port())
        self.upload_button.state(["!disabled"] if self.song and port and not self.busy else ["disabled"])
        self.device_status_button.state(["!disabled"] if port and not self.busy else ["disabled"])
        self.install_button.state(["disabled"] if self.busy else ["!disabled"])
        self.tree.state(["disabled"] if self.busy else ["!disabled"])
        self.stop_button.state(["!disabled"] if self.player.opened else ["disabled"])
        active=bool(self.pitch_min.get() and self.pitch_max.get())
        self.clear_pitch_button.state(["!disabled"] if active and self.score and not self.busy else ["disabled"])
        try:
            text=tr("框内 %s–%s")%(engine.note_name(int(self.pitch_min.get())),engine.note_name(int(self.pitch_max.get()))) if active else tr("空拍点 = 整轨")
        except ValueError: text=tr("请重新选择音域框")
        self.pitch_hint.set(text)

    def clear_pitch_filter(self):
        self.pitch_min.set("");self.pitch_max.set("")

    def _changed(self, *args):
        if self.updating or self.busy:
            return
        if self.result and self.song_kind == "midi":
            self.stop_audio()
            self._clear_song()
            self.result_text.set(tr("参数已改动，请重新生成；已保存的文件仍在原位置。"))
        self._refresh()

    def _selected(self, event=None):
        if self.busy or not self.score or self._rebuilding_language:
            return
        row=self.selection()
        if not row:
            self._refresh()
            return
        self._dismiss_range()
        self.stop_audio()
        self._clear_song()
        self.clear_pitch_filter()
        self.result_text.set(tr("已选择轨道 %d / 通道 %d，试听后确认主旋律。") % (row["track"],row["channel"]))
        options=row["transpose_options"]
        if options and 0 not in options:
            self.transpose.set(str(min(options,key=lambda value:(abs(value),value))))
        self._selection_hint(row)
        self.updating=True
        self.filename.set(self.score.source.stem[:48]+"_t%d_c%d"%(row["track"],row["channel"]))
        self.updating=False
        self._refresh()

    def _selection_hint(self, row):
        options = row["transpose_options"]
        shift = tr("整轨可移调：") + (tr("、").join("%+d" % n for n in options)
                if options else tr("整轨音域太宽，可尝试截取片段"))
        problems = []
        if row["drum_channel"]:
            problems.append(tr("GM鼓通道，不能作为陶笛旋律"))
        if row["errors"]:
            problems.append(tr("音符配对异常"))
        if row["simultaneous_groups"]:
            problems.append(tr("%d处同时多音，需要明确处理") % row["simultaneous_groups"])
        self.hint.set(tr("；").join(problems + [shift]) + tr("。可点击“拖动选择片段”边听边选。"))

    def _clear_song(self):
        self.result = None
        self.song = None
        self.song_kind = None
        self.upload_status.set(tr("先加载 JSON，或生成歌曲文件，再选择串口上传。"))
        self.progress.configure(value=0)

    def _run(self, label, work, done, determinate=False, song_load=False, operation=None):
        if self.busy:
            return
        self.busy=True
        self.operation=operation
        self.uploading=determinate
        self.loading_song=song_load
        self.status.set(label)
        self.progress.stop()
        self.progress.configure(mode="determinate" if determinate else "indeterminate", value=0, maximum=100)
        if not determinate:
            self.progress.start(12)
        self._refresh()
        def worker():
            try:
                self.events.put((done,work(),None))
            except Exception as error:
                self.events.put((done,None,error))
        threading.Thread(target=worker,daemon=True).start()

    def _poll(self):
        while True:
            try:
                done,result,error=self.events.get_nowait()
            except queue.Empty:
                break
            if done is None:
                self._upload_progress(*result)
                continue
            was_upload = self.uploading
            was_load = self.loading_song
            operation = self.operation
            self.busy=False
            self.uploading=False
            self.loading_song=False
            self.operation=None
            self.progress.stop()
            if error:
                self.status.set(tr("未完成，请按提示调整后重试。"))
                if was_upload:
                    self.progress.configure(value=0)
                    self.upload_status.set(tr("未确认保存，可读取设备状态后重试。"))
                if was_load:
                    self.result_text.set(tr("未能加载歌曲，请重新选择 MIDI 或 JSON。"))
                if not self.closing:
                    if isinstance(error,engine.ConversionIssue):
                        self._conversion_recovery(error)
                    elif operation=="convert":
                        self._show_recovery(str(error),[(tr("拖动选择较短片段"),self.open_range),
                            (tr("保存到项目输出目录并重试"),self._safe_output_and_generate),
                            (tr("选择其他保存位置并重试"),self._choose_folder_and_generate)])
                    elif operation=="load_midi":
                        self._show_recovery(str(error),[(tr("重新选择MIDI文件"),self.choose_file),
                            (tr("重新读取当前文件"),lambda:self.load_file(self.file.get()))])
                    else:
                        messagebox.showerror(tr("需要调整"),str(error),parent=self.root)
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
            try:
                if not self.player.playing():
                    self.audio_status.set(tr("试听结束"))
                    self._refresh()
            except RuntimeError as error:
                self.audio_status.set(tr("试听未完成"))
                self.status.set(str(error))
                self._refresh()
                if not self.closing:
                    messagebox.showerror(tr("试听失败"),str(error),parent=self.root)
        self._poll_id = self.root.after(100,self._poll)

    def choose_file(self):
        filename=filedialog.askopenfilename(parent=self.root,title=tr("选择 MIDI 文件"),
            filetypes=[(tr("MIDI 文件"),"*.mid *.midi"),(tr("所有文件"),"*.*")])
        if filename:
            self.load_file(filename)

    def choose_json(self):
        filename=filedialog.askopenfilename(parent=self.root,title=tr("加载歌曲 JSON"),
            filetypes=[(tr("歌曲 JSON"),"*.json"),(tr("所有文件"),"*.*")])
        if filename:
            self.load_json(filename)

    def load_json(self, filename):
        if self.busy:
            return
        self._dismiss_range()
        self._range_cache=None
        self.stop_audio()
        self._clear_song()
        self.score=None
        self.rows={}
        self.tree.delete(*self.tree.get_children())
        self.file.set(str(filename))
        self.result_text.set(tr("正在校验歌曲 JSON…"))
        def loaded(song):
            self.song=song
            self.song_kind="json"
            self.result=(song.path,None,None)
            self.result_text.set(tr("JSON 已校验：")+device.song_summary(song))
            self.hint.set(tr("JSON已加载，可直接试听或上传。"))
            self.upload_status.set(tr("歌曲已就绪，刷新串口或填写 COM 编号后上传。"))
            self.status.set(tr("已加载并校验 JSON：")+str(song.path))
            self.settings_tabs.select(self.upload_tab)
        self._run(tr("正在加载并校验 JSON…"),lambda:device.load_song(filename),loaded,song_load=True)

    def load_file(self, filename, tempo_policy="error"):
        if self.busy:
            return
        self._dismiss_range()
        self.valid_notes_only=False
        self.stop_audio()
        self.score=None
        self._range_cache=None
        self._clear_song()
        self.rows={}
        self.tree.delete(*self.tree.get_children())
        self.file.set(str(filename))
        self.result_text.set(tr("正在读取文件…"))
        def read():
            score=engine.read_score(filename) if tempo_policy=="error" else engine.read_score(filename,tempo_policy)
            return score,engine.inspect_score(score)
        def loaded(value):
            self.score,inspection=value
            for row in inspection["candidates"]:
                iid="%d:%d"%(row["track"],row["channel"])
                self.rows[iid]=row
                pitches=row["range"]
                span=engine.note_name(pitches[0])+"–"+engine.note_name(pitches[1]) if pitches else "—"
                state=(tr("鼓通道") if row["drum_channel"] else tr("配对异常") if row["errors"] else
                       tr("%d处同时多音")%row["simultaneous_groups"] if row["simultaneous_groups"] else tr("单音候选"))
                self.tree.insert("", "end", iid=iid, values=(row["track"],row["channel"],row["name"],row["notes"],span,state),
                                 tags=("problem",) if row["errors"] or row["drum_channel"] else ())
            self.updating=True
            self.title.set(self.score.source.stem[:80])
            self.transpose.set("0"); self.speed.set("100"); self.countdown.set("3")
            self.start.set(""); self.end.set("")
            self.clear_pitch_filter()
            self.polyphony.set(next(iter(POLYPHONY))); self.overlap.set(next(iter(OVERLAP)))
            self.ignore_expression.set(False)
            self.updating=False
            self.hint.set(tr("选中一行，再试听，确认它是你要的主旋律。轨道和通道编号从0开始。"))
            self.result_text.set(tr("读取完成，请选择一条旋律。"))
            adjusted=len(inspection["tempo_adjustments"])
            self.status.set(tr("读取完成：%d个轨道/通道候选。") % len(self.rows) +
                (tr("已按120 BPM读取，原速度图已忽略。") if self.score.tempo.conflict_policy=="fixed-120" else
                 tr("已兼容%d处重复速度。") % adjusted if adjusted else ""))
        self._run(tr("正在读取并检查 MIDI…"),read,loaded,song_load=True,operation="load_midi")

    def _dismiss_range(self):
        if self.range_dialog is not None and self.range_dialog.exists(): self.range_dialog.close()
        if self.recovery_dialog is not None and self.recovery_dialog.winfo_exists(): self.recovery_dialog.destroy()
        self.range_dialog=None
        self.recovery_dialog=None
        self._range_pending=None

    def _show_recovery(self, message, actions):
        if self.recovery_dialog is not None and self.recovery_dialog.winfo_exists():
            self.recovery_dialog.destroy()
        window=tk.Toplevel(self.root)
        self.recovery_dialog=window
        window.title(tr("选择处理方式，继续生成"))
        window.transient(self.root)
        frame=ttk.Frame(window,padding=16)
        frame.pack(fill="both",expand=True)
        ttk.Label(frame,text=message,wraplength=440,justify="left").pack(fill="x",pady=(0,12))
        self.recovery_actions={}
        for label,callback in actions:
            def run(action=callback):
                window.destroy()
                action()
            button=ttk.Button(frame,text=label,command=run)
            button.pack(fill="x",pady=3)
            self.recovery_actions[label]=button
        ttk.Button(frame,text=tr("返回调整"),command=window.destroy).pack(anchor="e",pady=(10,0))

    def _set_and_generate(self, variable, value):
        variable.set(value)
        self.generate()

    def _conversion_recovery(self, error):
        actions=[]
        if error.kind in ("tempo","tempo_invalid"):
            file=self.file.get()
            if error.kind=="tempo":
                actions=[(tr("采用最后一条速度并重新打开"),lambda:self.load_file(file,"last")),
                         (tr("采用第一条速度并重新打开"),lambda:self.load_file(file,"first"))]
            actions.append((tr("按120 BPM读取（忽略原速度图）"),lambda:self.load_file(file,"fixed-120")))
        else:
            current=POLYPHONY[self.polyphony.get()]
            if error.kind in ("polyphony","overlap","range","timing"):
                for label,policy in (("全部取最高音","highest"),("全部取最低音","lowest")):
                    if policy!=current:
                        actions.append((tr(label)+tr("并生成"),lambda value=label:self._set_and_generate(self.polyphony,value)))
            if error.kind in ("range","transpose"):
                options=error.details.get("options",[])
                if options:
                    shift=min(options,key=lambda value:(abs(value),value))
                    actions.insert(0,(tr("整体移调 %+d 半音并生成")%shift,lambda:self._set_and_generate(self.transpose,str(shift))))
                actions.insert(0,(tr("拖动时间轴，试听并选择可演奏片段"),self.open_range))
            if error.kind=="overlap":
                actions.append((tr("缩短重叠部分并生成"),lambda:self._set_and_generate(self.overlap,next(label for label,value in OVERLAP.items() if value=="trim"))))
            if error.kind=="expression":
                actions=[(tr("忽略弯音和踏板效果并生成"),lambda:self._set_and_generate(self.ignore_expression,True)),
                         (tr("选择不含这些效果的片段"),self.open_range)]
            if error.kind=="capacity":
                actions=[(tr("拖动选择较短的片段"),self.open_range)]
            if error.kind=="pitch_filter":
                actions=[(tr("上下拖动音域框或调整左右范围"),self.open_range),
                         (tr("取消音域框，重新调整"),self.clear_pitch_filter)]
            if error.kind=="pairing":
                def valid_only():
                    self.valid_notes_only=True
                    self.generate()
                actions=[(tr("仅转换完整音符并生成（舍弃异常音符）"),valid_only),
                         (tr("重新选择MIDI文件"),self.choose_file)]
            if error.kind=="timing":
                actions.append((tr("速度减半并生成"),lambda:self._set_and_generate(self.speed,str(Fraction(self.speed.get())/2))))
        self._show_recovery(str(error),actions)

    def _reset_and_generate(self):
        self.transpose.set("0"); self.speed.set("100"); self.countdown.set("3")
        self.start.set(""); self.end.set("")
        self.clear_pitch_filter()
        self.generate()

    def _safe_output_and_generate(self):
        self.folder.set(str(ROOT/"out/gui"))
        self.filename.set("melody")
        self.generate()

    def _choose_folder_and_generate(self):
        folder=filedialog.askdirectory(parent=self.root,title=tr("选择可写入的保存位置"))
        if folder:
            self.folder.set(folder)
            self.generate()

    def open_range(self):
        row=self.selection()
        if self.busy or not self.score or not row or not row["notes"] or row["drum_channel"]:
            return
        if self.range_dialog is not None and self.range_dialog.exists():
            self.range_dialog.window.lift(); return
        self.stop_audio()
        try:
            settings=model.settings(self.score,row["track"],row["channel"],self.get_form())
            start=settings["start_tick"]
            end=settings["end_tick"] or self.score.track_ends[row["track"]]
            if not 0<=start<end<=self.score.track_ends[row["track"]]: raise ValueError()
        except (ValueError,TypeError):
            start,end=0,self.score.track_ends[row["track"]]
        def apply(start,end,policy,options,pitch_min,pitch_max):
            self.start.set(str(Fraction(start,self.score.ppq)))
            self.end.set(str(Fraction(end,self.score.ppq)))
            self.polyphony.set(policy)
            self.pitch_min.set(str(pitch_min));self.pitch_max.set(str(pitch_max))
            try: shift=int(self.transpose.get())
            except ValueError: shift=0
            if shift not in options:
                shift=min(options,key=lambda value:(abs(value),value))
                self.transpose.set(str(shift))
            self.status.set(tr("已选框内 %s–%s，框外音符将舍弃，整体移调 %+d 半音；可直接生成。")%
                (engine.note_name(pitch_min),engine.note_name(pitch_max),shift))
        try: pitch_min=int(self.pitch_min.get())
        except ValueError: pitch_min=None
        self.range_dialog=RangeDialog(self.root,self.score,row,POLYPHONY,self.polyphony.get(),start,end,
            apply,self._range_preview,self.stop_audio,self._range_position,pitch_min)

    def _range_position(self):
        value=self.player.position_ms()
        return None if value is None else value+self._range_offset_ms

    def _range_preview(self, policy, start_ms, end_ms, pitch_min=None, pitch_max=None):
        if self.busy:
            if self.operation=="range_preview": self._range_pending=(policy,start_ms,end_ms,pitch_min,pitch_max)
            return
        if not self.score: return
        row=self.selection()
        if not row: return
        score=self.score
        dialog=self.range_dialog
        self.stop_audio()
        generation=self._audio_generation
        key=(score.sha256,row["track"],row["channel"],policy,start_ms,end_ms,pitch_min,pitch_max)
        def ready(file):
            if dialog and dialog.exists() and generation==self._audio_generation:
                self._range_offset_ms=start_ms
                self._play(file,0,tr("正在试听所选位置（原音高）"),end_ms-start_ms)
        if self._range_cache and self._range_cache[0]==key:
            ready(self._range_cache[1]); return
        def build():
            file=Path(self.preview_directory.name)/"range.mid"
            file.write_bytes(engine.range_audition_bytes(score,row["track"],row["channel"],start_ms*1000,end_ms*1000,policy,pitch_min,pitch_max))
            return file
        def complete(file):
            self._range_cache=(key,file)
            pending=self._range_pending
            self._range_pending=None
            if pending and dialog and dialog.exists(): self._range_preview(*pending)
            else: ready(file)
        self._run(tr("正在准备选段试听…"),build,complete,operation="range_preview")

    def get_form(self):
        return model.Form(self.title.get(),self.transpose.get(),self.speed.get(),self.countdown.get(),
            self.start.get(),self.end.get(),POLYPHONY[self.polyphony.get()],OVERLAP[self.overlap.get()],self.ignore_expression.get(),self.valid_notes_only,
            self.pitch_min.get(),self.pitch_max.get())

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
            if existing and not messagebox.askyesno(tr("替换已有文件？"),tr("将替换：\n")+"\n".join(existing)+tr("\n\n是否继续？"),parent=self.root):
                return
        except Exception as error:
            self._show_recovery(str(error),[(tr("恢复常用参数并重试"),self._reset_and_generate),
                (tr("拖动选择片段"),self.open_range),(tr("保存到项目输出目录并重试"),self._safe_output_and_generate)])
            return
        self.stop_audio()
        self._clear_song()
        score=self.score
        def convert():
            document,report=model.convert(score,row["track"],row["channel"],form)
            paths=engine.emit_conversion(score.source,document,report,output,force=bool(existing))
            return paths,document,report,device.load_song(paths[0])
        def complete(value):
            paths,document,report,song=value
            self.result=paths
            self.song=song
            self.song_kind="midi"
            self.result_text.set(model.summary(document,report))
            self.upload_status.set(tr("歌曲已生成，可在“上传到 Pico”页签选择串口上传。"))
            self.status.set(tr("已保存：")+str(paths[0]))
        self._run(tr("正在校验并生成歌曲、试听和处理报告…"),convert,complete,operation="convert")

    def audition(self):
        row=self.selection()
        if self.busy or not self.score or not row or row["errors"] or row["drum_channel"]:
            return
        self._dismiss_range()
        self._range_offset_ms=0
        self.stop_audio()
        score=self.score
        def build():
            file=Path(self.preview_directory.name)/"original.mid"
            file.write_bytes(engine.audition_bytes(score,row["track"],row["channel"]))
            first=score.channels[(row["track"],row["channel"])].notes[0].on
            return file,int(score.tempo.at(first)/1000)
        self._run(tr("正在准备原轨试听…"),build,lambda value:self._play(value[0],value[1],tr("正在试听原轨（原音高，从首音开始）")))

    def preview_result(self):
        if self.song and not self.busy:
            self._dismiss_range()
            song=self.song
            self.stop_audio()
            def build():
                file=Path(self.preview_directory.name)/"current.mid"
                file.write_bytes(preview_bytes(song.document)[0])
                return file
            self._run(tr("正在从当前歌曲准备试听…"),build,
                      lambda file:self._play(file,0,tr("正在试听当前歌曲")))

    def selected_port(self):
        value=self.port.get().strip()
        choice=self.port_choices.get(value)
        return choice.device if choice else value

    def _port_changed(self, *args):
        if not self.busy:
            self.upload_status.set(tr("串口已更改，可读取设备状态或上传当前歌曲。"))
            self.progress.configure(value=0)
        self._refresh()

    def refresh_ports(self):
        if self.busy:
            return
        previous=self.selected_port()
        def refreshed(choices):
            self.port_choices={choice.label:choice for choice in choices}
            self.port_combo.configure(values=list(self.port_choices))
            selected=next((choice for choice in choices if choice.device==previous),None)
            preferred=[choice for choice in choices if choice.pico]
            if selected is None and len(preferred)==1:
                selected=preferred[0]
            self.port.set(selected.label if selected else "")
            self.status.set(tr("找到 %d 个串口，请选择Pico配置端口。")%len(choices) if choices else
                            tr("没有找到串口：请检查USB数据线、GP21–GND接线，再刷新。"))
        self._run(tr("正在查找串口…"),device.list_ports,refreshed)

    def _report_upload_progress(self, stage, received, total):
        self.events.put((None,(stage,received,total),None))

    def _upload_progress(self, stage, received, total):
        labels={"connect":tr("正在打开串口…"),"handshake":tr("正在识别Pico…"),
                "transfer":tr("正在传输：%d / %d 字节")%(received,total),"validate":tr("正在由Pico校验歌曲…"),
                "commit":tr("正在保存到Pico…"),"verify":tr("正在回读并核对保存结果…"),"done":tr("保存结果已核对。")}
        percent={"connect":0,"handshake":0,"transfer":85*received/max(total,1),
                 "validate":90,"commit":94,"verify":98,"done":100}.get(stage,0)
        label=labels.get(stage,stage)
        self.progress.configure(value=percent)
        self.upload_status.set(label)
        self.status.set(label)

    def upload_song(self):
        if self.busy or self.song is None or not self.selected_port():
            return
        song,port=self.song,self.selected_port()
        self.stop_audio()
        def complete(status):
            self.progress.configure(value=100)
            self.upload_status.set(tr("上传成功，已回读核对。\n")+device.status_summary(status))
            self.status.set(tr("已保存到Pico。请断电取下GP21–GND跳线，再接Switch播放。"))
        self._run(tr("正在连接Pico…"),lambda:device.upload_song(song,port,self._report_upload_progress),
                  complete,determinate=True)

    def read_device_status(self):
        if self.busy or not self.selected_port():
            return
        port=self.selected_port()
        def complete(status):
            self.upload_status.set(device.status_summary(status))
            self.status.set(tr("设备状态已读取。"))
        self._run(tr("正在读取Pico保存状态…"),lambda:device.device_status(port),complete)

    def _play(self, file, start_ms, label, end_ms=None):
        try:
            started=self.player.play(file,start_ms,end_ms)
            status=label if started is not False else tr("已到试听结尾，所选位置没有可播放内容；可向前拖动进度条。")
            self.audio_status.set(status)
            self.status.set(status)
        except Exception as error:
            self.audio_status.set(tr("本机试听不可用"))
            messagebox.showerror(tr("试听未启动"),str(error),parent=self.root)
        self._refresh()

    def stop_audio(self):
        self._audio_generation+=1
        self._range_pending=None
        try:
            self.player.stop()
        except RuntimeError:
            pass
        self.audio_status.set("")
        self._refresh()

    def choose_folder(self):
        value=filedialog.askdirectory(parent=self.root,initialdir=self.folder.get() if Path(self.folder.get()).is_dir() else ROOT,title=tr("选择保存文件夹"))
        if value:
            self.folder.set(value)

    def toggle_advanced(self):
        self.settings_tabs.select(self.advanced)

    def _open(self, file):
        try:
            if os.name!="nt":
                raise RuntimeError(tr("文件位于：")+str(file))
            os.startfile(str(file))
        except (OSError, RuntimeError) as error:
            messagebox.showerror(tr("无法打开"),str(error),parent=self.root)

    def open_folder(self):
        if self.result:
            self._open(self.result[0].parent)

    def open_report(self):
        if self.result and self.result[2]:
            self._open(self.result[2])

    def copy_result(self):
        if self.result:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(self.result[0]))
            self.status.set(tr("已复制 JSON 路径。"))

    def install_dependency(self):
        if self.busy:
            return
        def install():
            PRIVATE_DEPS.mkdir(parents=True,exist_ok=True)
            completed=subprocess.run([sys.executable,"-m","pip","install","--target",str(PRIVATE_DEPS),
                "--upgrade","-r",str(ROOT/"tools/requirements-gui.txt"),"--disable-pip-version-check"],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors="replace",
                creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            if completed.returncode:
                raise RuntimeError(tr("组件安装未完成，请检查网络后重试。\n")+completed.stdout[-1800:])
            return True
        def installed(result):
            if str(PRIVATE_DEPS) not in sys.path:
                sys.path.insert(0,str(PRIVATE_DEPS))
            importlib.invalidate_caches()
            engine.require_mido()
            device.require_serial()
            self.install_button.pack_forget()
            self.status.set(tr("组件已安装，可以转换MIDI、加载JSON并上传到Pico。"))
        self._run(tr("正在安装转换与串口组件到本工程（需要联网）…"),install,installed)

    def _callback_error(self, kind, error, tb):
        folder=ROOT/"out/gui"
        folder.mkdir(parents=True,exist_ok=True)
        (folder/"gui_error.log").write_text("".join(traceback.format_exception(kind,error,tb)),encoding="utf-8")
        if not self.closing:
            messagebox.showerror(tr("窗口遇到问题"),str(error)+tr("\n详情已保存到 out/gui/gui_error.log"),parent=self.root)

    def close(self):
        if self.busy:
            self.closing=True
            self.status.set(tr("正在完成当前操作，随后自动关闭…"))
        else:
            self._destroy()

    def _destroy(self):
        if self.range_dialog is not None and self.range_dialog.exists():
            self.range_dialog.close()
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
