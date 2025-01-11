import os
import json
import asyncio
import sounddevice as sd
from vosk import Model, KaldiRecognizer
from gtts import gTTS
import pygame
import paho.mqtt.client as mqtt

# === CONFIGURATION ===
# MQTT
BROKER = "test.mosquitto.org"  # Broker MQTT
PORT = 1883  # Port MQTT

# Speech Recognition and Audio Settings
MODEL_PATH_THAI = "/home/admin123/Documents/project/vosk-model-th"  # Path ของโมเดลภาษาไทย
RESPONSE_AUDIO_FILE = "response.mp3"  # ไฟล์เสียงตอบกลับ
SAMPLE_RATE = 16000  # อัตราสุ่มตัวอย่างเสียง (16kHz)
FRAME_SIZE = 4000  # ขนาดเฟรมที่ใช้สำหรับการอ่านเสียง

# State Variables
keyword_detected = False
keyword_check = False
keyword_setup = False

# Sensor Values
moisture = "0"
light_intensity = "0"
n = "0"
p = "0"
k = "0"

# === MQTT FUNCTIONS ===
def on_connect(client, userdata, flags, rc):
    """Callback เมื่อเชื่อมต่อกับ MQTT Broker สำเร็จ"""
    print(f"Connected to MQTT Broker with result code {rc}")
    # Subscribe หัวข้อสำหรับเซ็นเซอร์
    topics = [
        "esp32/lux_sensor",
        "esp32/moisture",
        "esp32/n",
        "esp32/p",
        "esp32/k"
    ]
    for topic in topics:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    """Callback เมื่อได้รับข้อความจาก MQTT"""
    global moisture, light_intensity, n, p, k
    # เก็บค่าเซ็นเซอร์ลงตัวแปร
    if msg.topic == "esp32/lux_sensor":
        light_intensity = msg.payload.decode()
    elif msg.topic == "esp32/moisture":
        moisture = msg.payload.decode()
    elif msg.topic == "esp32/n":
        n = msg.payload.decode()
    elif msg.topic == "esp32/p":
        p = msg.payload.decode()
    elif msg.topic == "esp32/k":
        k = msg.payload.decode()

def on_publish(client, userdata, mid):
    """Callback เมื่อส่งข้อความสำเร็จ"""
    print("Message Published")

# สร้าง MQTT Client และตั้งค่า Callback
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.on_publish = on_publish

# เชื่อมต่อ MQTT
client.connect(BROKER, PORT, 60)

# === HELPER FUNCTIONS ===
def load_model(model_path):
    """โหลดโมเดลสำหรับการรู้จำเสียงพูด"""
    if not os.path.exists(model_path):
        print(f"Model path {model_path} does not exist. Please download the model first.")
        exit(1)
    return Model(model_path)

def speak(text, lang='th'):
    """แปลงข้อความเป็นเสียงและบันทึกเป็นไฟล์ MP3"""
    tts = gTTS(text=text, lang=lang)
    tts.save(RESPONSE_AUDIO_FILE)

def play_mp3(file_path):
    """เล่นไฟล์ MP3 และปิดระบบเสียงเมื่อเล่นเสร็จ"""
    pygame.mixer.init()  # เริ่มต้นระบบเสียง
    pygame.mixer.music.load(file_path)  # โหลดไฟล์เสียง
    pygame.mixer.music.play()  # เล่นไฟล์เสียง
    print(f"กำลังเล่นไฟล์: {file_path}")

    # รอจนกว่าเสียงจะเล่นเสร็จ
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)  # รอเล็กน้อยเพื่อลดการใช้งาน CPU

    print("การเล่นเสร็จสิ้น")
    pygame.mixer.music.stop()  # หยุดการเล่นเสียง
    pygame.mixer.quit()  # ปิดระบบเสียง


def pause_mic():
    """หยุดการรับเสียงจากไมโครโฟน"""
    sd.stop()
    print("ไมโครโฟนหยุดรับเสียงแล้ว")

