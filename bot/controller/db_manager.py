#controller/db_manager
import sys
import os
import sqlite3
import json

# ⚠️ จุดที่แก้: กำหนดชื่อไฟล์ Database ให้ตรงกับระบบหลัก
DB_NAME = "game_data.db"

# ดึง player_model เข้ามาใช้ เพื่อให้ใช้ระบบเงิน (Cash) แบบเดียวกับเกมส่วนอื่นๆ
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import models.player_model as player_model 

# ==========================================
# 👤 หมวดจัดการเงินของผู้เล่น (โอนงานให้ player_model)
# ==========================================
def get_balance(user_id):
    try:
        player = player_model.get_player(user_id)
        if player:
            return int(player.get("cash", 0))
        return 0
    except Exception as e:
        print(f"[ERROR] [db_manager] ดึงข้อมูลเงินผู้เล่นล้มเหลว: {e}")
        return 0

def update_balance(user_id, new_balance):
    try:
        player_model.update_player_field(user_id, "cash", int(new_balance))
    except Exception as e:
        print(f"[ERROR] [db_manager] บันทึกข้อมูลเงินผู้เล่นล้มเหลว: {e}")

# ==========================================
# 🤖 ระบบฐานข้อมูลความจำ Machine Learning
# ==========================================
def load_bot_memory(bot_name='AlphaBot'):
    """โหลดความจำสมองกลบอทจาก Database"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # ใช้เครื่องหมาย ? สำหรับ SQLite
        cursor.execute("SELECT memory FROM bot_data WHERE bot_name = ?", (bot_name,))
        result = cursor.fetchone()
        
        cursor.close() # 🛠️ ปิด cursor ก่อนปิด connection เสมอ
        conn.close()
        
        if result and result[0]:
            print(f"[LOG] โหลดความจำสมองกล '{bot_name}' สำเร็จ")
            return result[0] # ส่งคืนค่าเป็น JSON String ให้ bot_brain ไปแปลงต่อ
            
        print(f"[LOG] ไม่พบความจำ '{bot_name}' (เริ่มเรียนรู้ใหม่)")
        return None
    except Exception as e:
        print(f"[ERROR] โหลดความจำบอท {bot_name} ไม่ได้: {e}")
        return None

def save_bot_memory(memory_data, bot_name='AlphaBot'):
    """บันทึกความจำสมองกลลง Database"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # ⚠️ จุดสำคัญ: SQLite ใช้ ON CONFLICT DO UPDATE
        sql = """
            INSERT INTO bot_data (bot_name, memory) 
            VALUES (?, ?) 
            ON CONFLICT(bot_name) DO UPDATE SET memory = excluded.memory
        """
        
        cursor.execute(sql, (bot_name, memory_data))
        conn.commit()
        
        cursor.close() # 🛠️ ปิด cursor ก่อนปิด connection เสมอ
        conn.close()
        
        print(f"[LOG] บันทึกความจำล่าสุดของ '{bot_name}' ลงฐานข้อมูลเรียบร้อย")
    except Exception as e:
        print(f"[ERROR] บันทึกความจำบอท {bot_name} ล้มเหลว: {e}")