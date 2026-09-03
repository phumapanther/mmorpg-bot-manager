"""🎭 ชวนเพื่อนเดินทาง — ผจญภัยเป็นปาร์ตี้ ต่อสู้แบบผลัดเทิร์น

สเปก: docs/superpowers/specs/2026-09-03-party-rpg-design.md
แผน:  docs/superpowers/plans/2026-09-03-party-rpg.md

⚠️ กฎของแพ็กเกจนี้ (มีเทสคุมที่ tests/test_party_layering.py):
   - ห้าม import discord — แกนต้องใช้ได้ทั้งจากบอทและจากเว็บ
   - ห้าม import จาก bot/apps/ — นั่นคือชั้นตัวบอท ไม่ใช่แกนเกม
   - ห้ามวาดภาพเอง — ส่ง "เหตุการณ์" ให้ renderer ไปวาด (ดู events.py)
"""
