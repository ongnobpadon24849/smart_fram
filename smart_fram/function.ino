void callback(char* topic, byte* payload, unsigned int length) {
  payload[length] = '\0';
  String topic_str = topic, payload_str = (char*)payload;
  Serial.println("[" + topic_str + "]: " + payload_str);
  if (topic_str == "esp32/moisture_percent") {
    if (payload_str == "20") {
      moistureValue_percent_compare = 20;
    } else if (payload_str == "40") {
      moistureValue_percent_compare = 40;
    } else if (payload_str == "60") {
      moistureValue_percent_compare = 60;
    } else if (payload_str == "80") {
      moistureValue_percent_compare = 80;
    }
  }
}

void moistureSensor() {
  moistureValue = analogRead(MOISTURE_PIN);
  moistureValue_percent = (moistureValue - 0) * (0 - 100) / (4095 - 0) + 100;
  //  Serial.printf("Moisture: %d Percent: %d\n", moistureValue, moistureValue_percent);
}

void lightSensor() {
  lightIntensity = lightMeter.readLightLevel(); // อ่านค่า Analog จากขา 34
  //  Serial.printf("Light Intensity: %d\n", lightIntensity);
}
