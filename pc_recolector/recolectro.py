"""
Subsistema de Recolección de Datos - Cuarto Frío
Consulta la API-REST del ESP32 y almacena las lecturas en la BD local MySQL.
"""

import time
import requests
import mysql.connector

# --- CONFIGURACIÓN ---
ESP32_IP = "192.168.1.100"  # Reemplazar por la IP impresa en el Monitor Serial del ESP32
URL_ESTADO = f"http://{ESP32_IP}/api/estado"
INTERVALO_SEG = 2.0

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",  # Colocar contraseña de MySQL local
    "database": "cuarto_frio_db"
}


def conectar_bd():
    return mysql.connector.connect(**DB_CONFIG)


def main():
    print(f"[Recolector] Iniciando recolección desde {URL_ESTADO}...")
    ultima_fecha_esp32 = None

    while True:
        try:
            respuesta = requests.get(URL_ESTADO, timeout=3)
            respuesta.raise_for_status()
            datos = respuesta.json()

            fecha_esp32 = datos["fecha_hora"]

            # Evitar insertar lecturas repetidas si el ciclo del ESP32 aún no cambia
            if fecha_esp32 != ultima_fecha_esp32:
                sensores = datos["sensores"]
                actuadores = datos["actuadores"]
                params = datos["parametros"]

                conexion = conectar_bd()
                cursor = conexion.cursor()

                sql = """
                    INSERT INTO lecturas_sensores (
                        fecha_hora_esp32, temperatura, nivel_luz_ldr,
                        puerta_abierta, movimiento_detectado,
                        estado_ventilador, estado_luz, temp_objetivo_vigente
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                valores = (
                    fecha_esp32,
                    float(sensores["temperatura"]),
                    int(sensores["lectura_ldr"]),
                    1 if sensores["puerta_abierta"] else 0,
                    1 if sensores["movimiento"] else 0,
                    1 if actuadores["ventilador"] else 0,
                    1 if actuadores["luz"] else 0,
                    float(params["temp_objetivo"])
                )

                cursor.execute(sql, valores)
                conexion.commit()
                cursor.close()
                conexion.close()

                ultima_fecha_esp32 = fecha_esp32
                print(
                    f"[OK] {fecha_esp32} | Temp: {sensores['temperatura']}°C | "
                    f"Puerta: {'ABR' if sensores['puerta_abierta'] else 'CER'} | "
                    f"Fan: {'ON' if actuadores['ventilador'] else 'OFF'} | "
                    f"Luz: {'ON' if actuadores['luz'] else 'OFF'}"
                )

        except requests.RequestException as e:
            print(f"[Error Red/ESP32] No se pudo conectar al ESP32: {e}")
        except mysql.connector.Error as e:
            print(f"[Error MySQL] No se pudo guardar en BD: {e}")

        time.sleep(INTERVALO_SEG)


if __name__ == "__main__":
    main()