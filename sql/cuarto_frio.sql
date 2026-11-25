CREATE DATABASE IF NOT EXISTS cuarto_frio_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE cuarto_frio_db;

-- Tabla 1: Historial de lecturas de sensores y estado de actuadores
CREATE TABLE IF NOT EXISTS lecturas_sensores (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha_hora_esp32 DATETIME NOT NULL COMMENT 'Marca de tiempo generada por el ESP32 al sensar',
  fecha_hora_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Marca de tiempo de inserción en MySQL',
  temperatura DECIMAL(5,2) NOT NULL COMMENT 'Temperatura en grados Celsius (DHT22)',
  nivel_luz_ldr INT NOT NULL COMMENT 'Valor analógico de fotocelda (0-4095)',
  puerta_abierta TINYINT(1) NOT NULL COMMENT '1 = Abierta, 0 = Cerrada',
  movimiento_detectado TINYINT(1) NOT NULL COMMENT '1 = Movimiento PIR, 0 = Sin movimiento',
  estado_ventilador TINYINT(1) NOT NULL COMMENT '1 = Encendido, 0 = Apagado',
  estado_luz TINYINT(1) NOT NULL COMMENT '1 = Encendida, 0 = Apagada',
  temp_objetivo_vigente DECIMAL(5,2) NOT NULL COMMENT 'Parámetro temp_objetivo al momento de la lectura',
  INDEX idx_fecha_registro (fecha_hora_registro),
  INDEX idx_fecha_esp32 (fecha_hora_esp32)
) ENGINE=InnoDB;

-- Tabla 2: Auditoría de cambios en parámetros configurables
CREATE TABLE IF NOT EXISTS historial_configuracion (
  id INT AUTO_INCREMENT PRIMARY KEY,
  fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  temp_objetivo DECIMAL(5,2) NOT NULL,
  umbral_luz_puerta INT NOT NULL,
  tiempo_luz_seg INT NOT NULL,
  origen VARCHAR(50) NOT NULL DEFAULT 'GUI_PYTHON'
) ENGINE=InnoDB;

-- Registro inicial por defecto
INSERT INTO historial_configuracion (temp_objetivo, umbral_luz_puerta, tiempo_luz_seg, origen)
VALUES (4.00, 2000, 15, 'INICIAL');