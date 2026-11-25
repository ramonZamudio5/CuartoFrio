/**
 * Proyecto Final: Sistema Empotrado de Monitoreo y Control de Cuarto Frío
 * Microcontrolador: ESP32 DevKit V1
 * Responsabilidades:
 *   1. Servidor Web con archivos externos (HTML/CSS) en LittleFS
 *   2. API-REST (GET /api/estado y POST /api/config)
 *   3. Sensado periódico y control de actuadores con NoDelay (cero delay())
 */

#include <WiFi.h>
#include <WebServer.h>
#include <LittleFS.h>
#include <ArduinoJson.h>
#include <NoDelay.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <time.h>

// ============================================================================
// 1. CONFIGURACIÓN DE RED Y NTP
// ============================================================================
const char* SSID = "TU_RED_WIFI";
const char* PASSWORD = "TU_PASSWORD_WIFI";

// Zona horaria Sonora / Hermosillo (UTC -7, sin horario de verano)
const long GMT_OFFSET_SEC = -7 * 3600;
const int DAYLIGHT_OFFSET_SEC = 0;
const char* NTP_SERVER = "pool.ntp.org";

// ============================================================================
// 2. DEFINICIÓN DE PINES DE HARDWARE
// ============================================================================
#define PIN_DHT        4    // Sensor DHT22 (Temperatura)
#define PIN_LDR        34   // Fotocelda LDR (Puerta abierta/cerrada)
#define PIN_PIR        27   // Sensor PIR HC-SR501 (Movimiento)
#define PIN_FAN        26   // Base transistor NPN 2N2222 (Ventilador 5V)
#define PIN_RELE_LUZ   25   // Módulo Relé 1 Canal (Luz interior)

#define DHTTYPE DHT22
#define RELE_ON  HIGH
#define RELE_OFF LOW

// ============================================================================
// 3. ESTRUCTURAS DE DATOS (SOLO SE CONSERVA EL ÚLTIMO VALOR OBTENIDO)
// ============================================================================
struct ParametrosSistema {
  float tempObjetivo;       // Parámetro 1: Temperatura máxima antes de encender fan (°C)
  int umbralLuzPuerta;      // Parámetro 2: Umbral LDR (0-4095) que indica puerta abierta
  unsigned int tiempoLuzSeg;// Parámetro 3: Segundos sin movimiento para apagar luz
};

struct EstadoActual {
  char fechaHora[25];       // Timestamp del último sensado (YYYY-MM-DD HH:MM:SS)
  float temperatura;        // Última temperatura (°C)
  int lecturaLdr;           // Última lectura analógica LDR
  bool puertaAbierta;       // true = puerta abierta (entra luz)
  bool movimiento;          // true = movimiento detectado
  bool ventiladorEncendido; // Estado actuador ventilador
  bool luzEncendida;        // Estado actuador luz
};

ParametrosSistema config = { 4.0, 2000, 15 };
EstadoActual ultimoEstado = { "2026-01-01 00:00:00", 0.0, 0, false, false, false, false };

// ============================================================================
// 4. OBJETOS GLOBALES Y TEMPORIZADORES NoDelay
// ============================================================================
DHT dht(PIN_DHT, DHTTYPE);
LiquidCrystal_I2C lcd(0x27, 16, 2);
WebServer server(80);

// Temporizadores no bloqueantes (biblioteca NoDelay)
noDelay timerSensado(1000);      // Lectura de sensores y actualización LCD cada 1000 ms
noDelay timerControlLuz(250);    // Evaluación del temporizador de luz cada 250 ms
noDelay timerConexionWiFi(500);  // Verificación no bloqueante de conexión WiFi

unsigned long instanteUltimoMovimiento = 0;
bool wifiConectadoPrevio = false;

// ============================================================================
// 5. FUNCIONES AUXILIARES (FECHA/HORA, LCD Y CONTROL)
// ============================================================================
void obtenerFechaHoraActual(char* buffer, size_t len) {
  struct tm timeinfo;
  if (getLocalTime(&timeinfo, 10)) {
    strftime(buffer, len, "%Y-%m-%d %H:%M:%S", &timeinfo);
  } else {
    // Respaldo válido en formato DATETIME si no hay acceso a servidor NTP
    unsigned long segTotales = millis() / 1000;
    unsigned int hh = (segTotales / 3600) % 24;
    unsigned int mm = (segTotales / 60) % 60;
    unsigned int ss = segTotales % 60;
    snprintf(buffer, len, "2026-11-24 %02u:%02u:%02u", hh, mm, ss);
  }
}

