"""
Subsistema Principal (GUI) - Cuarto Frío
1. Monitoreo en vivo desde MySQL con representación gráfica del cuarto frío
2. Lectura y modificación de parámetros mediante API-REST del ESP32
3. Estadísticas y gráficas históricas por rango de tiempo desde MySQL
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import requests
import mysql.connector
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- CONFIGURACIÓN ---
ESP32_IP = "192.168.1.100"  # Reemplazar por la IP real del ESP32
URL_BASE_ESP32 = f"http://{ESP32_IP}"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",  # Colocar contraseña de MySQL local
    "database": "cuarto_frio_db"
}


class AplicacionCuartoFrio:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Control y Monitoreo - Cuarto Frío (ITSON)")
        self.root.geometry("1020x700")

        self.ultimo_id_bd = None

        self._construir_interfaz()
        self.cargar_parametros_esp32()
        self.monitorear_bd_en_vivo()

    def _construir_interfaz(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_monitoreo = ttk.Frame(notebook)
        self.tab_parametros = ttk.Frame(notebook)
        self.tab_estadisticas = ttk.Frame(notebook)

        notebook.add(self.tab_monitoreo, text="1. Monitoreo y Modelo Visual (BD Local)")
        notebook.add(self.tab_parametros, text="2. Parámetros del Sistema (API-REST)")
        notebook.add(self.tab_estadisticas, text="3. Estadísticas Históricas (Gráficos)")

        self._construir_tab_monitoreo()
        self._construir_tab_parametros()
        self._construir_tab_estadisticas()

    # =========================================================================
    # PESTAÑA 1: MONITOREO EN VIVO (DESDE MYSQL) + REPRESENTACIÓN GRÁFICA
    # =========================================================================
    def _construir_tab_monitoreo(self):
        contenedor = ttk.Frame(self.tab_monitoreo, padding=15)
        contenedor.pack(fill=tk.BOTH, expand=True)

        # Panel Izquierdo: Representación Gráfica del Cuarto Frío
        frame_visual = ttk.LabelFrame(contenedor, text="Representación Gráfica del Cuarto Frío", padding=10)
        frame_visual.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.canvas_cuarto = tk.Canvas(frame_visual, width=520, height=460, bg="#f1f5f9", highlightthickness=1, highlightbackground="#94a3b8")
        self.canvas_cuarto.pack(pady=10)

        # Panel Derecho: Datos Recientes de la Base de Datos Local
        frame_datos = ttk.LabelFrame(contenedor, text="Último Registro en MySQL", padding=15)
        frame_datos.pack(side=tk.RIGHT, fill=tk.Y)

        self.vars_monitoreo = {
            "id": tk.StringVar(value="--"),
            "fecha": tk.StringVar(value="--"),
            "temp": tk.StringVar(value="-- °C"),
            "ldr": tk.StringVar(value="--"),
            "puerta": tk.StringVar(value="--"),
            "movimiento": tk.StringVar(value="--"),
            "ventilador": tk.StringVar(value="--"),
            "luz": tk.StringVar(value="--")
        }

        etiquetas = [
            ("ID Registro BD:", "id"),
            ("Fecha/Hora Sensado:", "fecha"),
            ("Temperatura Interior:", "temp"),
            ("Nivel Luz (LDR):", "ldr"),
            ("Estado de Puerta:", "puerta"),
            ("Sensor Movimiento:", "movimiento"),
            ("Actuador Ventilador:", "ventilador"),
            ("Actuador Luz:", "luz"),
        ]

        for fila, (texto, clave) in enumerate(etiquetas):
            ttk.Label(frame_datos, text=texto, font=("Segoe UI", 10, "bold")).grid(row=fila, column=0, sticky="w", pady=8)
            ttk.Label(frame_datos, textvariable=self.vars_monitoreo[clave], font=("Segoe UI", 10)).grid(row=fila, column=1, sticky="e", padx=(15, 0), pady=8)

        self.dibujar_cuarto_frio(20.0, 4.0, False, False, False, False)

    def dibujar_cuarto_frio(self, temp, temp_obj, puerta_abierta, movimiento, fan_on, luz_on):
        c = self.canvas_cuarto
        c.delete("all")

        # Color interior según temperatura respecto al objetivo
        en_rango_frio = temp <= temp_obj
        color_interior = "#dbeafe" if en_rango_frio else "#fee2e2"
        color_borde_temp = "#2563eb" if en_rango_frio else "#dc2626"

        # Estructura externa del Cuarto Frío (paredes aislantes)
        c.create_rectangle(60, 60, 420, 380, fill=color_interior, outline="#334155", width=6)
        c.create_text(240, 35, text="MODELO FÍSICO: CUARTO FRÍO", font=("Segoe UI", 12, "bold"), fill="#0f172a")

        # 1. Actuador Ventilador / Evaporador (Superior Izquierda)
        color_fan = "#16a34a" if fan_on else "#94a3b8"
        c.create_rectangle(85, 85, 195, 165, fill="#e2e8f0", outline=color_fan, width=3)
        c.create_oval(115, 95, 165, 145, fill=color_fan, outline="#1e293b", width=2)
        c.create_text(140, 155, text=f"VENTILADOR: {'ON' if fan_on else 'OFF'}", font=("Segoe UI", 8, "bold"), fill="#0f172a")

        # 2. Actuador Luz Interior (Techo Centro)
        color_luz = "#facc15" if luz_on else "#cbd5e1"
        c.create_line(260, 60, 260, 95, width=3, fill="#334155")
        c.create_oval(240, 95, 280, 135, fill=color_luz, outline="#475569", width=2)
        c.create_text(260, 150, text=f"LUZ: {'ENCENDIDA' if luz_on else 'APAGADA'}", font=("Segoe UI", 8, "bold"), fill="#0f172a")

        # 3. Indicador Térmico Central (Sensor DHT22)
        c.create_rectangle(150, 195, 330, 265, fill="#ffffff", outline=color_borde_temp, width=2)
        c.create_text(240, 218, text=f"{temp:.1f} °C", font=("Segoe UI", 18, "bold"), fill=color_borde_temp)
        c.create_text(240, 246, text=f"Objetivo: <= {temp_obj:.1f} °C", font=("Segoe UI", 9), fill="#475569")

        # 4. Sensor PIR (Movimiento interior)
        color_pir = "#22c55e" if movimiento else "#94a3b8"
        c.create_oval(90, 315, 125, 350, fill=color_pir, outline="#1e293b", width=2)
        c.create_text(185, 332, text=f"PIR: {'MOVIMIENTO' if movimiento else 'SIN MOVIMIENTO'}", font=("Segoe UI", 9, "bold"), fill="#0f172a")

        # 5. Puerta Lateral + Fotocelda LDR (Pared Derecha)
        if puerta_abierta:
            # Puerta abierta hacia afuera (Rojo)
            c.create_line(420, 170, 495, 130, width=8, fill="#dc2626")
            c.create_text(455, 210, text="PUERTA\nABIERTA\n(LDR ALTA)", font=("Segoe UI", 9, "bold"), fill="#dc2626")
        else:
            # Puerta cerrada sellada (Verde)
            c.create_line(420, 170, 420, 320, width=8, fill="#16a34a")
            c.create_text(465, 245, text="PUERTA\nCERRADA\n(OK)", font=("Segoe UI", 9, "bold"), fill="#16a34a")

    def monitorear_bd_en_vivo(self):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM lecturas_sensores ORDER BY id DESC LIMIT 1")
            fila = cursor.fetchone()
            cursor.close()
            conn.close()

            # Actualizar solo cuando llegue un nuevo registro a la BD Local
            if fila and fila["id"] != self.ultimo_id_bd:
                self.ultimo_id_bd = fila["id"]

                temp = float(fila["temperatura"])
                temp_obj = float(fila["temp_objetivo_vigente"])
                puerta = bool(fila["puerta_abierta"])
                mov = bool(fila["movimiento_detectado"])
                fan = bool(fila["estado_ventilador"])
                luz = bool(fila["estado_luz"])

                self.vars_monitoreo["id"].set(str(fila["id"]))
                self.vars_monitoreo["fecha"].set(str(fila["fecha_hora_esp32"]))
                self.vars_monitoreo["temp"].set(f"{temp:.1f} °C (Obj: {temp_obj:.1f} °C)")
                self.vars_monitoreo["ldr"].set(str(fila["nivel_luz_ldr"]))
                self.vars_monitoreo["puerta"].set("ABIERTA" if puerta else "CERRADA")
                self.vars_monitoreo["movimiento"].set("DETECTADO" if mov else "SIN MOVIMIENTO")
                self.vars_monitoreo["ventilador"].set("ENCENDIDO" if fan else "APAGADO")
                self.vars_monitoreo["luz"].set("ENCENDIDA" if luz else "APAGADA")

                self.dibujar_cuarto_frio(temp, temp_obj, puerta, mov, fan, luz)

        except mysql.connector.Error:
            pass

        self.root.after(1000, self.monitorear_bd_en_vivo)

    # =========================================================================
    # PESTAÑA 2: PARÁMETROS DEL SISTEMA (API-REST DEL ESP32)
    # =========================================================================
    def _construir_tab_parametros(self):
        frame = ttk.LabelFrame(self.tab_parametros, text="Configuración Remota vía API-REST (ESP32)", padding=20)
        frame.pack(padx=20, pady=20, fill=tk.X)

        self.var_temp_obj = tk.StringVar()
        self.var_umbral_ldr = tk.StringVar()
        self.var_tiempo_luz = tk.StringVar()

        ttk.Label(frame, text="Temperatura Objetivo (°C):").grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=self.var_temp_obj, width=20).grid(row=0, column=1, padx=10, pady=8)

        ttk.Label(frame, text="Umbral Luz Puerta LDR (0 - 4095):").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=self.var_umbral_ldr, width=20).grid(row=1, column=1, padx=10, pady=8)

        ttk.Label(frame, text="Tiempo Luz sin Movimiento (seg):").grid(row=2, column=0, sticky="w", pady=8)
        ttk.Entry(frame, textvariable=self.var_tiempo_luz, width=20).grid(row=2, column=1, padx=10, pady=8)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=15)

        ttk.Button(btn_frame, text="Consultar Parámetros Actuales (GET)", command=self.cargar_parametros_esp32).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Guardar Cambios en ESP32 (POST)", command=self.guardar_parametros_esp32).pack(side=tk.LEFT, padx=5)

    def cargar_parametros_esp32(self):
        try:
            res = requests.get(f"{URL_BASE_ESP32}/api/estado", timeout=3)
            res.raise_for_status()
            params = res.json()["parametros"]
            self.var_temp_obj.set(str(params["temp_objetivo"]))
            self.var_umbral_ldr.set(str(params["umbral_luz_puerta"]))
            self.var_tiempo_luz.set(str(params["tiempo_luz_seg"]))
        except Exception as e:
            print(f"Aviso: No se pudo leer configuración inicial del ESP32: {e}")

    def guardar_parametros_esp32(self):
        try:
            payload = {
                "temp_objetivo": float(self.var_temp_obj.get()),
                "umbral_luz_puerta": int(self.var_umbral_ldr.get()),
                "tiempo_luz_seg": int(self.var_tiempo_luz.get())
            }
            res = requests.post(f"{URL_BASE_ESP32}/api/config", json=payload, timeout=3)
            res.raise_for_status()

            # Registrar cambio en auditoría MySQL
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO historial_configuracion (temp_objetivo, umbral_luz_puerta, tiempo_luz_seg, origen) VALUES (%s, %s, %s, %s)",
                (payload["temp_objetivo"], payload["umbral_luz_puerta"], payload["tiempo_luz_seg"], "GUI_PYTHON")
            )
            conn.commit()
            cursor.close()
            conn.close()

            messagebox.showinfo("Éxito", "Parámetros actualizados en el ESP32 correctamente.")
        except ValueError:
            messagebox.showerror("Error de formato", "Verifica que los valores numéricos sean válidos.")
        except Exception as e:
            messagebox.showerror("Error de comunicación", f"No se pudo actualizar el ESP32:\n{e}")

    # =========================================================================
    # PESTAÑA 3: ESTADÍSTICAS HISTÓRICAS (DESDE MYSQL)
    # =========================================================================
    def _construir_tab_estadisticas(self):
        panel_filtros = ttk.LabelFrame(self.tab_estadisticas, text="Período de Consulta (Base de Datos Local)", padding=10)
        panel_filtros.pack(fill=tk.X, padx=10, pady=10)

        ahora = datetime.now()
        hace_una_hora = ahora - timedelta(hours=1)

        self.var_inicio = tk.StringVar(value=hace_una_hora.strftime("%Y-%m-%d %H:%M:%S"))
        self.var_fin = tk.StringVar(value=ahora.strftime("%Y-%m-%d %H:%M:%S"))

        ttk.Label(panel_filtros, text="Inicio (YYYY-MM-DD HH:MM:SS):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(panel_filtros, textvariable=self.var_inicio, width=20).pack(side=tk.LEFT, padx=5)

        ttk.Label(panel_filtros, text="Fin (YYYY-MM-DD HH:MM:SS):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(panel_filtros, textvariable=self.var_fin, width=20).pack(side=tk.LEFT, padx=5)

        ttk.Button(panel_filtros, text="Generar Gráficos Estadísticos", command=self.generar_estadisticas).pack(side=tk.LEFT, padx=10)

        self.lbl_resumen = ttk.Label(self.tab_estadisticas, text="Selecciona un rango y presiona 'Generar Gráficos Estadísticos'.", font=("Segoe UI", 10, "bold"))
        self.lbl_resumen.pack(pady=5)

        self.figura = Figure(figsize=(9, 4.8), dpi=100)
        self.ax_temp = self.figura.add_subplot(211)
        self.ax_ldr = self.figura.add_subplot(212)
        self.figura.tight_layout(pad=2.5)

        self.canvas_graficos = FigureCanvasTkAgg(self.figura, master=self.tab_estadisticas)
        self.canvas_graficos.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def generar_estadisticas(self):
        inicio = self.var_inicio.get().strip()
        fin = self.var_fin.get().strip()

        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)
            sql = """
                SELECT fecha_hora_registro, temperatura, nivel_luz_ldr, temp_objetivo_vigente
                FROM lecturas_sensores
                WHERE fecha_hora_registro BETWEEN %s AND %s
                ORDER BY id ASC
            """
            cursor.execute(sql, (inicio, fin))
            registros = cursor.fetchall()
            cursor.close()
            conn.close()

            if not registros:
                messagebox.showinfo("Sin datos", "No se encontraron registros en el período indicado.")
                return

            tiempos = [r["fecha_hora_registro"].strftime("%H:%M:%S") for r in registros]
            temps = [float(r["temperatura"]) for r in registros]
            ldrs = [int(r["nivel_luz_ldr"]) for r in registros]
            objetivos = [float(r["temp_objetivo_vigente"]) for r in registros]

            t_min, t_max, t_prom = min(temps), max(temps), sum(temps) / len(temps)
            self.lbl_resumen.config(
                text=f"Registros: {len(registros)}  |  Temp. Mín: {t_min:.1f} °C  |  Temp. Máx: {t_max:.1f} °C  |  Promedio: {t_prom:.1f} °C"
            )

            self.ax_temp.clear()
            self.ax_temp.plot(tiempos, temps, color="#2563eb", marker="o", markersize=3, label="Temperatura (°C)")
            self.ax_temp.plot(tiempos, objetivos, color="#dc2626", linestyle="--", label="Temp. Objetivo (°C)")
            self.ax_temp.set_title("Comportamiento de Temperatura en el Cuarto Frío")
            self.ax_temp.set_ylabel("°C")
            self.ax_temp.legend(loc="upper right")
            self.ax_temp.grid(True, linestyle=":", alpha=0.6)

            self.ax_ldr.clear()
            self.ax_ldr.plot(tiempos, ldrs, color="#d97706", marker="s", markersize=3, label="Nivel de Luz LDR (Puerta)")
            self.ax_ldr.set_title("Nivel de Iluminación Interior (Apertura de Puerta)")
            self.ax_ldr.set_ylabel("ADC (0-4095)")
            self.ax_ldr.legend(loc="upper right")
            self.ax_ldr.grid(True, linestyle=":", alpha=0.6)

            # Reducir etiquetas del eje X si hay muchos puntos
            paso = max(1, len(tiempos) // 10)
            self.ax_temp.set_xticks(range(0, len(tiempos), paso))
            self.ax_temp.set_xticklabels(tiempos[::paso], rotation=25)
            self.ax_ldr.set_xticks(range(0, len(tiempos), paso))
            self.ax_ldr.set_xticklabels(tiempos[::paso], rotation=25)

            self.figura.tight_layout(pad=2.0)
            self.canvas_graficos.draw()

        except mysql.connector.Error as e:
            messagebox.showerror("Error MySQL", f"Error al consultar estadísticas:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = AplicacionCuartoFrio(root)
    root.mainloop()