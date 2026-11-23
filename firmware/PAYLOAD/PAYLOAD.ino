/*
Proyecto: Estación portátil de monitoreo para cultivo de Antirrhinum majus
Autores:  Jayder J, Sara G, Isabella T, Mariana C, Paola R, Juan Jose V, Sofia V.
Descripción: Lee los sensores con un intervalo propio para cada grupo y envía la trama $EST
a la Raspberry Pi por USB serial:
  - Luz (PAR y TSL2591), aire (SCD30) y caja (DHT22): se leen cada T_LECTURA.
    PAR y lux se promedian hasta el envío; las lecturas con los LEDs de la cámara encendidos
    no se cuentan, para que el flash no sume luz al DLI ni al fotoperiodo.
  - Sensores de suelo: una ronda cada T_SUELO; sus campos van solo en el envío siguiente a la ronda.
  - Envío a la Raspberry Pi: cada T_ENVIO.
Recibe órdenes de la Raspberry para prender los LEDs de la cámara (MEF de luces):
  {"cmd":"blanco"}  {"cmd":"uv"}  {"cmd":"apagar"}  {"cmd":"ping"}
  Opcional "seg": tiempo máximo encendido, ej. {"cmd":"uv","seg":120} para calibrar la cámara.
Si un sensor I2C no responde, la estación sigue enviando los demás datos, avisa con #ERR,
manda sus campos como nan y lo vuelve a intentar cada 30 s. En la trama, scd y tsl indican
si cada sensor está funcionando (1) o no (0).
*/

// librerias
#include <Wire.h>                            // LUX y CO2
#include "SparkFun_SCD30_Arduino_Library.h"  // CO2
#include <Adafruit_Sensor.h>                 // LUX y DHT22
#include <Adafruit_TSL2591.h>                // TSL lux
#include <ModbusRTU.h>                       // Hum suelo y PAR
#include <DHT.h>                             // Temperatura interna de la caja

// Etiquetado de estados MEF luces (fotos)
#define LUZ_APAGADA 0  // LEDs apagados
#define LUZ_BLANCA 1   // LEDs blancos encendidos
#define LUZ_UV 2       // LED UV encendido

// Bus I2C compartido (SCD30 0x61 + TSL2591 0x29)
#define PIN_SDA 8
#define PIN_SCL 9
#define DIR_SCD30 0x61
#define DIR_TSL2591 0x29

// Bus RS485 compartido (humedad de suelo + PAR)
#define PIN_RX 18
#define PIN_TX 17

// DHT22 y ventilador de la caja
#define PIN_DHT 4
#define PIN_VENT 5
#define DHTTYPE DHT22
#define T_ON 25.0   // C, prende el ventilador
#define T_OFF 22.0  // C, apaga el ventilador

// LEDs de la cámara (MOSFET)
#define PIN_LED_BLANCO 6  // 2 LEDs blancos
#define PIN_LED_UV 10      // LED UV

// Velocidad de comunicación
#define VELOCIDAD_I2C 50000  // Hz, el SCD30 necesita I2C lento
#define T_ESPERA_I2C 200     // ms máximos de espera del bus I2C (el SCD30 lo frena hasta 150 ms)
#define BAUDIOS_485 4800     // todos los equipos del bus deben compartir baudios
#define BAUDIOS_RASPI 115200 // serial hacia la Raspberry Pi

// Direcciones Modbus
#define ID_SENSOR_SUELO_1 4
#define ID_SENSOR_SUELO_2 2
#define ID_SENSOR_SUELO_3 3
#define ID_SENSOR_PAR_1 1

// Registros sensor de suelo JXCT JXBS-3001-RS (cada registro se lee por separado)
#define REG_PH 0x0006    // 0.01 pH
#define REG_HUM 0x0012   // 0.1 %
#define REG_TEMP 0x0013  // 0.1 C, con signo
#define REG_CE 0x0015    // 1 uS/cm

// Registro sensor PAR
#define REG_PAR 0x0000
#define PAR_USA_REG_ENTRADA false  // true = funcion 0x04, false = 0x03

// Tiempos de lectura y envío (cambiar aquí según el cultivo y el sitio)
#define T_LECTURA 10000         // ms entre lecturas de luz, aire y caja (el ventilador se controla con este ritmo)
#define T_ENVIO 60000           // ms entre envios del payload a la Raspi (PAR y lux van promediados)
#define T_SUELO 900000          // ms entre rondas de los sensores de suelo (15 min, sustrato; en campo 5 min)
#define T_PRIMER_ENVIO 15000    // ms después de arrancar para el primer envío