void actualizarPantallaLCD() {
  // Fila 0: Temp y Puerta -> Ej: "T:23.5°C P:CER "
  lcd.setCursor(0, 0);
  lcd.print("T:");
  lcd.print(ultimoEstado.temperatura, 1);
  lcd.print((char)223);
  lcd.print("C P:");
  lcd.print(ultimoEstado.puertaAbierta ? "ABR  " : "CER  ");

  // Fila 1: Actuadores -> Ej: "Fan:ON  Luz:OFF"
  lcd.setCursor(0, 1);
  lcd.print("Fan:");
  lcd.print(ultimoEstado.ventiladorEncendido ? "ON  " : "OFF ");
  lcd.print("Luz:");
  lcd.print(ultimoEstado.luzEncendida ? "ON " : "OFF");
}

void ejecutarCicloSensado() {
  // 1. Obtener timestamp exacto del sensado
  obtenerFechaHoraActual(ultimoEstado.fechaHora, sizeof(ultimoEstado.fechaHora));

  // 2. Leer Fotocelda (LDR) para estado de la puerta
  ultimoEstado.lecturaLdr = analogRead(PIN_LDR);
  ultimoEstado.puertaAbierta = (ultimoEstado.lecturaLdr > config.umbralLuzPuerta);

  // 3. Leer Temperatura (DHT22)
  float tempLeida = dht.readTemperature();
  if (!isnan(tempLeida)) {
    ultimoEstado.temperatura = tempLeida;
  }

  // 4. Lógica del Ventilador:
  // Si la puerta está abierta se apaga para conservar frío; si está cerrada actúa por temperatura
  if (ultimoEstado.puertaAbierta) {
    ultimoEstado.ventiladorEncendido = false;
  } else {
    ultimoEstado.ventiladorEncendido = (ultimoEstado.temperatura > config.tempObjetivo);
  }
  digitalWrite(PIN_FAN, ultimoEstado.ventiladorEncendido ? HIGH : LOW);

  // 5. Actualizar LCD local
  actualizarPantallaLCD();
}

void evaluarControlLuzPIR() {
  bool hayMovimiento = (digitalRead(PIN_PIR) == HIGH);
  ultimoEstado.movimiento = hayMovimiento;

  if (hayMovimiento) {
    instanteUltimoMovimiento = millis();
    if (!ultimoEstado.luzEncendida) {
      ultimoEstado.luzEncendida = true;
      digitalWrite(PIN_RELE_LUZ, RELE_ON);
      actualizarPantallaLCD();
    }
  } else {
    unsigned long tiempoSinMovMs = millis() - instanteUltimoMovimiento;
    unsigned long limiteMs = (unsigned long)config.tiempoLuzSeg * 1000UL;
    if (ultimoEstado.luzEncendida && (tiempoSinMovMs >= limiteMs)) {
      ultimoEstado.luzEncendida = false;
      digitalWrite(PIN_RELE_LUZ, RELE_OFF);
      actualizarPantallaLCD();
    }
  }
}

// ============================================================================
// 6. SERVIDOR WEB (LittleFS) Y ENDPOINTS API-REST
// ============================================================================
String construirJsonEstado() {
  JsonDocument doc;
  doc["fecha_hora"] = ultimoEstado.fechaHora;

  JsonObject params = doc["parametros"].to<JsonObject>();
  params["temp_objetivo"] = config.tempObjetivo;
  params["umbral_luz_puerta"] = config.umbralLuzPuerta;
  params["tiempo_luz_seg"] = config.tiempoLuzSeg;

  JsonObject sensores = doc["sensores"].to<JsonObject>();
  sensores["temperatura"] = ultimoEstado.temperatura;
  sensores["lectura_ldr"] = ultimoEstado.lecturaLdr;
  sensores["puerta_abierta"] = ultimoEstado.puertaAbierta;
  sensores["movimiento"] = ultimoEstado.movimiento;

  JsonObject actuadores = doc["actuadores"].to<JsonObject>();
  actuadores["ventilador"] = ultimoEstado.ventiladorEncendido;
  actuadores["luz"] = ultimoEstado.luzEncendida;

  String salida;
  serializeJson(doc, salida);
  return salida;
}

