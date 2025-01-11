#include <WiFi.h>
#include <PubSubClient.h>

#include "ETT_ModbusRTU.h"
#include <HardwareSerial.h>

#include <NTPClient.h>

#include <BH1750.h>
#include <Wire.h>

#define SerialRS485_RX_PIN    26  //RO
#define SerialRS485_TX_PIN    27  //DI
#define RS485_DIRECTION_PIN   25  //DE,RE
#define RS485_RXD_SELECT      LOW
#define RS485_TXD_SELECT      HIGH

#define WIFI_STA_NAME "Noppadon_host"
#define WIFI_STA_PASS "88888888"
#define MQTT_SERVER   "test.mosquitto.org"
#define MQTT_PORT     1883
#define MQTT_NAME     "ESP32"

#define MOISTURE_PIN          33

#define RELAY_PIN_1           32
#define RELAY_PIN_2           14

#define LIGHT_PIN             34

Modbus master(0, Serial2, RS485_DIRECTION_PIN);  // กำหนด Modbus RTU ผ่าน Serial2 (RS485)
uint16_t au16dataSlave2[3];  // Buffer สำหรับเก็บข้อมูล SOIL NPK
modbus_t telegram[1];        // กำหนด Modbus Telegram 1 ตัว

int16_t moistureValue = 0;
int16_t moistureValue_percent = 0;
int16_t moistureValue_percent_compare = 20;

float lightIntensity = 0;
float lightIntensity_compare = 80;

uint32_t time_send = 0;
uint32_t time_print = 0;

float soil_n, soil_p, soil_k;

const char *ntpServer = "pool.ntp.org";
const long  utcOffsetInSeconds = 25200;

bool timeConditionMet = false;

BH1750 lightMeter;

WiFiClient client;
PubSubClient mqtt(client);

WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, ntpServer, utcOffsetInSeconds);

void setup() {
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(WIFI_STA_NAME);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_STA_NAME, WIFI_STA_PASS);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());

  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setCallback(callback);

  pinMode(RELAY_PIN_1, OUTPUT);
  pinMode(RELAY_PIN_2, OUTPUT);
  pinMode(LIGHT_PIN, INPUT);

  pinMode(RS485_DIRECTION_PIN, OUTPUT);
  digitalWrite(RS485_DIRECTION_PIN, RS485_RXD_SELECT);

  Serial.begin(9600);  // Serial Debug
  Serial2.begin(9600, SERIAL_8N1, SerialRS485_RX_PIN, SerialRS485_TX_PIN);

  Serial.println("SOIL NPK SENSOR SETUP...");

  // ตั้งค่า Modbus Telegram
  telegram[0].u8id = 20;              // Slave ID ของเซ็นเซอร์ SOIL NPK
  telegram[0].u8fct = 3;              // Function code (Read Holding Registers)
  telegram[0].u16RegAdd = 30;         // Start address ของข้อมูลในเซ็นเซอร์
  telegram[0].u16CoilsNo = 3;         // จำนวน Register ที่จะอ่าน (N, P, K)
  telegram[0].au16reg = au16dataSlave2;  // ชี้ไปยัง Buffer

  master.begin(Serial2);  // เริ่มต้น Modbus Master
  master.setTimeOut(3000); // Timeout 3 วินาที

  Wire.begin();
  lightMeter.begin();

  timeClient.begin();
  timeClient.update();
  String currentTime = timeClient.getFormattedTime();
  if (currentTime >= "06:00:00" && currentTime <= "21:59:00") timeConditionMet = true;
  if (currentTime >= "22:00:00" || currentTime <= "05:59:00") timeConditionMet = false;
  Serial.println(timeConditionMet);
}

void loop() {
  static uint8_t u8state = 0;
  static unsigned long u32wait;

  switch (u8state) {
    case 0:
      master.query(telegram[0]);
      u8state++;
      break;

    case 1:
      if (master.poll()) {
        soil_n = au16dataSlave2[0];  // ค่า Nitrogen
        soil_p = au16dataSlave2[1];  // ค่า Phosphorus
        soil_k = au16dataSlave2[2];  // ค่า Potassium

        u8state = 0;
        u32wait = millis() + 1000;
      }
      break;
  }

  if (millis() > u32wait && u8state == 0) {
    u8state = 0;
  }

  moistureSensor();
  lightSensor();

  if (millis() - time_print >= 1000) {
    Serial.printf("moistureValue_percent_compare: %d\n", moistureValue_percent_compare);
    Serial.printf("Soil N: %.2f, P: %.2f, K: %.2f\n", soil_n, soil_p, soil_k);
    Serial.printf("Moisture: %d Percent: %d\n", moistureValue, moistureValue_percent);
    Serial.printf("Light Intensity: %.2f\n", lightIntensity);
    time_print = millis();
  }

  timeClient.update();
  String currentTime = timeClient.getFormattedTime();
  //  Serial.println(timeClient.getFormattedTime());
  if (currentTime == "06:00:00" && timeConditionMet == false) {
    timeConditionMet = true;
  }
  else if (currentTime == "22:00:00" && timeConditionMet == true) {
    timeConditionMet = false;
  }

  if (timeConditionMet) {
    digitalWrite(RELAY_PIN_1, moistureValue_percent < moistureValue_percent_compare ? HIGH : LOW);
    digitalWrite(RELAY_PIN_2, lightIntensity < lightIntensity_compare ? HIGH : LOW);
  } else {
    digitalWrite(RELAY_PIN_1, LOW);
    digitalWrite(RELAY_PIN_2, LOW);
  }

  if (millis() - time_send >= 5000) {
    mqtt.publish("esp32/moisture", String(moistureValue_percent).c_str());
    mqtt.publish("esp32/lux_sensor", String(lightIntensity).c_str());
    mqtt.publish("esp32/n", String(soil_n).c_str());
    mqtt.publish("esp32/p", String(soil_p).c_str());
    mqtt.publish("esp32/k", String(soil_k).c_str());
    time_send = millis();
  }

  if (mqtt.connected() == false) {
    Serial.print("MQTT connection... ");
    if (mqtt.connect(MQTT_NAME)) {
      Serial.println("connected");
      mqtt.subscribe("esp32/moisture_percent");
    } else {
      Serial.println("failed");
      delay(5000);
    }
  } else {
    mqtt.loop();
  }
}