// Otros tiempos
#define INTERVALO_PETICION 100  // ms entre peticiones Modbus seguidas
#define T_ESTABILIZAR 500       // ms con la luz encendida antes de avisar que está lista
#define T_MAX_LUZ 10000         // ms máximo encendida si no llega la orden de apagar
#define T_MAX_MANUAL 300000     // ms máximo que se acepta en "seg" (5 min)
#define T_REINTENTO_I2C 30000   // ms entre intentos de reconectar un sensor I2C caído
#define T_SIN_DATOS_SCD30 30000 // ms sin datos nuevos del SCD30 para darlo por caído
#define LARGO_MAX_ORDEN 100     // caracteres máximos de una orden por serial

// Objetos
SCD30 sensorCO2;  // para leer el sensor SCD30
Adafruit_TSL2591 sensorLux = Adafruit_TSL2591(2591);
ModbusRTU modbus;
DHT sensorCaja(PIN_DHT, DHTTYPE);  // temperatura interna de la caja

// Variables que se leen en el bus RS485
enum Variable : uint8_t { VAR_PH, VAR_HUM, VAR_TEMP, VAR_CE, VAR_PAR };

// Una peticion = un sensor + un registro
struct Peticion {
  uint8_t idSensor;
  uint16_t registro;
  Variable variable;
  uint8_t indice;  // sensor de suelo 0, 1 o 2; no se usa en PAR
};

// Tabla de peticiones: primero las de suelo, la de PAR siempre de última
const Peticion peticiones[] = {
  { ID_SENSOR_SUELO_1, REG_PH,   VAR_PH,   0 },
  { ID_SENSOR_SUELO_1, REG_HUM,  VAR_HUM,  0 },
  { ID_SENSOR_SUELO_1, REG_TEMP, VAR_TEMP, 0 },
  { ID_SENSOR_SUELO_1, REG_CE,   VAR_CE,   0 },

  { ID_SENSOR_SUELO_2, REG_PH,   VAR_PH,   1 },
  { ID_SENSOR_SUELO_2, REG_HUM,  VAR_HUM,  1 },
  { ID_SENSOR_SUELO_2, REG_TEMP, VAR_TEMP, 1 },
  { ID_SENSOR_SUELO_2, REG_CE,   VAR_CE,   1 },

  { ID_SENSOR_SUELO_3, REG_PH,   VAR_PH,   2 },
  { ID_SENSOR_SUELO_3, REG_HUM,  VAR_HUM,  2 },
  { ID_SENSOR_SUELO_3, REG_TEMP, VAR_TEMP, 2 },
  { ID_SENSOR_SUELO_3, REG_CE,   VAR_CE,   2 },

  { ID_SENSOR_PAR_1,   REG_PAR,  VAR_PAR,  0 },
};
const uint8_t NUM_PETICIONES = sizeof(peticiones) / sizeof(peticiones[0]);
const uint8_t IDX_PAR = NUM_PETICIONES - 1;  // la petición de PAR es la última de la tabla

// Variables I2C (NAN = sin lectura valida)
float co2 = NAN;
float temperatura = NAN;
float humedad = NAN;
float lux = NAN;

// Estado de los sensores I2C (true = funcionando)
bool scd30Ok = false;
bool tslOk = false;

// Variables caja (DHT22 y ventilador)
float temperaturaCaja = NAN;
bool ventiladorOn = false;

// Variables RS485 (NAN = sin lectura valida)
float par = NAN;
float humedadSuelo[3]       = { NAN, NAN, NAN };
float temperaturaSuelo[3]   = { NAN, NAN, NAN };
float conductividadSuelo[3] = { NAN, NAN, NAN };
float phSuelo[3]            = { NAN, NAN, NAN };

// Promedios de luz entre envíos
float sumaPar = 0;
uint16_t lecturasPar = 0;
float sumaLux = 0;
uint16_t lecturasLux = 0;
float luxPromedio = NAN;

// Control del bus Modbus
uint16_t valorCrudo = 0;
uint8_t siguienteSuelo = 0;   // siguiente petición de la ronda de suelo
uint8_t peticionActiva = 0;
bool rondaSuelo = true;       // arranca con una ronda para tener datos de suelo pronto
bool pedirPar = false;        // true cuando toca leer el PAR
bool sueloListo = false;      // true cuando terminó una ronda y falta enviarla

