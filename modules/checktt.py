import re
import time
import threading
import json
import os
from datetime import datetime, timedelta
import schedule  # pip install schedule
from zlapi.models import Message, ThreadType
from modules.user_info import register_user, load_user_info

# Đường dẫn file lưu trữ dữ liệu thống kê
STATS_FILE = "message_stats.json"

# Cấu trúc dữ liệu thống kê được chia theo ngày và tuần
message_stats = {}

# Định nghĩa ID của bot
BOT_ID = "770810507108566189"  # Thay bằng ID thực tế của bot

# Danh sách ID của Admin
ADMIN_IDS = ["9123173293216833155", "1874166068975395869", "4544068758699002896"]

# Biến global để lưu đối tượng client (đã được khởi tạo từ bên ngoài)
global_client = None

def set_client(client_obj):
    global global_client
    global_client = client_obj

def save_stats():
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(message_stats, f, ensure_ascii=False, indent=2)

def load_stats():
    global message_stats
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            message_stats = json.load(f)
    else:
        message_stats = {}

load_stats()

def get_daily_storage_key(dt=None):
    """Trả về key lưu trữ theo định dạng YYYY-MM-DD."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d")

def get_weekly_storage_key(dt=None):
    """Trả về key lưu trữ theo định dạng YYYY-WW (ISO week)."""
    if dt is None:
        dt = datetime.now()
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year}-{iso_week:02d}"

def record_message(message_object, author_id, thread_id):
    """
    Ghi nhận số tin nhắn của từng thành viên cho một nhóm chat.
    """
    global message_stats
    if str(author_id) == BOT_ID:
        # print("[DEBUG] record_message: Bỏ qua tin nhắn của bot.")
        return

    register_user(message_object, author_id, global_client)

    user_id = str(author_id)
    dname = message_object.get("dName", "")
    if not dname or dname.strip().lower() == "vy":
        content = message_object.get("content", "")
        m = re.search(r"📩\s*(.+?)\s+đã gửi", content)
        if m:
            user_name = m.group(1).strip()
        else:
            user_name = f"User {user_id}"
    else:
        user_name = dname.strip()

    # print(f"[DEBUG] record_message: thread_id = {thread_id}, user_id = {user_id}, user_name = {user_name}")

    if thread_id not in message_stats or not isinstance(message_stats[thread_id], dict):
        message_stats[thread_id] = {"daily": {}, "weekly": {}}

    day_key = get_daily_storage_key()
    week_key = get_weekly_storage_key()

    if day_key not in message_stats[thread_id]["daily"]:
        message_stats[thread_id]["daily"][day_key] = {}
    if week_key not in message_stats[thread_id]["weekly"]:
        message_stats[thread_id]["weekly"][week_key] = {}

    if user_id in message_stats[thread_id]["daily"][day_key]:
        message_stats[thread_id]["daily"][day_key][user_id]['count'] += 1
    else:
        message_stats[thread_id]["daily"][day_key][user_id] = {'name': user_name, 'count': 1}

    if user_id in message_stats[thread_id]["weekly"][week_key]:
        message_stats[thread_id]["weekly"][week_key][user_id]['count'] += 1
    else:
        message_stats[thread_id]["weekly"][week_key][user_id] = {'name': user_name, 'count': 1}

    save_stats()

def generate_statistics_text(thread_id, period="daily", mode="current"):
    """
    Sinh nội dung tin nhắn thống kê cho một nhóm chat.
    """
    if period == "daily":
        if mode == "previous":
            dt = datetime.now() - timedelta(days=1)
        else:
            dt = datetime.now()
        storage_key = dt.strftime("%Y-%m-%d")
        header_date = dt.strftime("%d/%m/%Y")
        header = f"📊 Thống kê tin nhắn ngày {header_date}:\n"
        stats = message_stats.get(thread_id, {}).get("daily", {}).get(storage_key, {})
    elif period == "weekly":
        if mode == "previous":
            dt = datetime.now() - timedelta(weeks=1)
        else:
            dt = datetime.now()
        iso_year, iso_week, _ = dt.isocalendar()
        storage_key = f"{iso_year}-{iso_week:02d}"
        header = f"📊 Báo cáo tin nhắn Tuần {iso_week:02d} - {iso_year}:\n"
        stats = message_stats.get(thread_id, {}).get("weekly", {}).get(storage_key, {})
    else:
        header = ""
        stats = {}

    if not stats:
        return header + "Không có tin nhắn từ các thành viên có dữ liệu."

    if BOT_ID in stats:
        del stats[BOT_ID]

    positive = [(uid, info) for uid, info in stats.items() if info.get("count", 0) > 0]

    result = ""
    if positive:
        # Logic riêng cho thread cũ 1311...
        if period == "weekly" and str(thread_id) == "1311505722605591852":
            filtered = [(uid, info) for uid, info in positive if info["count"] >= 50]
            if filtered:
                filtered.sort(key=lambda x: x[1]["count"], reverse=True)
                ranking_lines = [f"{i+1}. {info['name']}: {info['count']} tin nhắn" for i, (uid, info) in enumerate(filtered)]
                result = header + "\n".join(ranking_lines)
            else:
                result = header + "Không có thành viên nào có từ 50 tin nhắn."
        else:
            # Logic mặc định cho các thread khác (bao gồm thread mới)
            sorted_positive = sorted(positive, key=lambda x: x[1]["count"], reverse=True)
            ranking_lines = [f"{i+1}. {info['name']}: {info['count']} tin nhắn" for i, (uid, info) in enumerate(sorted_positive)]
            result = header + "\n".join(ranking_lines)
    else:
        result = header + "Không có tin nhắn từ các thành viên có dữ liệu."

    return result

def handle_checktt_command(message, message_object, thread_id, thread_type, author_id, client):
    """
    Xử lý lệnh thống kê tin nhắn (!checktt ...).
    """
    global message_stats
    if str(author_id) not in ADMIN_IDS:
        client.sendMessage(Message(text="🚫 Bạn không có quyền sử dụng lệnh này!"), thread_id, thread_type)
        return

    # ----- Xử lý lệnh lday (daily previous) -----
    if message.strip().lower().startswith("!checktt lday"):
        tokens = message.strip().split()
        if len(tokens) == 2:
            day_key = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            stats = message_stats.get(thread_id, {}).get("daily", {}).get(day_key, {})
            target_user_id = str(author_id)
            target_user_name = message_object.get("dName", f"User {author_id}")
            count = stats.get(target_user_id, {}).get("count", 0)
            response_text = f"📩 {target_user_name} đã gửi {count} tin nhắn ngày hôm qua."
            client.sendMessage(Message(text=response_text), thread_id, thread_type)
            return
        elif len(tokens) == 3 and tokens[2].lower() == "all":
            response_text = generate_statistics_text(thread_id, period="daily", mode="previous")
            client.sendMessage(Message(text=response_text), thread_id, thread_type)
            return
        else:
            m_lday_tag = re.search(r"!checktt lday\s+@(.+)", message)
            if m_lday_tag:
                parsed_name = m_lday_tag.group(1).strip()
                day_key = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                stats = message_stats.get(thread_id, {}).get("daily", {}).get(day_key, {})
                target_user_id = None
                for uid, info in stats.items():
                    if info.get("name", "").lower() == parsed_name.lower():
                        target_user_id = uid
                        break
                count = stats.get(target_user_id, {}).get("count", 0) if target_user_id else 0
                response_text = f"📩 {parsed_name} đã gửi {count} tin nhắn ngày hôm qua."
                client.sendMessage(Message(text=response_text), thread_id, thread_type)
                return

    # ----- Xử lý lệnh lweek (weekly previous) -----
    if message.strip().lower().startswith("!checktt lweek"):
        tokens = message.strip().split()
        if len(tokens) == 2:
            dt = datetime.now() - timedelta(weeks=1)
            storage_key = get_weekly_storage_key(dt)
            weekly_stats = message_stats.get(thread_id, {}).get("weekly", {}).get(storage_key, {})
            target_user_id = str(author_id)
            target_user_name = message_object.get("dName", f"User {author_id}")
            count = weekly_stats.get(target_user_id, {}).get("count", 0)
            response_text = f"📩 {target_user_name} đã gửi {count} tin nhắn tuần trước."
            client.sendMessage(Message(text=response_text), thread_id, thread_type)
            return
        elif len(tokens) == 3 and tokens[2].lower() == "all":
            response_text = generate_statistics_text(thread_id, period="weekly", mode="previous")
            client.sendMessage(Message(text=response_text), thread_id, thread_type)
            return
        else:
            m_lweek_tag = re.search(r"!checktt lweek\s+@(.+)", message)
            if m_lweek_tag:
                parsed_name = m_lweek_tag.group(1).strip()
                dt = datetime.now() - timedelta(weeks=1)
                storage_key = get_weekly_storage_key(dt)
                weekly_stats = message_stats.get(thread_id, {}).get("weekly", {}).get(storage_key, {})
                target_user_id = None
                for uid, info in weekly_stats.items():
                    if info.get("name", "").lower() == parsed_name.lower():
                        target_user_id = uid
                        break
                count = weekly_stats.get(target_user_id, {}).get("count", 0) if target_user_id else 0
                response_text = f"📩 {parsed_name} đã gửi {count} tin nhắn tuần trước."
                client.sendMessage(Message(text=response_text), thread_id, thread_type)
                return

    # ----- Xử lý lệnh weekly (current) -----
    if message.strip().lower() == "!checktt week":
        response_text = generate_statistics_text(thread_id, period="weekly", mode="current")
        client.sendMessage(Message(text=response_text), thread_id, thread_type)
        return

    # ----- Xử lý lệnh daily (current) -----
    if message.strip().lower() == "!checktt all":
        response_text = generate_statistics_text(thread_id, period="daily", mode="current")
        client.sendMessage(Message(text=response_text), thread_id, thread_type)
        return

    m = re.search(r"!checktt\s+@(.+)", message)
    if m:
        parsed_name = m.group(1).strip()
        day_key = get_daily_storage_key()
        stats = message_stats.get(thread_id, {}).get("daily", {}).get(day_key, {})
        target_user_id = None
        for uid, info in stats.items():
            if info.get("name", "").lower() == parsed_name.lower():
                target_user_id = uid
                target_user_name = info.get("name")
                break
        count = stats.get(target_user_id, {}).get("count", 0) if target_user_id else 0
        response_text = f"📩 {parsed_name} đã gửi {count} tin nhắn hôm nay."
        client.sendMessage(Message(text=response_text), thread_id, thread_type)
    else:
        day_key = get_daily_storage_key()
        stats = message_stats.get(thread_id, {}).get("daily", {}).get(day_key, {})
        target_user_id = str(author_id)
        target_user_name = message_object.get("dName", f"User {author_id}")
        count = stats.get(target_user_id, {}).get("count", 0)
        response_text = f"📩 {target_user_name} đã gửi {count} tin nhắn hôm nay."
        client.sendMessage(Message(text=response_text), thread_id, thread_type)

def get_mitaizl():
    return {
        'checktt': record_message,
        'handle_checktt': handle_checktt_command
    }

#########################################
# Phần gửi thống kê tự động (không reset dữ liệu lịch sử)
#########################################

# --- CẤU HÌNH DANH SÁCH ID NHÓM ---
# Thêm ID nhóm mới vào danh sách này
TARGET_THREAD_IDS = [
    "1311505722605591852",  # Nhóm 1 (Cũ)
    "6578233211669146965"   # Nhóm 2 (Mới thêm)
]

def send_daily_stats():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] --- BẮT ĐẦU GỬI BÁO CÁO NGÀY ---")
    
    # Duyệt qua từng ID trong danh sách để gửi
    for thread_id in TARGET_THREAD_IDS:
        try:
            # Tạo báo cáo riêng cho từng nhóm
            report = generate_statistics_text(thread_id, period="daily", mode="current")
            
            # Gửi tin nhắn
            global_client.sendMessage(Message(text=report), thread_id, ThreadType.GROUP)
            print(f"✅ Đã gửi báo cáo ngày thành công cho nhóm: {thread_id}")
            
        except Exception as e:
            # Dùng try-except để nếu lỗi nhóm này thì nhóm kia vẫn nhận được
            print(f"❌ Lỗi khi gửi báo cáo ngày cho nhóm {thread_id}: {e}")

def send_weekly_stats():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] --- BẮT ĐẦU GỬI BÁO CÁO TUẦN ---")
    
    for thread_id in TARGET_THREAD_IDS:
        try:
            report = generate_statistics_text(thread_id, period="weekly", mode="current")
            global_client.sendMessage(Message(text=report), thread_id, ThreadType.GROUP)
            print(f"✅ Đã gửi báo cáo tuần thành công cho nhóm: {thread_id}")
        except Exception as e:
            print(f"❌ Lỗi khi gửi báo cáo tuần cho nhóm {thread_id}: {e}")

def start_scheduler():
    # --- CẤU HÌNH GIỜ GỬI (GIỮ NGUYÊN GIỜ CŨ CỦA BẠN) ---
    # Lịch trình này sẽ áp dụng cho TẤT CẢ các nhóm trong danh sách TARGET_THREAD_IDS
    
    schedule.every().day.at("18:00").do(send_daily_stats)
    schedule.every().sunday.at("18:00").do(send_weekly_stats)

    def scheduler_thread():
        print("⏳ Bắt đầu chạy scheduler gửi báo cáo tự động cho danh sách nhóm...")
        while True:
            schedule.run_pending()
            time.sleep(1)

    scheduler = threading.Thread(target=scheduler_thread)
    scheduler.daemon = True
    scheduler.start()