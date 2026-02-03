import json
import os
from datetime import datetime, timedelta

# Đường dẫn file thống kê (dùng chung với checktt.py)
STATS_FILE = "message_stats.json"
# ID của bot (điền ID thực tế của bot)
BOT_ID = "770810507108566189"  # Thay đổi theo thực tế

def load_stats():
    """Tải dữ liệu thống kê từ file."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("Lỗi khi tải file stats:", e)
            return {}
    return {}

def save_stats(stats):
    """Lưu dữ liệu thống kê vào file."""
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Lỗi khi lưu file stats:", e)

def get_daily_storage_key(dt=None):
    """Trả về key ngày dạng YYYY-MM-DD."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d")

class SpamDetector:
    def __init__(self, message_limit=10, time_window=60, warning_limit=3):
        """
        message_limit: Số tin nhắn tối đa cho phép trong khoảng time_window (mặc định 10).
        time_window: Khoảng thời gian tính spam, đơn vị giây (mặc định 60 giây).
        warning_limit: Số lần cảnh cáo trước khi reset (mặc định 3, lần thứ 4 sẽ reset).
        """
        self.message_limit = message_limit
        self.time_window = time_window
        self.warning_limit = warning_limit
        # spam_tracker bây giờ lưu danh sách các dict: {"timestamp": datetime, "content": str}
        self.spam_tracker = {}   # {member_id: [ {timestamp, content}, ... ]}
        self.warnings = {}       # {member_id: warning_count}
        self.current_day = get_daily_storage_key()

    def _convert_timestamp(self, timestamp):
        """
        Chuyển đổi timestamp thành đối tượng datetime nếu cần.
        Nếu timestamp là số hoặc chuỗi số thì giả định nó là mili-giây và chuyển đổi theo giây.
        """
        if isinstance(timestamp, datetime):
            return timestamp
        try:
            ts = float(timestamp) / 1000  # chia 1000 vì giá trị ts nhận được là mili-giây
            return datetime.fromtimestamp(ts)
        except Exception as e:
            print("Lỗi chuyển đổi timestamp:", e)
            return datetime.now()

    def process_message(self, thread_id, member_id, timestamp=None, content=""):
        """
        Xử lý tin nhắn của thành viên để kiểm tra spam trong một nhóm cụ thể.

        Tham số:
          - thread_id: ID của nhóm.
          - member_id: ID của thành viên.
          - timestamp: Thời gian tin nhắn (mặc định hiện tại).
          - content: Nội dung tin nhắn.

        Sau mỗi tin nhắn:
          - Lưu lại timestamp và content vào spam_tracker cho member_id.
          - Loại bỏ các tin nhắn cũ hơn time_window giây (cho điều kiện gốc).
          - Kiểm tra các điều kiện cảnh báo:
              + Điều kiện gốc: Số tin nhắn trong time_window vượt quá message_limit.
              + Điều kiện 1: 5 tin nhắn trong 5 giây.
              + Điều kiện 2: 5 tin nhắn trong 10 giây.
              + Điều kiện 3: 5 tin nhắn liên tiếp trong 20 giây mà mỗi tin chỉ có 1 từ.
          - Nếu một trong các điều kiện được thỏa mãn:
              + Tăng số cảnh cáo của thành viên.
              + Nếu cảnh cáo từ 1 đến 3: trừ số tin nhắn spam khỏi số tin nhắn trong ngày của thành viên tại nhóm
                và trả về thông báo cảnh báo.
              + Nếu cảnh cáo đạt 4: reset số tin nhắn trong ngày của thành viên tại nhóm về 0 và trả về thông báo reset.
        Trả về thông báo cảnh báo (string) nếu có, ngược lại trả về None.
        """
        # Reset warnings và spam_tracker nếu ngày thay đổi
        today = get_daily_storage_key()
        if today != self.current_day:
            self.current_day = today
            self.warnings = {}
            self.spam_tracker = {}

        # Bỏ qua tin nhắn của bot
        if str(member_id) == BOT_ID:
            return None

        # Chuyển đổi timestamp nếu cần
        timestamp = self._convert_timestamp(timestamp) if timestamp else datetime.now()

        # Thêm tin nhắn vào spam_tracker
        self.spam_tracker.setdefault(member_id, [])
        self.spam_tracker[member_id].append({"timestamp": timestamp, "content": content})

        # Lọc danh sách tin nhắn theo khoảng thời gian cho điều kiện gốc (time_window)
        cutoff = timestamp - timedelta(seconds=self.time_window)
        self.spam_tracker[member_id] = [m for m in self.spam_tracker[member_id] if m["timestamp"] > cutoff]
        # Tính tổng số tin nhắn theo điều kiện gốc
        spam_count = len(self.spam_tracker[member_id])
        current_warn = self.warnings.get(member_id, 0)
        print(f"[DEBUG] member_id: {member_id}, spam_count: {spam_count}, current_warning: {current_warn}")

        # Kiểm tra điều kiện bổ sung:
        # Điều kiện 1: 5 tin nhắn trong 5 giây
        messages_5s = [m for m in self.spam_tracker[member_id] if m["timestamp"] > timestamp - timedelta(seconds=5)]
        condition1 = len(messages_5s) >= 5

        # Điều kiện 2: 5 tin nhắn trong 10 giây
        messages_10s = [m for m in self.spam_tracker[member_id] if m["timestamp"] > timestamp - timedelta(seconds=10)]
        condition2 = len(messages_10s) >= 5

        # Điều kiện 3: 5 tin nhắn liên tiếp trong 20 giây mà mỗi tin chỉ có 1 từ
        messages_20s = [m for m in self.spam_tracker[member_id] if m["timestamp"] > timestamp - timedelta(seconds=20)]
        if len(messages_20s) >= 5:
            last_five = messages_20s[-5:]
            # Kiểm tra từng tin: sau khi loại bỏ khoảng trắng, nếu chia theo khoảng trắng có đúng 1 phần tử
            condition3 = all(len(m["content"].strip().split()) == 1 for m in last_five)
        else:
            condition3 = False

        # Điều kiện gốc: spam_count vượt quá message_limit
        original_condition = spam_count > self.message_limit

        # Nếu một trong các điều kiện được thỏa mãn, tiến hành xử lý cảnh báo
        if original_condition or condition1 or condition2 or condition3:
            # Tăng số lần cảnh cáo của thành viên
            self.warnings[member_id] = current_warn + 1
            current_warning = self.warnings[member_id]
            # Tải dữ liệu thống kê từ file
            stats = load_stats()
            day_key = get_daily_storage_key()
            # Cập nhật dữ liệu cho nhóm (thread_id) hiện tại
            if thread_id not in stats or not isinstance(stats[thread_id], dict):
                stats[thread_id] = {"daily": {}}
            if day_key not in stats[thread_id]["daily"]:
                stats[thread_id]["daily"][day_key] = {}
            # Đảm bảo dữ liệu của thành viên tại nhóm đã tồn tại
            if str(member_id) not in stats[thread_id]["daily"][day_key]:
                stats[thread_id]["daily"][day_key][str(member_id)] = {"name": f"User {member_id}", "count": 0}

            # Lấy tên của thành viên từ file thống kê
            member_name = stats[thread_id]["daily"][day_key][str(member_id)].get("name", f"User {member_id}")

            if current_warning < 4:
                # Cảnh báo lần 1 đến 3: trừ số tin nhắn spam khỏi số tin nhắn trong ngày
                current_count = stats[thread_id]["daily"][day_key][str(member_id)].get("count", 0)
                new_count = max(0, current_count - spam_count)
                stats[thread_id]["daily"][day_key][str(member_id)]["count"] = new_count
                save_stats(stats)
                # Reset spam_tracker để không xử lý lại tin nhắn cũ
                self.spam_tracker[member_id] = []
                msg = (f"🚨 Cảnh báo spam lần {current_warning}\n"
                       f"❌ {member_name} sẽ bị reset tin nhắn nếu tiếp tục hành vi này\n"
                       f"🚫 Tôi đã trừ đi số lượng tin nhắn spam của bạn")
                print(f"[DEBUG] {msg}")
                return msg
            else:
                # Lần cảnh báo thứ 4: reset số tin nhắn trong ngày của thành viên tại nhóm về 0
                stats[thread_id]["daily"][day_key][str(member_id)]["count"] = 0
                save_stats(stats)
                self.warnings[member_id] = 0
                self.spam_tracker[member_id] = []
                msg = (f"🚨 Vượt quá số lần cảnh báo 🚨\n"
                       f"🚫 {member_name} đã bị reset số lượng tin nhắn")
                print(f"[DEBUG] {msg}")
                return msg
        return None