// Temporizadores
unsigned long tiempoPeticion = 0;
unsigned long tiempoLectura = 0;
unsigned long tiempoEnvio = 0;
unsigned long tiempoSuelo = 0;
unsigned long tiempoReintentoI2C = 0;
unsigned long tiempoUltimoCO2 = 0;

// Variables MEF luces
unsigned int estadoLuces = LUZ_APAGADA;  // estado actual, inicia apagado
unsigned int ordenLuces = LUZ_APAGADA;   // última orden recibida desde la Raspi
bool hayOrden = false;                   // true cuando llega una orden nueva
bool avisoListo = false;                 // true cuando ya se avisó que la luz está lista
unsigned long tiniLuces = 0;             // tiempo inicial del estado de luces
unsigned long tMaxLuz = T_MAX_LUZ;       // tiempo máximo encendida para la orden actual
String orden = "";                       // texto de la orden que va llegando por serial

// subrutinas y funciones

// Se ejecuta cuando llega la respuesta Modbus: solo guarda el dato
bool guardarLectura(Modbus::ResultCode evento, uint16_t idTransaccion, void* datos) {
  const Peticion& p = peticiones[peticionActiva];
  bool lecturaValida = (evento == Modbus::EX_SUCCESS);

  switch (p.variable) {
    case VAR_PH:   phSuelo[p.indice] = lecturaValida ? valorCrudo / 100.0 : NAN; break;
    case VAR_HUM:  humedadSuelo[p.indice] = lecturaValida ? valorCrudo / 10.0 : NAN; break;
    case VAR_TEMP: temperaturaSuelo[p.indice] = lecturaValida ? (int16_t)valorCrudo / 10.0 : NAN; break;
    case VAR_CE:   conductividadSuelo[p.indice] = lecturaValida ? (float)valorCrudo : NAN; break;
    case VAR_PAR:
      // con los LEDs de la cámara encendidos no se cuenta la lectura
      if (lecturaValida && estadoLuces == LUZ_APAGADA) {
        sumaPar += valorCrudo;
        lecturasPar++;
      }
      break;
  }

  // la última petición de suelo cierra la ronda
  if (peticionActiva == IDX_PAR - 1) sueloListo = true;
  return true;
}

// Lanza una petición Modbus de la tabla; devuelve true si el bus la aceptó
bool lanzarPeticion(uint8_t i) {
  const Peticion& p = peticiones[i];
  peticionActiva = i;

  uint16_t idTransaccion;
  if (p.variable == VAR_PAR && PAR_USA_REG_ENTRADA) {
    idTransaccion = modbus.readIreg(p.idSensor, p.registro, &valorCrudo, 1, guardarLectura);
  } else {
    idTransaccion = modbus.readHreg(p.idSensor, p.registro, &valorCrudo, 1, guardarLectura);
  }
  return idTransaccion != 0;
}

// Revisa si un sensor responde en el bus I2C
bool respondeI2C(uint8_t direccion) {
  Wire.beginTransmission(direccion);
  return Wire.endTransmission() == 0;
}

// Intenta iniciar el SCD30; si no responde, avisa y el programa sigue
void iniciarSCD30() {
  if (sensorCO2.begin()) {
    sensorCO2.setMeasurementInterval(2);  // intervalo de medicion (s)
    scd30Ok = true;
    tiempoUltimoCO2 = millis();
    Serial.println("#OK,SCD30 detectado");
  } else {
    scd30Ok = false;
    Serial.println("#ERR,SCD30 no detectado");
  }
}

// Intenta iniciar el TSL2591; si no responde, avisa y el programa sigue
void iniciarTSL2591() {
  if (sensorLux.begin(&Wire)) {
    sensorLux.setGain(TSL2591_GAIN_LOW);  // configuracion para luz intensa
    sensorLux.setTiming(TSL2591_INTEGRATIONTIME_100MS);
    tslOk = true;
    Serial.println("#OK,TSL2591 detectado");
  } else {
    tslOk = false;
    Serial.println("#ERR,TSL2591 no detectado");
  }
}

