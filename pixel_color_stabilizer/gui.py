"""Small local Tk editor. No browser, GPU, service or commercial editor needed."""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

import numpy as np
from PIL import Image, ImageTk

from .media import load_animation, export_bundle
from .session import Session


class Editor:
    def __init__(self, root):
        self.root = root
        root.title('Pixel Color Stabilizer · 区域时段稳色')
        root.geometry('1120x800')
        root.minsize(880, 680)
        self.session = None
        self.busy = False
        self.dirty = False
        self.timer = None
        self.drag = None
        self.photos = []
        self.messages = queue.Queue()
        self.poll_id = None
        self.frame = tk.IntVar(value=1)
        self.zoom = tk.IntVar(value=4)
        self.mode = tk.StringVar(value='majority')
        self.cleanup = tk.BooleanVar(value=False)
        self.halo = tk.BooleanVar(value=False)
        self.vars = {k: tk.StringVar(value=v) for k, v in
                     dict(start='1', end='1', x='0', y='0', width='1', height='1', duration='100').items()}
        self.status = tk.StringVar(value='打开 PNG 序列、GIF/APNG 或精灵图开始。全部处理在本机完成。')
        outer = ttk.Frame(root, padding=14)
        outer.pack(fill='both', expand=True)
        toolbar = ttk.Frame(outer)
        toolbar.pack(fill='x')
        self.controls = []
        for label, command in [('打开动画 / Open', lambda: self.open('animation')),
                               ('PNG 序列', lambda: self.open('files')),
                               ('文件夹 / Folder', lambda: self.open('folder')),
                               ('精灵图 / Sheet', lambda: self.open('sheet'))]:
            b = ttk.Button(toolbar, text=label, command=command)
            b.pack(side='left', padx=(0, 6)); self.controls.append(b)
        self.export_button = ttk.Button(toolbar, text='导出 / Export', command=self.export)
        self.export_button.pack(side='right'); self.controls.append(self.export_button)
        ttk.Label(outer, text='框选静止部位，选择帧段，预览后应用；运动部位请缩短时段。', padding=(0, 12)).pack(anchor='w')
        fields = ttk.Frame(outer)
        fields.pack(fill='x')
        for i, (key, label) in enumerate([('start', '起始帧（含）'), ('end', '结束帧（含）'),
                                         ('x', 'X'), ('y', 'Y'), ('width', '宽 px'), ('height', '高 px'),
                                         ('duration', 'PNG 帧时长 ms')]):
            ttk.Label(fields, text=label).grid(row=0, column=i, sticky='w', padx=4)
            e = ttk.Entry(fields, textvariable=self.vars[key], width=12)
            e.grid(row=1, column=i, sticky='ew', padx=4)
            self.controls.append(e); fields.columnconfigure(i, weight=1)
        views = ttk.Frame(outer)
        views.pack(fill='both', expand=True, pady=12)
        self.canvases = []
        for i, title in enumerate(('当前已应用素材 · 拖动框选', '本次预览 · 尚未应用')):
            box = ttk.LabelFrame(views, text=title, padding=4)
            box.grid(row=0, column=i, sticky='nsew', padx=(0, 8) if i == 0 else (8, 0))
            c = tk.Canvas(box, background='#282a2d', width=440, height=360, highlightthickness=0)
            xbar = ttk.Scrollbar(box, orient='horizontal', command=c.xview)
            ybar = ttk.Scrollbar(box, orient='vertical', command=c.yview)
            c.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
            c.grid(row=0, column=0, sticky='nsew'); xbar.grid(row=1, column=0, sticky='ew'); ybar.grid(row=0, column=1, sticky='ns')
            box.rowconfigure(0, weight=1); box.columnconfigure(0, weight=1)
            self.canvases.append(c); views.columnconfigure(i, weight=1)
        views.rowconfigure(0, weight=1)
        before = self.canvases[0]
        before.bind('<ButtonPress-1>', self.begin_drag)
        before.bind('<B1-Motion>', self.move_drag)
        before.bind('<ButtonRelease-1>', self.end_drag)
        playback = ttk.Frame(outer); playback.pack(fill='x')
        self.play_button = ttk.Button(playback, text='播放 / Play', command=self.toggle_play)
        self.play_button.pack(side='left'); self.controls.append(self.play_button)
        self.slider = ttk.Scale(playback, from_=1, to=1, command=self.seek)
        self.slider.pack(side='left', fill='x', expand=True, padx=12); self.controls.append(self.slider)
        self.frame_label = ttk.Label(playback, text='0 / 0', width=14)
        self.frame_label.pack(side='left')
        ttk.Label(playback, text='缩放').pack(side='left')
        zoom = ttk.Combobox(playback, values=(1, 2, 3, 4, 6, 8, 12, 16), textvariable=self.zoom, state='readonly', width=4)
        zoom.pack(side='left'); self.controls.append(zoom)
        zoom.bind('<<ComboboxSelected>>', lambda _: self.draw())
        options = ttk.Frame(outer); options.pack(fill='x', pady=12)
        for label, value in [('含透明投票 · 稳定轮廓', 'majority'), ('只稳颜色 · 保留轮廓', 'preserve')]:
            b = ttk.Radiobutton(options, text=label, variable=self.mode, value=value)
            b.pack(side='left', padx=(0, 14)); self.controls.append(b)
        for label, var in [('合并孤立点', self.cleanup), ('允许清理选区外 1px', self.halo)]:
            b = ttk.Checkbutton(options, text=label, variable=var)
            b.pack(side='left', padx=(0, 12)); self.controls.append(b)
        ttk.Label(outer, text='透明严格超过半数则清空；半数平票补齐。颜色同票取最早出现值。X/Y 从 0 开始，帧号从 1 开始。', wraplength=1000).pack(anchor='w')
        actions = ttk.Frame(outer); actions.pack(fill='x', pady=12)
        self.preview_button = ttk.Button(actions, text='生成预览 / Preview', command=self.preview)
        self.apply_button = ttk.Button(actions, text='应用当前选区 / Apply', command=self.apply)
        self.undo_button = ttk.Button(actions, text='撤回 / Undo', command=self.undo)
        for b in (self.preview_button, self.apply_button, self.undo_button):
            b.pack(side='left', padx=(0, 8)); self.controls.append(b)
        ttk.Label(outer, textvariable=self.status, wraplength=1040).pack(anchor='w')
        for key, var in self.vars.items():
            if key != 'duration':
                var.trace_add('write', self.invalidate)
        for var in (self.mode, self.cleanup, self.halo):
            var.trace_add('write', self.invalidate)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.update_controls()
        self.poll_id = root.after(80, self.poll)

    def update_controls(self):
        for widget in self.controls:
            widget.state(['disabled'] if self.busy else ['!disabled'])
        if not self.busy:
            for widget in (self.preview_button, self.export_button, self.play_button, self.slider):
                widget.state(['!disabled'] if self.session else ['disabled'])
            self.apply_button.state(['!disabled'] if self.session and self.session.preview else ['disabled'])
            self.undo_button.state(['!disabled'] if self.session and self.session.history else ['disabled'])

    def invalidate(self, *_):
        if self.session and not self.busy:
            self.session.invalidate()
            self.status.set('选区或参数已改变，请重新生成预览。')
            self.update_controls(); self.draw()

    def stop(self):
        if self.timer is not None:
            self.root.after_cancel(self.timer); self.timer = None
        self.play_button.configure(text='播放 / Play')

    def open(self, kind):
        if self.busy:
            return
        if self.dirty and not messagebox.askyesno('未导出修改', '当前修改尚未导出，仍然打开其他素材？', parent=self.root):
            return
        try:
            cell = None; count = None
            if kind == 'files':
                source = filedialog.askopenfilenames(filetypes=[('PNG sequence', '*.png')])
            elif kind == 'folder':
                source = filedialog.askdirectory()
            else:
                source = filedialog.askopenfilename(filetypes=[('PNG / GIF / APNG', '*.png *.gif *.apng')])
            if not source:
                return
            if kind == 'sheet':
                w = simpledialog.askinteger('精灵图', '单帧宽度 px', minvalue=1, parent=self.root)
                if w is None: return
                h = simpledialog.askinteger('精灵图', '单帧高度 px', minvalue=1, parent=self.root)
                if h is None: return
                count = simpledialog.askinteger('精灵图', '有效帧数（按行排列，排除末尾空格）', minvalue=1, parent=self.root)
                if count is None: return
                cell = (w, h)
            duration = int(self.vars['duration'].get())
            self.stop()
            self.background(lambda: load_animation(source, duration, cell, count), self.loaded)
        except Exception as error:
            messagebox.showerror('打开失败', str(error), parent=self.root)

    def loaded(self, animation):
        self.session = Session(animation)
        self.dirty = False
        h, w = animation.frames[0].shape[:2]
        self.vars['start'].set('1'); self.vars['end'].set(str(len(animation.frames)))
        for key, value in dict(x=0, y=0, width=w, height=h).items():
            self.vars[key].set(str(value))
        # Fit a large canvas initially; users can zoom and scroll explicitly.
        self.zoom.set(max(1, min(8, 430 // w, 340 // h)))
        self.frame.set(1); self.slider.configure(to=len(animation.frames)); self.slider.set(1)
        for c in self.canvases:
            c.xview_moveto(0); c.yview_moveto(0)
        self.status.set(f'已打开 {len(animation.frames)} 帧 · {w} × {h} · {sum(animation.durations)} ms。请框选需要稳定的部位。')
        self.draw()

    def background(self, job, success):
        self.stop(); self.busy = True; self.update_controls(); self.status.set('正在处理…')
        def run():
            try:
                self.messages.put((success, job(), None))
            except Exception as error:
                self.messages.put((success, None, error))
        threading.Thread(target=run, daemon=True).start()

    def poll(self):
        try:
            callback, result, error = self.messages.get_nowait()
            self.busy = False
            if error:
                self.status.set(str(error)); messagebox.showerror('处理失败', str(error), parent=self.root)
            else:
                callback(result)
            self.update_controls()
        except queue.Empty:
            pass
        self.poll_id = self.root.after(80, self.poll)

    def params(self):
        keys = ('start', 'end', 'x', 'y', 'width', 'height')
        values = {k: int(self.vars[k].get()) for k in keys}
        return dict(start=values['start'], end=values['end'],
                    rectangles=[{k: values[k] for k in ('x', 'y', 'width', 'height')}],
                    alpha_mode=self.mode.get(), cleanup_isolated=self.cleanup.get(),
                    cleanup_halo=1 if self.cleanup.get() and self.halo.get() else 0)

    def preview(self):
        if not self.session or self.busy: return
        try:
            params = self.params()
            self.session.invalidate(); self.update_controls()
            self.background(lambda: self.session.make_preview(**params), self.preview_ready)
        except ValueError as error:
            messagebox.showerror('参数错误', str(error), parent=self.root)

    def preview_ready(self, report):
        self.frame.set(report['start']); self.slider.set(report['start'])
        self.status.set(f"预览：{report['changed_positions']} 个坐标 / {report['changed_pixels']} 处像素变化；补齐 {report['filled_pixels']}，清空 {report['cleared_pixels']}。尚未应用。")
        self.draw()

    def apply(self):
        if self.busy or not self.session or self.session.preview is None: return
        self.stop(); self.session.apply(); self.dirty = True
        self.status.set('已应用。可以继续框选；完成后导出保存。')
        self.update_controls(); self.draw()

    def undo(self):
        if self.busy or not self.session or not self.session.history: return
        self.stop(); self.session.undo(); self.dirty = True
        self.status.set('已撤回最近一次修改；历史仅保留于本次会话。')
        self.update_controls(); self.draw()

    def export(self):
        if not self.session or self.busy: return
        if self.session.preview is not None:
            messagebox.showinfo('预览尚未应用', '请先应用当前预览，或修改参数以取消预览，再导出。', parent=self.root)
            return
        parent = filedialog.askdirectory(title='选择导出位置（将在其中新建文件夹）')
        if not parent: return
        name = simpledialog.askstring('导出', '新文件夹名', initialvalue='stabilized', parent=self.root)
        if not name: return
        from pathlib import Path
        if name in ('.', '..') or any(c in name for c in '/\\:') or Path(name).name != name:
            messagebox.showerror('导出失败', '请输入单个文件夹名。', parent=self.root); return
        def done(path):
            self.dirty = False
            self.status.set(f'已导出 PNG 序列、APNG、精灵图与时序 JSON：{path}')
            messagebox.showinfo('导出完成', str(path), parent=self.root)
        self.background(lambda: export_bundle(Path(parent)/name, self.session.current), done)

    def seek(self, value):
        self.frame.set(round(float(value))); self.draw()

    def toggle_play(self):
        if self.timer is not None:
            self.stop(); return
        if not self.session or self.busy: return
        self.play_button.configure(text='暂停 / Pause')
        self.tick()

    def tick(self):
        if not self.session: return
        self.draw()
        index = self.frame.get()-1
        self.timer = self.root.after(self.session.current.durations[index], self.advance)

    def advance(self):
        try:
            start, end = int(self.vars['start'].get()), int(self.vars['end'].get())
            if not 1 <= start <= end <= len(self.session.current.frames): raise ValueError()
        except ValueError:
            start, end = 1, len(self.session.current.frames)
        index = self.frame.get()
        index = start if index >= end or index < start else index+1
        self.frame.set(index); self.slider.set(index); self.tick()

    def point(self, event):
        h, w = self.session.current.frames[0].shape[:2]
        c = self.canvases[0]; z = self.zoom.get()
        return max(0, min(w-1, int(c.canvasx(event.x)//z))), max(0, min(h-1, int(c.canvasy(event.y)//z)))

    def begin_drag(self, event):
        if not self.session or self.busy: return
        self.drag = self.point(event); self.move_drag(event)

    def move_drag(self, event):
        if self.drag is None or self.busy: return
        x, y = self.point(event); a, b = self.drag
        for key, value in dict(x=min(x, a), y=min(y, b), width=abs(x-a)+1, height=abs(y-b)+1).items():
            self.vars[key].set(str(value))

    def end_drag(self, event):
        self.move_drag(event); self.drag = None

    def draw(self):
        if not self.session: return
        current = self.session.current
        i = max(0, min(len(current.frames)-1, self.frame.get()-1))
        self.frame_label.configure(text=f'{i+1} / {len(current.frames)} · {current.durations[i]}ms')
        self.photos = []
        for c, animation in zip(self.canvases, (current, self.session.preview or current)):
            image = Image.fromarray(animation.frames[i]); w, h = image.size; z = self.zoom.get()
            yy, xx = np.indices((h, w)); grid = ((xx//8 + yy//8) % 2)*16 + 64
            checker = np.empty((h, w, 4), np.uint8); checker[..., :3] = grid[..., None]; checker[..., 3] = 255
            bg = Image.fromarray(checker); bg.alpha_composite(image)
            photo = ImageTk.PhotoImage(bg.resize((w*z, h*z), Image.Resampling.NEAREST))
            self.photos.append(photo); c.delete('all'); c.create_image(0, 0, image=photo, anchor='nw')
            c.configure(scrollregion=(0, 0, w*z, h*z))
            try:
                x, y, rw, rh = (int(self.vars[k].get()) for k in ('x', 'y', 'width', 'height'))
                c.create_rectangle(x*z, y*z, (x+rw)*z, (y+rh)*z, outline='#ffcd57', width=2)
            except ValueError:
                pass

    def close(self):
        if self.busy:
            messagebox.showinfo('正在处理', '请等待当前处理完成。', parent=self.root); return
        if self.dirty and not messagebox.askyesno('未导出修改', '修改尚未导出，仍然退出？', parent=self.root): return
        self.stop()
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
        self.root.destroy()


def main():
    root = tk.Tk()
    Editor(root)
    root.mainloop()


if __name__ == '__main__':
    main()
