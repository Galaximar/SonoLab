"""Guía visual de SonoLab, independiente de las mediciones de la sesión."""
import math
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from matplotlib import get_data_path


INK = '#193348'
MUTED = '#567083'
TEAL = '#087f75'
PALE = '#e0f1ed'
BACKGROUND = '#f2f6f8'
LINE = '#dce5eb'
ORANGE = '#c65b10'

SECTIONS = (
    ('Primeros pasos', 'Medir la velocidad del sonido\ncon dos micrófonos',
     'Cada ensayo usa dos micrófonos separados. Ambos registran los mismos dos aplausos, en un archivo por micrófono.'),
    ('Cargar y editar', 'Preparar las mediciones',
     'Una fila reúne el audio A, el audio B y la separación entre sus micrófonos.'),
    ('Analizar y leer', 'Entender los resultados',
     'El análisis comienza al pulsar «Analizar pares». Podés revisar cada toma por separado.'),
    ('Revisar las marcas', 'Ver dónde empieza cada aplauso',
     'Las marcas deben señalar la llegada del sonido directo, no simplemente su pico más alto.'),
    ('Gráficos y temperatura', 'Explorar y demostrar',
     'Relacioná una toma con la recta y compará la medición con la referencia por temperatura.'),
    ('Guardar y compartir', 'Conservar la experiencia',
     'La sesión guarda la lista de audios y sus datos. Los resultados se exportan al analizar.'),
)