def get_mitaizl():
    """
    Trả về dictionary chứa các hàm cần thiết để module được load.
    Giả sử bot sẽ gọi get_mitaizl() để lấy các chức năng của module spam.
    """
    return {
        'spam': SpamDetector().process_message
    }

if __name__ == "__main__":
    # Sử dụng message_limit=3 để dễ dàng kích hoạt cảnh báo trong test
    detector = SpamDetector(message_limit=3, time_window=60, warning_limit=3)
    thread_id = "1234567890"
    member_id = "111222333"
    now = datetime.now()

    # Giả lập gửi 12 tin nhắn trong vòng 1 phút từ thành viên tại nhóm có ID thread_id
    # Một số tin nhắn có nội dung là 1 từ để kích hoạt điều kiện 3
    messages = [
        {"delay": 0,  "content": "Hi"},
        {"delay": 3,  "content": "Hello"},
        {"delay": 6,  "content": "Hey"},
        {"delay": 9,  "content": "Yo"},
        {"delay": 12, "content": "Sup"},
        {"delay": 15, "content": "This is spam"},  # nhiều từ, không tính điều kiện 3
        {"delay": 18, "content": "A"},
        {"delay": 21, "content": "B"},
        {"delay": 24, "content": "C"},
        {"delay": 27, "content": "D"},
        {"delay": 30, "content": "E"},
        {"delay": 33, "content": "Extra"},
    ]

    for msg in messages:
        ts = now + timedelta(seconds=msg["delay"])
        warning = detector.process_message(thread_id, member_id, timestamp=ts, content=msg["content"])
        if warning:
            print(warning)