// Cada 30 s vuelve a intentar los sensores I2C que estén caídos
void reintentarSensoresI2C() {
  if (scd30Ok && tslOk) return;
  if (millis() - tiempoReintentoI2C < T_REINTENTO_I2C) return;
  tiempoReintentoI2C = millis();

  if (!scd30Ok) iniciarSCD30();
  if (!tslOk) iniciarTSL2591();
}

// Lee CO2, temperatura y humedad del SCD30 (NAN si no funciona)
// Al SCD30 no se le hace la consulta de presencia: si se desconecta, deja de entregar datos
void leerSCD30() {
  if (scd30Ok) {
    if (sensorCO2.dataAvailable()) {
      co2 = sensorCO2.getCO2();
      temperatura = sensorCO2.getTemperature();
      humedad = sensorCO2.getHumidity();
      tiempoUltimoCO2 = millis();
    } else if (millis() - tiempoUltimoCO2 >= T_SIN_DATOS_SCD30) {
      // responde pero no entrega datos nuevos: no se reenvía un valor viejo
      scd30Ok = false;
      Serial.println("#ERR,SCD30 sin datos nuevos");
    }
  }

  if (!scd30Ok) {
    co2 = NAN;
    temperatura = NAN;
    humedad = NAN;
  }
}

// Lee el TSL2591 y guarda la iluminancia (NAN si se satura o no funciona)
void leerTSL2591() {
  if (tslOk && !respondeI2C(DIR_TSL2591)) {
    tslOk = false;
    Serial.println("#ERR,TSL2591 desconectado");
  }

  if (!tslOk) {
    lux = NAN;
    return;
  }

  // leer ambos canales opticos
  uint32_t lectura = sensorLux.getFullLuminosity();
  uint16_t infrarrojo = lectura >> 16;
  uint16_t espectroCompleto = lectura & 0xFFFF;

  // Calcular iluminancia estimada
  float valor = sensorLux.calculateLux(espectroCompleto, infrarrojo);

  // Detectar saturacion o lectura no valida
  if (espectroCompleto == 0xFFFF || infrarrojo == 0xFFFF || valor < 0) {
    lux = NAN;
  } else {
    lux = valor;
  }

  // se suma al promedio solo con los LEDs de la cámara apagados
  if (!isnan(lux) && estadoLuces == LUZ_APAGADA) {
    sumaLux += lux;
    lecturasLux++;
  }
}

// Calcula los promedios de PAR y lux desde el último envío y los reinicia
void calcularPromediosLuz() {
  par = lecturasPar > 0 ? sumaPar / lecturasPar : NAN;
  luxPromedio = lecturasLux > 0 ? sumaLux / lecturasLux : NAN;
  sumaPar = 0;
  lecturasPar = 0;
  sumaLux = 0;
  lecturasLux = 0;
}

// Lee el DHT22 y prende/apaga el ventilador con histeresis
void controlarVentilador() {
  temperaturaCaja = sensorCaja.readTemperature();
  if (isnan(temperaturaCaja)) return;  // lectura fallida, no cambia el ventilador

  if (!ventiladorOn && temperaturaCaja >= T_ON) {
    ventiladorOn = true;
    digitalWrite(PIN_VENT, HIGH);
  } else if (ventiladorOn && temperaturaCaja <= T_OFF) {
    ventiladorOn = false;
    digitalWrite(PIN_VENT, LOW);
  }
}

// Agrega ",clave=valor" al payload, o ",clave=nan" si no hay lectura valida
void agregarCampo(String& payload, const char* clave, float valor, int decimales) {
  payload += ',';
  payload += clave;
  payload += '=';
  if (isnan(valor)) {
    payload += "nan";
  } else {
    payload += String(valor, decimales);
  }
}