class HelpGuide(tk.Toplevel):
    """Ventana no modal: sus ejemplos nunca ejecutan acciones sobre la sesión."""

    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.title('SonoLab · Cómo funciona')
        self.configure(bg=BACKGROUND)
        self.transient(parent)
        width = min(1000, self.winfo_screenwidth()-60)
        height = min(760, self.winfo_screenheight()-90)
        self.geometry(f'{width}x{height}')
        self.minsize(min(760, width), min(540, height))
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        self.bind('<Escape>', lambda event: self.destroy())
        self.bind('<MouseWheel>', self._wheel)
        self.bind('<Button-4>', lambda event: self._scroll(-3))
        self.bind('<Button-5>', lambda event: self._scroll(3))
        self.page_index = 0
        self.wrapped = []
        self.icons = []
        self._styles()

        header = tk.Frame(self, bg=INK, padx=24, pady=18)
        header.pack(fill='x')
        tk.Label(header, text='SONOLAB  /  GUÍA DE USO', bg=INK, fg='#8fd6c9',
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        tk.Label(header, text='Cómo funciona SonoLab', bg=INK, fg='white',
                 font=('Segoe UI', 23, 'bold')).pack(anchor='w', pady=(4, 3))
        tk.Label(header, text='Los controles, los gráficos y el recorrido de una medición.',
                 bg=INK, fg='#d6e4ee', font=('Segoe UI', 10)).pack(anchor='w')

        footer = tk.Frame(self, bg='white', padx=20, pady=12)
        footer.pack(side='bottom', fill='x')
        self.counter = tk.Label(footer, bg='white', fg=MUTED, font=('Segoe UI', 10))
        self.counter.pack(side='left')
        self.close_button = ttk.Button(footer, text='Cerrar guía', command=self.destroy)
        self.close_button.pack(side='right', padx=(16, 0))
        self.next_button = ttk.Button(footer, text='Siguiente →', style='Guide.Next.TButton',
                                      command=lambda: self.show_page(self.page_index+1))
        self.next_button.pack(side='right', padx=(6, 0))
        self.previous_button = ttk.Button(footer, text='← Anterior',
                                          command=lambda: self.show_page(self.page_index-1))
        self.previous_button.pack(side='right')

        main = tk.Frame(self, bg=BACKGROUND)
        main.pack(fill='both', expand=True)
        sidebar = tk.Frame(main, bg='#e8eff3', width=202, padx=12, pady=20)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text='CONTENIDO', bg='#e8eff3', fg=MUTED,
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w', padx=8, pady=(0, 10))
        self.navigation = []
        for i, (name, _, _) in enumerate(SECTIONS):
            button = tk.Button(sidebar, text=f'{i+1:02d}   {name}', anchor='w',
                               wraplength=166, justify='left', relief='flat', bd=0,
                               padx=10, pady=12, font=('Segoe UI', 10), cursor='hand2',
                               command=lambda index=i: self.show_page(index))
            button.pack(fill='x', pady=3)
            self.navigation.append(button)
        self.sidebar_note = tk.Label(sidebar, text='Elegí un tema o avanzá\ncon «Siguiente».\n\nEsc cierra esta guía.',
                                     justify='left', bg='#e8eff3', fg=MUTED, font=('Segoe UI', 9))
        self.sidebar_note.pack(anchor='w', padx=8, pady=(24, 0))

        reader = tk.Frame(main, bg=BACKGROUND)
        reader.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(reader, bg=BACKGROUND, highlightthickness=0, yscrollincrement=18)
        scrollbar = ttk.Scrollbar(reader, orient='vertical', command=self.canvas.yview)
        scrollbar.pack(side='right', fill='y')
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.body = tk.Frame(self.canvas, bg=BACKGROUND, padx=24, pady=22)
        self.body_id = self.canvas.create_window((0, 0), window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda event: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', self._resize)
        self.bind('<Configure>', self._adapt_height, add='+')
        self.show_page(0)

    def _styles(self):
        style = ttk.Style(self)
        style.configure('Guide.Next.TButton', background=TEAL, foreground='white',
                        font=('Segoe UI', 10, 'bold'), padding=(12, 7))
        style.map('Guide.Next.TButton', background=[('disabled', '#e8eff3'), ('active', '#06675f')],
                  foreground=[('disabled', '#718491')])

    def _label(self, parent, text, size=10, bold=False, color=INK, background=None, inset=0):
        label = tk.Label(parent, text=text, bg=background or parent.cget('bg'), fg=color,
                         font=('Segoe UI', size, 'bold' if bold else 'normal'),
                         justify='left', anchor='w', wraplength=self._wrap_width()-inset)
        label.pack(fill='x', anchor='w')
        self.wrapped.append((label, inset))
        return label

    def _wrap_width(self):
        return max(260, self.canvas.winfo_width()-94)

    def _resize(self, event):
        self.canvas.itemconfigure(self.body_id, width=event.width)
        for label, inset in self.wrapped:
            label.configure(wraplength=self._wrap_width()-inset)

    def _adapt_height(self, event):
        if event.widget is not self:
            return
        compact = event.height < 650
        for button in self.navigation:
            button.configure(pady=6 if compact else 12)
            button.pack_configure(pady=2 if compact else 3)
        if compact:
            self.sidebar_note.pack_forget()
        elif not self.sidebar_note.winfo_manager():
            self.sidebar_note.pack(anchor='w', padx=8, pady=(24, 0))

    def _scroll(self, units):
        if self.canvas.yview() != (0., 1.):
            self.canvas.yview_scroll(units, 'units')
        return 'break'

    def _wheel(self, event):
        if event.delta:
            return self._scroll(-max(1, abs(event.delta)//120)*3 if event.delta > 0
                                else max(1, abs(event.delta)//120)*3)

    def _card(self, heading, text, control=None, primary=False):
        frame = tk.Frame(self.body, bg='white', highlightbackground=LINE,
                         highlightthickness=1, padx=16, pady=14)
        frame.pack(fill='x', pady=(0, 12))
        if control:
            # Muestra visual del control, sin ejecutar acciones de la aplicación.
            tk.Label(frame, text=control, bg=TEAL if primary else '#eef3f6',
                     fg='white' if primary else INK, relief='solid', bd=1,
                     padx=12, pady=7, font=('Segoe UI', 10, 'bold' if primary else 'normal')).pack(
                         anchor='w', pady=(0, 10))
        self._label(frame, heading, size=12, bold=True).pack_configure(pady=(0, 5))
        self._label(frame, text)

    def _note(self, text):
        frame = tk.Frame(self.body, bg=PALE, padx=16, pady=12)
        frame.pack(fill='x', pady=(0, 12))
        self._label(frame, text, color='#075f57')

    def _toolbar_card(self):
        frame = tk.Frame(self.body, bg='white', highlightbackground=LINE,
                         highlightthickness=1, padx=16, pady=14)
        frame.pack(fill='x', pady=(0, 12))
        self._label(frame, 'La barra del gráfico ampliado', size=12, bold=True).pack_configure(pady=(0, 8))
        controls = (
            ('home', 'Home · Vista inicial', 'Restablece la vista completa del gráfico.'),
            ('back', 'Back · Atrás', 'Vuelve a la vista anterior.'),
            ('forward', 'Forward · Adelante', 'Recupera la siguiente vista del historial.'),
            ('move', 'Pan · Desplazar', 'Activá el botón y arrastrá para mover la vista.'),
            ('zoom_to_rect', 'Zoom · Ampliar', 'Activá el botón y dibujá un rectángulo sobre la zona que querés ampliar.'),
            ('subplots', 'Subplots · Márgenes', 'Abre los controles de márgenes y espaciado. Reset restaura sus valores.'),
            ('filesave', 'Save · Guardar imagen', 'Elegí el nombre, la ubicación y el formato para guardar el gráfico.'),
        )
        for icon, title, explanation in controls:
            row = tk.Frame(frame, bg='white')
            row.pack(fill='x', pady=8)
            picture = tk.PhotoImage(master=self, file=str(Path(get_data_path())/'images'/f'{icon}.png'))
            picture = picture.subsample(max(1, math.ceil(picture.width()/24)))
            self.icons.append(picture)
            tk.Label(row, image=picture, bg='#eef3f6', padx=8, pady=8).pack(side='left', anchor='n', padx=(0, 12))
            text = tk.Frame(row, bg='white')
            text.pack(side='left', fill='x', expand=True)
            self._label(text, title, bold=True, inset=50)
            self._label(text, explanation, inset=50)
        self._label(frame, 'Estos son los mismos iconos de la barra del gráfico. '
                    'Pulsá otra vez Pan o Zoom para desactivarlo. Cambian la vista, no el cálculo.',
                    color=MUTED).pack_configure(pady=(8, 0))

    def _diagram(self, kind):
        canvas = tk.Canvas(self.body, height=186 if kind == 'setup' else 210,
                           bg='white', highlightbackground=LINE, highlightthickness=1)
        canvas.pack(fill='x', pady=(0, 14))
        canvas.bind('<Configure>', lambda event: self._draw(canvas, kind, event.width))

    @staticmethod
    def _draw(c, kind, width):
        c.delete('all')
        font = ('Segoe UI', 10)
        if kind == 'setup':
            left, right = 72, width-72
            c.create_line(left+32, 90, right-32, 90, fill='#9cb0bc', width=2, arrow='both')
            c.create_text(width/2, 72, text='Separación entre micrófonos', fill=MUTED, font=font)
            for x, letter, caption in ((left, 'A', '1.er aplauso'), (right, 'B', '2.º aplauso')):
                c.create_text(x, 25, text=letter, fill=TEAL, font=('Segoe UI', 15, 'bold'))
                c.create_polygon(x-13, 58, x-13, 44, x+13, 44, x+13, 58,
                                 x+13, 77, x+13, 91, x-13, 91, x-13, 77,
                                 smooth=True, fill=PALE, outline=TEAL, width=2)
                for y in (58, 65, 72):
                    c.create_line(x-7, y, x+7, y, fill=TEAL, width=1.5)
                c.create_arc(x-21, 63, x+21, 105, start=180, extent=180,
                             style='arc', outline=TEAL, width=2)
                c.create_line(x-21, 84, x-21, 72, fill=TEAL, width=2)
                c.create_line(x+21, 84, x+21, 72, fill=TEAL, width=2)
                c.create_line(x, 105, x, 118, fill=TEAL, width=2)
                c.create_line(x-15, 118, x+15, 118, fill=TEAL, width=2)
                c.create_text(x, 138, text=caption, fill=INK, font=font)
            c.create_text(width/2, 166, text='Cada micrófono registra ambos aplausos.', fill=MUTED, font=font)
        elif kind == 'wave':
            x0, x1 = 64, width-30
            span = x1-x0
            for y, name, shift in ((66, 'A', 0), (133, 'B', .022)):
                c.create_text(25, y, text=name, fill=TEAL, font=('Segoe UI', 13, 'bold'))
                c.create_line(x0, y, x1, y, fill=LINE)
                points = []
                for i in range(361):
                    t = i/360
                    amplitude = 2*math.sin(90*t)
                    for onset in (.25+shift, .72-shift):
                        if 0 <= t-onset < .13:
                            amplitude += 32*math.exp(-32*(t-onset))*math.sin(500*(t-onset))
                    points.extend((x0+t*span, y-amplitude))
                c.create_line(*points, fill='#427caf', width=1.5)
                for onset in (.25+shift, .72-shift):
                    x = x0+onset*span
                    c.create_line(x, y-35, x, y+27, fill=ORANGE, width=2, dash=(4, 3))
            c.create_text(x0+.25*span, 17, text='Aplauso 1', fill=INK, font=font)
            c.create_text(x0+.72*span, 17, text='Aplauso 2', fill=INK, font=font)
            c.create_text(width/2, 189, text='Esquema ilustrativo · naranja: inicios del sonido', fill=MUTED, font=font)
        else:
            x0, x1, y0, y1 = 52, width-30, 164, 32
            c.create_line(x0, y1, x0, y0, x1, y0, fill=MUTED, width=1.5)
            c.create_line(x0+15, y0-9, x1-15, y1+7, fill='#427caf', width=2)
            for i, dy in enumerate((4, -6, 7, -3, 5)):
                x = x0+(x1-x0)*(.15+i*.17)
                y = y0-(y0-y1)*(.15+i*.17)+dy
                c.create_oval(x-4, y-4, x+4, y+4, fill=TEAL, outline=TEAL)
                if i == 2:
                    c.create_oval(x-10, y-10, x+10, y+10, outline=ORANGE, width=3)
            c.create_text(15, 32, text='ΔT', fill=MUTED, font=font)
            c.create_text(width/2, 188, text='Separación entre micrófonos · esquema ilustrativo', fill=MUTED, font=font)

    def show_page(self, index):
        index = max(0, min(len(SECTIONS)-1, index))
        self.page_index = index
        for widget in self.body.winfo_children():
            widget.destroy()
        self.wrapped.clear()
        self.icons.clear()
        for i, button in enumerate(self.navigation):
            selected = i == index
            button.configure(bg=TEAL if selected else '#e8eff3', fg='white' if selected else INK,
                             activebackground='#06675f' if selected else '#dce7ed',
                             activeforeground='white' if selected else INK)
        _, title, introduction = SECTIONS[index]
        self._label(self.body, f'{index+1:02d} / {len(SECTIONS):02d}', size=10, bold=True, color=TEAL)
        self._label(self.body, title, size=20, bold=True).pack_configure(pady=(5, 8))
        self._label(self.body, introduction, color=MUTED).pack_configure(pady=(0, 18))
        getattr(self, f'_page_{index}')()
        self.counter.configure(text=f'{index+1} de {len(SECTIONS)} · Guía visual')
        self.previous_button.configure(state='disabled' if index == 0 else 'normal')
        self.next_button.configure(state='disabled' if index == len(SECTIONS)-1 else 'normal')
        self.body.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        self.canvas.yview_moveto(0)

    def _page_0(self):
        self._diagram('setup')
        self._card('1. Grabar el mismo ensayo',
                   'Ubicá los micrófonos en posiciones fijas y medí la separación entre micrófonos. '
                   'Iniciá las grabaciones, aplaudí cerca de A y después cerca de B, y guardá un archivo por micrófono. '
                   'Pueden usarse micrófonos de celulares u otros equipos de grabación. No hace falta iniciar las grabaciones al mismo tiempo.')
        self._card('2. Cargar y analizar',
                   'Agregá un par de audios por ensayo, su distancia y la temperatura del aire. '
                   'Dejá vacíos los inicios para detectarlos automáticamente y pulsá «Analizar pares».',
                   '+ Agregar par A/B')
        self._card('3. Comparar varias distancias',
                   'Con al menos tres distancias distintas y una pendiente positiva se obtiene la velocidad '
                   'del ajuste. Seleccioná cada fila para revisar sus dos audios y los cuatro inicios.')
        self._note('Los recuadros de esta guía muestran cómo reconocer los controles. '
                   'Para usarlos, volvé a la ventana principal; la guía puede quedar abierta.')

    def _page_1(self):
        self._card('Agregar una medición',
                   'Abre el formulario del par. A corresponde al micrófono junto al primer aplauso y B '
                   'al micrófono junto al segundo. Ambos archivos deben contener los dos aplausos.', '+ Agregar par A/B')
        self._card('Buscar los archivos',
                   'Hay un botón «Elegir…» para Audio A y otro para Audio B. Seleccioná WAV, MP4, M4A '
                   'u otro formato admitido. En «Separación (m)», ingresá la distancia entre micrófonos; '
                   'podés usar coma o punto decimal.', 'Elegir…')
        self._card('Confirmar el formulario',
                   '«OK» acepta la medición; «Cancel» cierra sin aplicar los cambios. Los campos '
                   '«Aplauso 1» y «Aplauso 2» son tiempos en segundos dentro de cada audio: completá '
                   'ambos o dejá ambos vacíos para la detección automática.', 'OK   /   Cancel')
        self._card('Corregir una toma',
                   'Seleccioná una fila y abrí este botón, o hacé doble clic en la fila. Podés cambiar '
                   'archivos, separación e inicios. Después de analizar, aparecen los tiempos detectados '
                   'para poder revisarlos.', 'Editar / revisar marcas')
        self._card('Retirar filas de la sesión',
                   'Elimina las filas seleccionadas de la lista. Los archivos de audio permanecen en su carpeta. '
                   'Podés seleccionar varias filas con Ctrl o Shift.', 'Quitar')
        self._card('Registrar la temperatura del experimento',
                   'El campo superior «Temperatura °C (opcional)» acepta valores entre −20 y 40 °C. '
                   'Se usa para la referencia teórica al analizar; puede quedar vacío. '
                   'Si cambiás este valor, pulsá «Analizar pares» para actualizar la referencia.')
        self._note('Agregar, editar o quitar mediciones deja la sesión pendiente de un nuevo análisis. '
                   'Los resultados exportados anteriormente se conservan.')

    def _page_2(self):
        self._card('Procesar los pares cargados',
                   'Convierte los audios, localiza los aplausos, calcula tiempos y velocidades, ajusta la recta '
                   'y exporta los resultados. La reducción de graves se aplica automáticamente cuando el detector '
                   'encuentra evidencia para hacerlo. Los archivos originales no se sobrescriben.',
                   'Analizar pares', primary=True)
        self._card('Leer la tabla',
                   'TA es el intervalo entre aplausos en A; TB, el intervalo en B. TA−TB es su diferencia '
                   'en milisegundos. «v (m/s)» es la velocidad de esa toma: 2 × separación / (TA−TB), '
                   'usando segundos. Seleccionar una fila muestra sus audios y resalta su punto en el ajuste.')
        self._card('Reconocer los estados',
                   'Pendiente: todavía falta analizar.\n'
                   'Procesado: se pudo calcular la velocidad; puede haber avisos para revisar.\n'
                   'Sin medición: no se pudo obtener una velocidad válida; consultá el resumen.')
        self._card('Interpretar las tres tarjetas',
                   'La primera muestra la velocidad obtenida de la pendiente y su margen ±, no el promedio '
                   'de las velocidades individuales. La segunda indica pares calculados / total. '
                   'La tercera muestra la referencia teórica para la temperatura registrada.')
        self._card('Qué significa «Ajuste provisional»',
                   'El cálculo está terminado. La etiqueta aparece en todos los ajustes para recordar que hay '
                   'que revisar los inicios y el montaje antes de validar la medición. No es un aviso de error '
                   'detectado ni cambia la velocidad o su margen. Revisar marcas no cambia esa etiqueta.')
        self._card('Consultar el detalle del análisis',
                   '«Resumen del experimento» reúne los tiempos, resultados y avisos de cada par. '
                   '«Incertidumbre · fuentes de error» explica los aportes del ± y los supuestos utilizados. '
                   'El margen es estimado: no representa una cobertura fija ni incluye sesgos desconocidos.')
        self._note('Durante el análisis algunos controles se desactivan. «Abrir resultados» se habilita '
                   'al terminar; los controles del ajuste necesitan resultados suficientes.')

    def _page_3(self):
        self._diagram('wave')
        self._card('Elegir qué ensayo mirar',
                   'Seleccioná una fila y entrá en «Audios A y B · marcas». A está a la izquierda y B '
                   'a la derecha. Arriba se ven los audios completos; en el medio, el primer aplauso; '
                   'abajo, el segundo. Las líneas marcan los tiempos de llegada.')
        self._card('Abrir la imagen en tamaño completo',
                   'Hacé doble clic sobre el gráfico de los audios. Se abre la imagen exportada en el visor '
                   'del sistema; allí podés usar sus herramientas de ampliación. Las zonas amarillas, '
                   'cuando aparecen, indican dónde se aplicó reducción automática de graves.')
        self._card('Ajustar los inicios manualmente',
                   'Abrí la fila seleccionada. Los cuatro campos corresponden a los dos aplausos en cada '
                   'archivo. Indicá los segundos desde el comienzo de ese archivo, con el primer tiempo '
                   'antes del segundo. Confirmá con «OK» y volvé a analizar.', 'Editar / revisar marcas')
        self._note('Para volver a la detección automática de un audio, borrá sus dos tiempos. '
                   'Elegí las marcas por lo que muestra la señal; una velocidad cercana a la referencia '
                   'no demuestra por sí sola que sean correctas.')

    def _page_4(self):
        self._diagram('fit')
        self._card('Seguir una medición en la recta',
                   'La pestaña «Ajuste lineal · puntos y recta» muestra TA−TB frente a la separación. '
                   'El círculo naranja señala la toma elegida en la tabla. Si hay repeticiones, '
                   'la recta usa los promedios por distancia; el círculo sigue señalando la toma individual.')
        self._card('Ampliar el ajuste',
                   'Abre una ventana más grande. También podés hacer doble clic en el gráfico del ajuste. '
                   'La selección naranja sigue a la fila elegida en la ventana principal.', 'Ampliar gráfico')
        self._toolbar_card()
        self._card('Ir al ajuste desde el resumen',
                   'El botón al pie de «Resumen del experimento» selecciona la pestaña del ajuste. '
                   'Desde allí, «Ampliar gráfico» abre la ventana con herramientas.', 'Ver gráfico del ajuste')
        self._card('Explorar la referencia térmica',
                   'En «Temperatura · referencia», mové el deslizador entre −20 y 40 °C. '
                   'El punto naranja y el valor mostrado siguen la temperatura explorada. '
                   'El círculo azul conserva la temperatura del último análisis.')
        self._card('Comparar las dos temperaturas de las pruebas',
                   'Los botones «16 °C» y «20 °C» llevan el deslizador a esos valores. La curva usa '
                   'v = 331,3 + 0,606 × T. Este control explora la teoría: no cambia la temperatura '
                   'de la sesión, las marcas ni la velocidad experimental.', '16 °C     /     20 °C')

    def _page_5(self):
        self._card('Guardar la sesión',
                   'En el menú «Archivo», «Guardar sesión…» crea un JSON con la lista de pares, distancias, '
                   'marcas manuales si las hay, temperatura y configuración de incertidumbre. '
                   'Los audios quedan como archivos separados.', 'Archivo → Guardar sesión…')
        self._card('Recuperar una sesión',
                   '«Abrir sesión…» carga el JSON y reemplaza la lista actual. Guardá antes la sesión actual '
                   'si querés conservarla. Después de abrir, pulsá «Analizar pares» para calcular los resultados.',
                   'Archivo → Abrir sesión…')
        self._card('Encontrar tablas y gráficos exportados',
                   'Abre la carpeta del último análisis: contiene el resumen, los resultados por par, '
                   'el ajuste, las imágenes de las señales y el detalle de incertidumbre. '
                   'Cada análisis crea su propia carpeta dentro de Documents/EcoLab, en la carpeta personal.',
                   'Abrir resultados')
        self._card('Llevar la sesión a otra computadora',
                   'Copiá el JSON y sus audios conservando la estructura de carpetas. Las rutas relativas '
                   'se resuelven desde la carpeta del JSON. Para las sesiones incluidas, mantené '
                   'los JSON junto a «audios», con sus carpetas 1_40cm, 2_40cm y 3_proximo.')
        self._card('Cerrar SonoLab',
                   '«Archivo → Salir» o la X de la ventana principal cierran el programa. '
                   'Si hay un análisis en curso, esperá a que termine. Guardá la sesión si querés '
                   'conservar la lista actual.', 'Archivo → Salir')
        self._card('Volver a esta guía',
                   '«¿Cómo funciona?» abre esta ayuda. Usá el índice, «Anterior» o «Siguiente» para recorrerla. '
                   'Podés desplazar el contenido con la rueda o la barra lateral. «Cerrar guía», Esc o la X '
                   'cierran únicamente esta ventana.', '¿Cómo funciona?')
