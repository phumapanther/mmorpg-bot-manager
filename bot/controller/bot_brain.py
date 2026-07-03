#controller/bot_brain
import sys
import os
import random
import json # ✅ ย้ายมาไว้ด้านบน

# เพิ่มบรรทัดนี้เพื่อให้ Python มองเห็นโฟลเดอร์หลัก
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from controller import db_manager  

class BlackjackBot:
    def __init__(self):
        self.q_table = {} 
        
        try:
            # ไปถาม Database ว่า "มีความจำเก่าของฉันไหม?"
            raw_data = db_manager.load_bot_memory('AlphaBot') 
            
            if raw_data:
                # แปลงจาก JSON String กลับมาเป็น Dictionary
                self.q_table = json.loads(raw_data)
                print("[LOG] [BOT_BRAIN] 🧠 AlphaBot: โหลดความจำ Q-Table เรียบร้อยพร้อมลุย!")
            else:
                print("[LOG] [BOT_BRAIN] ✨ AlphaBot: เริ่มต้นสมองใหม่ (ว่างเปล่า)")
                
        except json.JSONDecodeError as e:
            # ดักจับ Error กรณีข้อมูลใน Database เสียหาย (Corrupted)
            print(f"[ERROR] [BOT_BRAIN] ⚠️ ข้อมูลความจำ AlphaBot เสียหาย ({e}) กำลังรีเซ็ตสมองใหม่...")
            self.q_table = {}
        except Exception as e:
            print(f"[ERROR] [BOT_BRAIN] ⚠️ โหลดความจำล้มเหลว: {e}")
            self.q_table = {}

    def get_action(self, player_score, dealer_upcard, epsilon=0.1):
        # สร้าง Key ใหม่ที่รวมข้อมูล 2 ฝั่ง เช่น "15-10" (เรา 15 เจ้ามือโชว์ 10)
        state = f"{player_score}-{dealer_upcard}"
        
        # ถ้ายังไม่เคยเจอเหตุการณ์นี้ ให้ตั้งค่าเริ่มต้นเป็น 0 ทั้ง Stand [0] และ Hit [1]
        if state not in self.q_table:
            self.q_table[state] = [0.0, 0.0]
        
        # ระบบสุ่มสำรวจ (Exploration) เพื่อให้บอทลองอะไรใหม่ๆ นอกกรอบ
        if random.random() < epsilon:
            return random.choice(["!hit", "!c"])

        # เลือกเส้นทางที่ให้ค่าตอบแทน (Q-Value) สูงที่สุด
        if self.q_table[state][0] >= self.q_table[state][1]:
            return "!c"  # Stand (พอ)
        else:
            return "!hit" # Hit (จั่ว)


    def calculate_reward(self, result_type, p_score, b_score=None):
        """
        รวมกฎการให้รางวัลไว้ที่เดียว เพื่อป้องกันบอทสับสน
        result_type: 'bust', 'win', 'lose', 'tie'
        """
        if result_type == 'bust': return -1.0
        if result_type == 'win': return 1.0
        if result_type == 'lose': return -1.0
        if result_type == 'tie': return 0.1
        return 0.0

    def learn(self, state, action, reward):
        # จัดการ Index ให้ตรงกับข้อมูล: 0 = Stand (!c), 1 = Hit (!hit)
        action_idx = 1 if action == "!hit" else 0
        
        # ป้องกันกรณีเกิด State ใหม่
        if state not in self.q_table:
            self.q_table[state] = [0.0, 0.0]
            
        old_value = self.q_table[state][action_idx]
        # สูตรอัปเดตสมอง
        self.q_table[state][action_idx] = old_value + 0.1 * (reward - old_value)