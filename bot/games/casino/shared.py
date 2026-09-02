"""ของกลางหมวดคาสิโน — ฟังก์ชันที่ไฮโล/สล็อตใช้ร่วมกัน

แยกออกจาก bot/casino_core.py เดิม (รื้อโครงสร้าง 2026-09-02)
ห้ามก๊อปฟังก์ชันนี้ไปไว้ที่อื่น — ทุกเกมต้อง import จากที่นี่ที่เดียว
"""
import bot.models.player_model as player_model


def _take_bet(user_id, bet):
    """ตรวจและหักเงินเดิมพัน — คืน (ok, ข้อความผิดพลาด)"""
    if bet <= 0:
        return False, "❌ เดิมพันต้องมากกว่า 0 ทอง!"
    player = player_model.get_player(user_id)
    if not player:
        return False, "❌ ไม่พบข้อมูลตัวละครของคุณ!"
    if player.get("cash", 0) < bet:
        return False, "❌ เงินในกระเป๋าของคุณไม่พอ!"
    player_model.increment_player_field(user_id, "cash", -bet)
    return True, ""
