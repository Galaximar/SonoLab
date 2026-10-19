"""Ventana y controles compartidos de SonoLab; la aplicación inicia en paired_app.py."""
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from desktop import open_path

BACKGROUND = '#eef3f6'
FOREGROUND = '#193348'
ACCENT = '#087f75'


class BaseWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('SonoLab · Velocidad del sonido')
        self.geometry('1240x850')
        self.minsize(1020, 700)
        self.configure(bg=BACKGROUND)
        self.entries = {}
        self.analysis_result = None
        self.busy = False
        self.events = queue.Queue()
        self.original_image = None
        self.photo = None
        self.counter = 0
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.configure_styles()
        self.build_widgets()
        self.after(120, self.process_events)

    def configure_styles(self):
        s = ttk.Style(self)
        s.theme_use('clam')
        s.configure('.', font=('Segoe UI', 10), background=BACKGROUND, foreground=FOREGROUND)
        s.configure('TFrame', background=BACKGROUND)
        s.configure('Card.TFrame', background='white')
        s.configure('TLabel', background=BACKGROUND)
        s.configure('Title.TLabel', font=('Segoe UI', 25, 'bold'))
        s.configure('Sub.TLabel', foreground='#567083')
        s.configure('Metric.TLabel', background='white', font=('Segoe UI', 23, 'bold'))
        s.configure('Caption.TLabel', background='white', foreground='#567083')
        s.configure('TButton', padding=(12, 7))
        s.configure('Go.TButton', background=ACCENT, foreground='white', font=('Segoe UI', 11, 'bold'))
        s.map('Go.TButton', background=[('active', '#06675f'), ('disabled', '#9bafac')])
        s.configure('Treeview', background='white', fieldbackground='white', rowheight=32, borderwidth=0)
        s.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), padding=7)
        s.map('Treeview', background=[('selected', '#d9eeeb')], foreground=[('selected', FOREGROUND)])
        s.configure('TNotebook.Tab', padding=(16, 8))

    def build_widgets(self):
        base = ttk.Frame(self, padding=22)
        base.pack(fill='both', expand=True)
        self.title_label = ttk.Label(base, text='SonoLab', style='Title.TLabel')
        self.title_label.pack(anchor='w')
        self.subtitle_label = ttk.Label(base, text='Medí la velocidad del sonido a partir de tus grabaciones.', style='Sub.TLabel')
        self.subtitle_label.pack(anchor='w', pady=(0, 16))
        controls = ttk.Frame(base)
        self.header_controls = controls
        controls.pack(fill='x')
        self.add = ttk.Button(controls, text='+ Agregar audios', command=self.add_pair)
        self.add.pack(side='left')
        self.edit = ttk.Button(controls, text='Cambiar distancia', command=self.edit_pair)
        self.edit.pack(side='left', padx=6)
        self.remove = ttk.Button(controls, text='Quitar', command=self.remove_selected)
        self.remove.pack(side='left')
        ttk.Label(controls, text='Temperatura °C (opcional)').pack(side='left', padx=(18, 5))
        self.temp = ttk.Entry(controls, width=7)
        self.temp.pack(side='left')
        self.help_button = ttk.Button(controls, text='¿Cómo funciona?', command=self.show_help)
        self.help_button.pack(side='right', padx=(6, 0))
        table_frame = ttk.Frame(base)
        table_frame.pack(fill='x', pady=(12, 0))
        self.table = ttk.Treeview(table_frame, columns=(), show='headings', height=4)
        scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.table.pack(side='left', fill='x', expand=True)
        self.table.tag_configure('aviso', foreground='#945814')
        self.table.tag_configure('fallo', foreground='#ad3541')
        self.table.bind('<<TreeviewSelect>>', self.select_measurement)
        self.table.bind('<Double-1>', lambda e: self.edit_pair() if not self.analysis_result else None)
        actions = ttk.Frame(base)
        actions.pack(fill='x', pady=12)
        self.go = ttk.Button(actions, text='Analizar grabaciones', style='Go.TButton', command=self.analyze)
        self.go.pack(side='left')
        self.open_results_button = ttk.Button(actions, text='Abrir resultados', command=self.open_results, state='disabled')
        self.open_results_button.pack(side='left', padx=8)
        self.status = tk.StringVar(value='Agregá un audio e indicá a qué distancia de la pared lo grabaste.')
        ttk.Label(actions, textvariable=self.status, style='Sub.TLabel').pack(side='left', padx=8)
        self.progress_bar = ttk.Progressbar(base, mode='determinate')
        self.progress_bar.pack(fill='x', pady=(0, 12))
        cards = ttk.Frame(base)
        self.cards_frame = cards
        cards.pack(fill='x')
        self.metrics = []
        for heading in ['VELOCIDAD DEL AJUSTE', 'DETECCIONES / ARCHIVOS', 'REFERENCIA POR TEMPERATURA']:
            card = ttk.Frame(cards, style='Card.TFrame', padding=14)
            card.pack(side='left', fill='x', expand=True, padx=(0, 8))
            ttk.Label(card, text=heading, style='Caption.TLabel').pack(anchor='w')
            value = ttk.Label(card, text='—', style='Metric.TLabel')
            value.pack(anchor='w', pady=(5, 0))
            self.metrics.append(value)
        self.notice = tk.StringVar(value='Los resultados son provisionales hasta revisar las señales. La distancia aproximada también aporta incertidumbre.')
        self.notice_label = ttk.Label(base, textvariable=self.notice, wraplength=1120, foreground='#8b5b1c')
        self.notice_label.pack(fill='x', pady=(12, 10))
        self.tabs = ttk.Notebook(base)
        self.tabs.pack(fill='both', expand=True)
        signal_panel = ttk.Frame(self.tabs)
        self.tabs.add(signal_panel, text='Señal de la grabación')
        self.image_canvas = tk.Canvas(signal_panel, bg='white', highlightthickness=0)
        self.image_canvas.pack(fill='both', expand=True)
        self.image_canvas.bind('<Configure>', lambda e: self.redraw_image())
        self.image_canvas.bind('<Double-1>', lambda e: self.open_image())
        self.detail = tk.StringVar(value='Seleccioná una grabación después del análisis para ver su señal. Doble clic en el gráfico para ampliarlo.')
        ttk.Label(signal_panel, textvariable=self.detail, wraplength=1100).pack(fill='x', pady=5)
        summary = ttk.Frame(self.tabs)
        self.tabs.add(summary, text='Resumen del experimento')
        self.text = tk.Text(summary, wrap='word', bg='white', fg=FOREGROUND, font=('Segoe UI', 11), relief='flat', padx=18, pady=14)
        self.text.pack(fill='both', expand=True)
        self.text.insert('1.0', 'Los resultados se guardan automáticamente en Documentos/EcoLab, en una carpeta por análisis.\n\nSe conservan todos los originales. No es necesario renombrar los archivos.\n\nPodés guardar y abrir una sesión desde el menú Archivo.')
        self.text.configure(state='disabled')
        self.view_fit_button = ttk.Button(summary, text='Ver gráfico del ajuste', command=self.show_fit, state='disabled')
        self.view_fit_button.pack(anchor='w', pady=5)
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label='Guardar sesión…', command=self.save_session)
        file_menu.add_command(label='Abrir sesión…', command=self.load_session)
        file_menu.add_separator()
        file_menu.add_command(label='Salir', command=self.close)
        menu.add_cascade(label='Archivo', menu=file_menu)
        self.configure(menu=menu)

    def remove_selected(self):
        if self.busy:
            return
        for iid in self.table.selection():
            self.table.delete(iid)
            del self.entries[iid]
        self.invalidate_results()

    def set_busy(self, active):
        self.busy = active
        for widget in [self.add, self.edit, self.remove, self.go, self.temp]:
            widget.configure(state='disabled' if active else 'normal')

    def process_events(self):
        try:
            while True:
                kind, event_data = self.events.get_nowait()
                if kind == 'progreso':
                    i, n, msg = event_data
                    self.progress_bar.configure(maximum=n, value=i)
                    self.status.set(msg)
                elif kind == 'resultado':
                    self.set_busy(False)
                    self.show_result(event_data)
                elif kind == 'error':
                    self.set_busy(False)
                    self.status.set('No se pudo completar el análisis')
                    messagebox.showerror('Análisis interrumpido', event_data, parent=self)
        except queue.Empty:
            pass
        self.after(120, self.process_events)

    def select_measurement(self, event=None):
        if not self.analysis_result or not self.table.selection():
            return
        f = self.results_by_id[self.table.selection()[0]]
        self.detail.set(f['nombre'] + ' · ' + (' | '.join(f['avisos']) if f['avisos'] else 'Detección automática. Verificá las marcas sobre la señal.') + ' · Doble clic en el gráfico para ampliar.')
        self.show_image(f['grafico'])

    def show_image(self, path):
        self.image_path = path
        self.original_image = None
        if path:
            with Image.open(path) as img:
                self.original_image = img.copy()
        self.redraw_image()

    def redraw_image(self):
        self.image_canvas.delete('all')
        w, h = self.image_canvas.winfo_width(), self.image_canvas.winfo_height()
        if self.original_image:
            img = self.original_image.copy()
            img.thumbnail((max(1, w-12), max(1, h-12)), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(img)
            self.image_canvas.create_image(w/2, h/2, image=self.photo)
        else:
            self.image_canvas.create_text(w/2, h/2, text='La señal de tu grabación aparecerá aquí', fill='#78909e', font=('Segoe UI', 13))

    def open_image(self):
        if getattr(self, 'image_path', None):
            self.open_external(self.image_path)

    def open_results(self):
        if self.analysis_result:
            self.open_external(self.analysis_result['salida'])

    def open_external(self, path):
        try:
            open_path(path)
        except OSError as exc:
            messagebox.showerror('No se pudo abrir', str(exc), parent=self)

    def close(self):
        if self.busy:
            messagebox.showinfo('Análisis en curso', 'Esperá a que termine el análisis antes de cerrar.', parent=self)
            return
        self.destroy()