// Arma la trama: aire, luz y caja siempre; suelo solo si terminó una ronda
String construirPayload() {
  String payload = "$EST";

  // I2C y caja
  agregarCampo(payload, "co2",  co2, 0);
  agregarCampo(payload, "ta",   temperatura, 1);
  agregarCampo(payload, "hra",  humedad, 1);
  agregarCampo(payload, "lux",  luxPromedio, 1);
  agregarCampo(payload, "par",  par, 1);
  agregarCampo(payload, "tc",   temperaturaCaja, 1);
  agregarCampo(payload, "vent", ventiladorOn ? 1 : 0, 0);
  agregarCampo(payload, "luz",  estadoLuces, 0);
  agregarCampo(payload, "scd",  scd30Ok ? 1 : 0, 0);
  agregarCampo(payload, "tsl",  tslOk ? 1 : 0, 0);

  // Sensores de suelo (s1, s2, s3), solo cuando hay una ronda nueva
  if (sueloListo) {
    char clave[8];
    for (uint8_t i = 0; i < 3; i++) {
      snprintf(clave, sizeof(clave), "s%uh", i + 1);
      agregarCampo(payload, clave, humedadSuelo[i], 1);
      snprintf(clave, sizeof(clave), "s%ut", i + 1);
      agregarCampo(payload, clave, temperaturaSuelo[i], 1);
      snprintf(clave, sizeof(clave), "s%uce", i + 1);
      agregarCampo(payload, clave, conductividadSuelo[i], 0);
      snprintf(clave, sizeof(clave), "s%uph", i + 1);
      agregarCampo(payload, clave, phSuelo[i], 2);
    }
    sueloListo = false;
  }

  return payload;
}

// Cambia el estado de la MEF de luces y lo reporta a la Raspi
void cambiarEstadoLuces(unsigned int nuevo) {
  estadoLuces = nuevo;
  tiniLuces = millis();
  avisoListo = false;
  if (nuevo == LUZ_APAGADA) Serial.println("Estado: LUZ_APAGADA");
  if (nuevo == LUZ_BLANCA) Serial.println("Estado: LUZ_BLANCA");
  if (nuevo == LUZ_UV) Serial.println("Estado: LUZ_UV");
}

// Interpreta la orden recibida desde la Raspi
void procesarOrden() {
  if (orden.indexOf("ping") >= 0) {
    Serial.println("#OK,ping");
    return;
  }

  if (orden.indexOf("blanco") >= 0) {
    ordenLuces = LUZ_BLANCA;
  } else if (orden.indexOf("uv") >= 0) {
    ordenLuces = LUZ_UV;
  } else if (orden.indexOf("apagar") >= 0) {
    ordenLuces = LUZ_APAGADA;
  } else {
    Serial.println("#ERR,orden desconocida");
    return;
  }

  // Tiempo máximo encendida: 10 s por defecto, o el que llegue en "seg"
  tMaxLuz = T_MAX_LUZ;
  int i = orden.indexOf("\"seg\":");
  if (i >= 0) {
    tMaxLuz = orden.substring(i + 6).toInt() * 1000UL;
    if (tMaxLuz == 0 || tMaxLuz > T_MAX_MANUAL) tMaxLuz = T_MAX_MANUAL;
  }
  hayOrden = true;
}

// Lee lo que llega por serial; cada línea es una orden
void leerOrdenes() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      procesarOrden();
      orden = "";
    } else if (c != '\r') {
      orden += c;
      if (orden.length() > LARGO_MAX_ORDEN) orden = "";  // descarta texto sin fin de línea
    }
  }
}

// MEF de luces: blanco y UV nunca se prenden al mismo tiempo
void MEF_Luces() {
  unsigned long trel = millis() - tiniLuces;

  switch (estadoLuces) {
    case LUZ_APAGADA:
      // 1. Estado de las salidas físicas
      digitalWrite(PIN_LED_BLANCO, LOW);
      digitalWrite(PIN_LED_UV, LOW);

      // 2. Calculo de variables internas
      // nada que calcular

      // 3. Preguntas de transición
      if (hayOrden) {
        hayOrden = false;
        if (ordenLuces != LUZ_APAGADA) cambiarEstadoLuces(ordenLuces);
      }
      break;

    case LUZ_BLANCA:
      // 1. Estado de las salidas físicas
      digitalWrite(PIN_LED_BLANCO, HIGH);
      digitalWrite(PIN_LED_UV, LOW);

      // 2. Calculo de variables internas
      if (!avisoListo && trel >= T_ESTABILIZAR) {
        Serial.println("#OK,luz lista");  // la Raspi ya puede tomar la foto
        avisoListo = true;
      }

      // 3. Preguntas de transición
      if (hayOrden) {
        hayOrden = false;
        cambiarEstadoLuces(ordenLuces);
      } else if (trel >= tMaxLuz) {
        Serial.println("#ERR,luz apagada por tiempo maximo");
        cambiarEstadoLuces(LUZ_APAGADA);
      }
      break;

    case LUZ_UV:
      // 1. Estado de las salidas físicas
      digitalWrite(PIN_LED_BLANCO, LOW);
      digitalWrite(PIN_LED_UV, HIGH);

      // 2. Calculo de variables internas
      if (!avisoListo && trel >= T_ESTABILIZAR) {
        Serial.println("#OK,luz lista");  // la Raspi ya puede tomar la foto
        avisoListo = true;
      }

      // 3. Preguntas de transición
      if (hayOrden) {
        hayOrden = false;
        cambiarEstadoLuces(ordenLuces);
      } else if (trel >= tMaxLuz) {
        Serial.println("#ERR,luz apagada por tiempo maximo");
        cambiarEstadoLuces(LUZ_APAGADA);
      }
      break;
  }
}