void manejarGetIndex() {
  File file = LittleFS.open("/index.html", "r");
  if (!file) {
    server.send(500, "text/plain", "Error: No se encontro /index.html en LittleFS");
    return;
  }
  server.streamFile(file, "text/html");
  file.close();
}

void manejarGetStyles() {
  File file = LittleFS.open("/styles.css", "r");
  if (!file) {
    server.send(404, "text/plain", "Error: No se encontro /styles.css en LittleFS");
    return;
  }
  server.streamFile(file, "text/css");
  file.close();
}

void manejarGetApiEstado() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", construirJsonEstado());
}

void manejarPostApiConfig() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  if (!server.hasArg("plain")) {
    server.send(400, "application/json", "{\"error\":\"Cuerpo JSON requerido\"}");
    return;
  }

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, server.arg("plain"));
  if (error) {
    server.send(400, "application/json", "{\"error\":\"JSON invalido\"}");
    return;
  }

  if (!doc["temp_objetivo"].isNull()) {
    config.tempObjetivo = doc["temp_objetivo"].as<float>();
  }
  if (!doc["umbral_luz_puerta"].isNull()) {
    int umbral = doc["umbral_luz_puerta"].as<int>();
    if (umbral >= 0 && umbral <= 4095) {
      config.umbralLuzPuerta = umbral;
    }
  }
  if (!doc["tiempo_luz_seg"].isNull()) {
    int tiempo = doc["tiempo_luz_seg"].as<int>();
    if (tiempo >= 1 && tiempo <= 3600) {
      config.tiempoLuzSeg = (unsigned int)tiempo;
    }
  }

  // Re-evaluar inmediatamente con los nuevos parámetros
  ejecutarCicloSensado();
  server.send(200, "application/json", construirJsonEstado());
}

// ============================================================================
// 7. SETUP Y LOOP PRINCIPAL (SIN delay())
// ============================================================================
void setup() {
  Serial.begin(115200);

  pinMode(PIN_LDR, INPUT);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_FAN, OUTPUT);
  pinMode(PIN_RELE_LUZ, OUTPUT);

  digitalWrite(PIN_FAN, LOW);
  digitalWrite(PIN_RELE_LUZ, RELE_OFF);

  dht.begin();
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("  CUARTO FRIO   ");
  lcd.setCursor(0, 1);
  lcd.print("Conectando WiFi ");

  if (!LittleFS.begin(true)) {
    Serial.println("Error al montar LittleFS");
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);

  // Registro de rutas Web (LittleFS) y API-REST
  server.on("/", HTTP_GET, manejarGetIndex);
  server.on("/styles.css", HTTP_GET, manejarGetStyles);
  server.on("/api/estado", HTTP_GET, manejarGetApiEstado);
  server.on("/api/config", HTTP_POST, manejarPostApiConfig);
  server.begin();

  // Lectura inicial inmediata
  ejecutarCicloSensado();
}

void loop() {
  // 1. Atender peticiones HTTP (Página Web y API-REST) continuamente
  server.handleClient();

  // 2. Supervisar conexión WiFi y sincronización NTP sin bloquear
  if (timerConexionWiFi.update()) {
    bool conectadoAhora = (WiFi.status() == WL_CONNECTED);
    if (conectadoAhora && !wifiConectadoPrevio) {
      wifiConectadoPrevio = true;
      configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
      Serial.print("WiFi conectado. IP asignada: ");
      Serial.println(WiFi.localIP());
    } else if (!conectadoAhora) {
      wifiConectadoPrevio = false;
    }
  }

  // 3. Control periódico de luz por sensor PIR (cada 250 ms vía NoDelay)
  if (timerControlLuz.update()) {
    evaluarControlLuzPIR();
  }

  // 4. Sensado general de temperatura, puerta, timestamp y LCD (cada 1000 ms vía NoDelay)
  if (timerSensado.update()) {
    ejecutarCicloSensado();
  }
}