def resume_mic():
    """เริ่มการรับเสียงจากไมโครโฟน"""
    print("ไมโครโฟนเริ่มรับเสียงอีกครั้ง")

async def audio_stream():
    """สตรีมข้อมูลเสียงจากไมโครโฟน"""
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
        while True:
            audio_data, _ = stream.read(FRAME_SIZE)
            yield audio_data.tobytes()

def process_recognition_result(result, lang):
    """ประมวลผลคำสั่งจากการรู้จำเสียงพูด"""
    global keyword_detected, keyword_check, keyword_setup
    text = result.get("text", "").strip()
    if not text:
        return

    print(f"[{lang}]: {text}")

    if lang == "ไทย":
        process_thai_commands(text)

def process_thai_commands(text):
    """ตรวจสอบคำสั่งภาษาไทยและตอบสนอง"""
    global keyword_detected, keyword_check, keyword_setup
    global moisture, light_intensity, n, p, k
    text = text.replace(" ", "")

    if not keyword_detected and "เปิดระบบ" in text:
        keyword_detected = True
        speak("ตินตินพร้อมรับคำสั่งแล้วค่ะ")
        play_mp3(RESPONSE_AUDIO_FILE)
    elif keyword_detected:
        if "แก้ไข" in text:
            speak_and_reset("พร้อมทำการตั้งค่าความชื้นแล้วค่ะ", setup=True)
        elif "เช็ค" in text or "เช็ก" in text or "ตรวจสอบ" in text:
            speak_and_reset("ต้องการตรวจสอบความชื้น, แสง หรือค่าปุ๋ย คะ", check=True)
    elif keyword_check:
        if "แสง" in text:
            speak_and_reset(f"แสงปัจจุบันคือ {light_intensity} ลัมเมนต์ค่ะ", check=False)
        elif "ความชื้น" in text:
            speak_and_reset(f"ความชื้นปัจจุบันคือ {moisture} เปอร์เซ็นต์ค่ะ", check=False)
        elif "ปุ๋ย" in text:
            speak_and_reset(f"ค่าN:{n}% ค่าP:{p}% ค่าK:{k}% ค่ะ", check=False)
    elif keyword_setup:
        setup_humidity(text)

def setup_humidity(text):
    """ตั้งค่าความชื้นตามคำสั่ง"""
    global keyword_setup
    mapping = {
        "ยี่สิบ": 20,
        "สี่สิบ": 40,
        "หกสิบ": 60,
        "แปดสิบ": 80
    }
    for key, value in mapping.items():
        if key in text:
            client.publish("esp32/moisture_percent", str(value))
            speak_and_reset(f"ตั้งค่าความชื้นเป็น {value} เปอร์เซ็นต์แล้วค่ะ", setup=False)
            break

def speak_and_reset(response, check=False, setup=False, lang='th'):
    """พูดข้อความและรีเซ็ตสถานะ"""
    global keyword_detected, keyword_check, keyword_setup
    print(response)
    speak(response, lang=lang)
    pause_mic()  # หยุดไมโครโฟนขณะเล่นเสียง
    play_mp3(RESPONSE_AUDIO_FILE)
    resume_mic()  # เริ่มรับเสียงอีกครั้ง
    keyword_detected = False
    keyword_check = check
    keyword_setup = setup

# === MAIN FUNCTION ===
async def main():
    print("กำลังโหลดโมเดล...")
    model_thai = load_model(MODEL_PATH_THAI)

    recognizer_thai = KaldiRecognizer(model_thai, SAMPLE_RATE)

    print("กรุณาพูด...")

    # เริ่ม MQTT Client ใน asyncio loop
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, client.loop_forever)

    # อ่านข้อมูลเสียงจากไมโครโฟน
    async for audio_bytes in audio_stream():
        if recognizer_thai.AcceptWaveform(audio_bytes):
            result = json.loads(recognizer_thai.Result())
            process_recognition_result(result, "ไทย")

if __name__ == "__main__":
    asyncio.run(main())