// setup
// Config
void setup() {
  // 0. LEDs de la cámara apagados desde el arranque
  pinMode(PIN_LED_BLANCO, OUTPUT);
  pinMode(PIN_LED_UV, OUTPUT);
  digitalWrite(PIN_LED_BLANCO, LOW);
  digitalWrite(PIN_LED_UV, LOW);

  // 1. Iniciar comunicacion serial con la Raspi
  Serial.begin(BAUDIOS_RASPI);
  delay(1000);

  // 2. Iniciar bus I2C y bajar la velocidad
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(VELOCIDAD_I2C);
  Wire.setTimeOut(T_ESPERA_I2C);

  // 3. Iniciar sensor SCD30 (CO2, temperatura, humedad) sin bloquear
  iniciarSCD30();

  // 4. Iniciar sensor TSL2591 (lux) sin bloquear
  iniciarTSL2591();

  // 5. Iniciar bus RS485 (suelo y PAR)
  Serial2.begin(BAUDIOS_485, SERIAL_8N1, PIN_RX, PIN_TX);
  modbus.begin(&Serial2);
  modbus.master();

  // 6. Iniciar DHT22 y ventilador (apagado al arrancar)
  pinMode(PIN_VENT, OUTPUT);
  digitalWrite(PIN_VENT, LOW);
  sensorCaja.begin();

  Serial.println("#OK,estacion lista");
  Serial.println("Estado: LUZ_APAGADA");

  // 7. Iniciar temporizadores (el primer envío sale a los T_PRIMER_ENVIO)
  tiempoPeticion = millis();
  tiempoLectura = millis() - T_LECTURA;
  tiempoEnvio = millis() - T_ENVIO + T_PRIMER_ENVIO;
  tiempoSuelo = millis();
  tiniLuces = millis();
  tiempoReintentoI2C = millis();
}

// Exec
void loop() {
  unsigned long tiempoActual = millis();

  // 0. Órdenes de la Raspi y MEF de luces
  leerOrdenes();
  MEF_Luces();

  // 1. Cada T_LECTURA: lee I2C y DHT22, controla el ventilador y pide un PAR
  if (tiempoActual - tiempoLectura >= T_LECTURA) {
    tiempoLectura = tiempoActual;

    reintentarSensoresI2C();
    leerSCD30();
    leerTSL2591();
    controlarVentilador();
    pedirPar = true;
  }

  // 2. Cada T_SUELO: empieza una ronda de los sensores de suelo
  if (tiempoActual - tiempoSuelo >= T_SUELO) {
    tiempoSuelo = tiempoActual;
    rondaSuelo = true;
    siguienteSuelo = 0;
  }

  // 3. Lanza una peticion Modbus cuando el bus esta libre (el PAR tiene prioridad)
  if (tiempoActual - tiempoPeticion >= INTERVALO_PETICION && !modbus.slave()) {
    if (pedirPar) {
      if (lanzarPeticion(IDX_PAR)) pedirPar = false;
    } else if (rondaSuelo) {
      if (lanzarPeticion(siguienteSuelo)) {
        siguienteSuelo++;
        if (siguienteSuelo >= IDX_PAR) {
          siguienteSuelo = 0;
          rondaSuelo = false;
        }
      }
    }
    tiempoPeticion = tiempoActual;
  }

  // 4. Cada T_ENVIO: promedia la luz y envia el payload a la Raspi
  if (tiempoActual - tiempoEnvio >= T_ENVIO) {
    tiempoEnvio = tiempoActual;

    calcularPromediosLuz();
    Serial.println(construirPayload());
  }

  modbus.task();  // Siempre llamar para manejar la comunicacion Modbus
}
