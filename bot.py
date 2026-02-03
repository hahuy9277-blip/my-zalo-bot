from dotenv import load_dotenv
load_dotenv()

from config import API_KEY, SECRET_KEY, IMEI, SESSION_COOKIES, PREFIX
from mitaizl import CommandHandler
from zlapi import ZaloAPI
from zlapi.models import Message, ThreadType
from modules.bot_info import *
from modules.da import welcome
from modules.checktt import record_message, handle_checktt_command, set_client, start_scheduler
from modules.tag_conversation import handle_conversational_tag
from modules.math_calculator import get_mitaizl as get_math_handler
from modules.number_tracker import get_mitaizl as get_number_tracker_module
from colorama import Fore, Style, init
import threading
import os
import sys
import re
from datetime import datetime
from flask import Flask # Thêm mới

# --- CẤU HÌNH WEB SERVER CHO RENDER ---
app = Flask('')
@app.route('/')
def home():
    return "Bot Yasuo đang online 24/7!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()
# ---------------------------------------

init(autoreset=True)
from modules.spam import get_mitaizl as get_spam_module
spam_handler = get_spam_module().get('spam')

class Client(ZaloAPI):
    def __init__(self, api_key, secret_key, imei, session_cookies):
        super().__init__(api_key, secret_key, imei=imei, session_cookies=session_cookies)
        handle_bot_admin(self)
        self.version = 1.1
        self.me_name = "Bot by Bơ"
        self.date_update = "26/9/2024"
        self.command_handler = CommandHandler(self)

    def onEvent(self, event_data, event_type):
        welcome(self, event_data, event_type)

    def onMessage(self, mid, author_id, message, message_object, thread_id, thread_type):
        print(f"{Fore.GREEN}{Style.BRIGHT}------------------------------")
        print(f"- Message: {message}")
        print(f"- Author ID: {author_id}")
        print(f"------------------------------{Style.RESET_ALL}")

        if str(author_id) == str(self.uid): return
        if not isinstance(message, str):
            message = getattr(message, "content", str(message))
        
        user_name = message_object.get("dName", "bạn")
        msg_lower = message.lower().strip()

        # Logic xử lý tin nhắn (Giữ nguyên các hàm check của ông)
        def check_exact_keyword(text, keywords):
            for word in keywords:
                pattern = rf"(?<!\w){re.escape(word)}(?!\w)"
                if re.search(pattern, text): return True
            return False

        # --- CÁC CHỨC NĂNG ---
        # 1. Toán học
        math_handler = get_math_handler().get('calculate')
        calc_response = math_handler(message, user_name)
        if calc_response:
            self.send(Message(text=calc_response), thread_id, thread_type)
            return

        # 2. Đối thoại AI (Gemini)
        if handle_conversational_tag(message, message_object, thread_id, thread_type, author_id, self):
            return

        # 3. Ghi nhận tương tác & Checktt
        record_message(message_object, author_id, thread_id)
        
        # 4. Xử lý lệnh Prefix (!)
        try:
            self.command_handler.handle_command(message, author_id, message_object, thread_id, thread_type)
        except Exception as e:
            print(f"[ERROR] {e}")

def schedule_restart(interval_hours=1):
    def restart_check():
        print("[INFO] Tự động Restart để làm mới kết nối...")
        python = sys.executable
        os.execl(python, python, *sys.argv)
    threading.Timer(interval_hours * 3600, restart_check).start()

if __name__ == "__main__":
    keep_alive() # Kích hoạt máy thở cho Render
    client = Client(API_KEY, SECRET_KEY, IMEI, SESSION_COOKIES)
    set_client(client)
    start_scheduler()
    client.listen()
