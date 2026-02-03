import requests
import json
import re
import random
from zlapi.models import Message

# =========================================================
# BẢN SIÊU CẤP - DÙNG CHO RENDER/RAILWAY (6 KEY)
# =========================================================

API_KEYS = [
    "AIzaSyBkweaSw9qqqklFjNRW-5Wat2bgz5VtiOU",
    "AIzaSyDkvIYrk6f5YRdqDqD9c-DhDzkBGyMqO0Y",
    "AIzaSyBFDejHgKTXSSE-NccmAs49rGmyF-Yz5u4",
    "AIzaSyAxXzEaLrcE91QInid1BEb6F9o2vLpgSUs",
    "AIzaSyDXwdpROFF4_QWmZfaImgmcYWIWOBACbxc",
    "AIzaSyDUa2uNagKOA2vhL9GLYqpprtZJwwxLBQs"
]

MODEL_NAME = "gemini-1.5-flash"
SYSTEM_PROMPT = "Bạn là Bot xéo xắc, Gen Z. Trả lời dưới 15 từ. Cà khịa người hỏi."

def ask_gemini_stable(text):
    # Chọn Key ngẫu nhiên để chia tải
    key = random.choice(API_KEYS)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={key}"
    
    payload = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\nUser: {text}"}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"}
        ],
        "generationConfig": {"maxOutputTokens": 100, "temperature": 0.9}
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        return "Lag tí, hỏi lại xem!"
    except:
        return "Mạng mẽo chán đời quá!"

def handle_conversational_tag(message, message_object, thread_id, thread_type, author_id, client):
    if not message_object.mentions: return False
    if not any(m.get('uid') == client.uid for m in message_object.mentions): return False

    user_name = message_object.get("dName", "Bạn")
    content = re.sub(r'@.*? ', '', message, count=1).strip()
    
    if len(content) > 0:
        print(f"[LOG] {user_name} hỏi: {content}")
        reply = ask_gemini_stable(content)
        client.send(Message(text=reply), thread_id, thread_type)
    else:
        client.send(Message(text="Tag làm chi? Solo Yasuo không?"), thread_id, thread_type)
    return True

def get_mitaizl():
    return { "tag_conversation": handle_conversational_tag }