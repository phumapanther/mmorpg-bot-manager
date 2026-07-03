# MMORPG Bot Manager

Discord MMORPG bot with web management panel.

## การรันแบบ Dev

```bash
pip install -r requirements.txt
python launcher.py
```

เมื่อเรียกใช้ `launcher.py` จะเปิด browser ไปยังแผงควบคุม (panel) ที่ `http://localhost:8770` โดยอัตโนมัติ หากต้องการรันบอทที่เชื่อมต่อกับ Discord โดยตรง ให้ใช้ flag `--run-bot`

```bash
python launcher.py --run-bot
```

## สร้าง .exe ในการแจกจ่าย

```bash
pip install pyinstaller
pyinstaller build.spec
```

ผลลัพธ์คือ `dist/BotManager.exe` สามารถแจกจ่ายและใช้ได้เลย ต้องให้ `config.example.json` อยู่ในโฟลเดอร์เดียวกับ exe

### ขั้นแรกเมื่อรันครั้งแรก

1. เรียกใช้ `BotManager.exe`
2. แผงควบคุมจะเปิดที่ `http://localhost:8770`
3. แอปพลิเคชันจะสร้าง `config.json` อัตโนมัติจาก `config.example.json`
4. ตั้งค่า Discord token และค่าอื่น ๆ ผ่านแผงควบคุม
5. คลิก "Restart" ในแผงควบคุมเพื่อนำการตั้งค่าไปใช้

## หมายเหตุ

- การเปลี่ยนแปลงการตั้งค่าจะต้องคลิก "Restart" ในแผงควบคุมเพื่อให้มีผล
- ไฟล์ `config.json` (ที่มี token) ไม่ควรนำไปแจกจ่าย ให้ผู้ใช้สร้างไฟล์นี้เองบนเครื่องของตนเอง
