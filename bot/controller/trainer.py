#controller/bot_brain
import random
from controller.bot_brain import BlackjackBot
from controller import db_manager
import json

def train_alpha_bot(iterations=5000):
    print(f"[LOG] [TRAINER] 🚀 เริ่มต้นกระบวนการฝึกสอน AlphaBot จำนวน {iterations} รอบ...")
    
    # โหลดสมองบอท
    bot = BlackjackBot()

    original_size = len(bot.q_table)
    print(f"[LOG] [TRAINER] พบข้อมูลเก่า {original_size} รายการ")
    
    for i in range(iterations):
        p_score = random.randint(4, 24)
        d_upcard = random.randint(1, 10)
        
        # จำลองการจั่ว (อย่าใส่ตรรกะรางวัลเอง ให้ใช้ของบอท)
        action = bot.get_action(p_score, d_upcard, epsilon=0.3)
        
        # จำลองผลลัพธ์แบบสุ่ม
        if action == "!hit":
            final_score = p_score + random.randint(1, 10)
            if final_score > 24:
                reward = bot.calculate_reward('bust', final_score)
            else:
                # ถ้าจั่วแล้วไม่เกิน ให้ Reward กลางๆ (หรือจะข้ามไปก็ได้)
                reward = 0.0 
        else:
            # จำลองสถานการณ์ Stand แล้วลุ้นแต้มเจ้ามือ
            dealer_score = random.randint(15, 24)
            if p_score > dealer_score:
                reward = bot.calculate_reward('win', p_score)
            elif p_score == dealer_score:
                reward = bot.calculate_reward('tie', p_score)
            else:
                reward = bot.calculate_reward('lose', p_score)

        bot.learn(f"{p_score}-{d_upcard}", action, reward)
        
        if (i + 1) % 1000 == 0:
            print(f"[LOG] [TRAINER] ⚙️ เทรนไปแล้ว {i+1} รอบ...")

    # บันทึกความจำลงฐานข้อมูลหลังจากเทรนเสร็จ
    memory_json = json.dumps(bot.q_table)
    db_manager.save_bot_memory(memory_json, 'AlphaBot')

    new_size = len(bot.q_table)
    print(f"[LOG] [TRAINER] ✅ เสร็จสิ้น! ขนาดดาต้า: {original_size} -> {new_size}")

if __name__ == "__main__":
    train_alpha_bot(5000)