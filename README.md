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

## ฟีเจอร์เกม (คำสั่งแชท)

- `!reward` — รับรางวัล (เงิน/exp/ไอเทม) ตามยศ (role) ที่ผู้เล่นมี ตั้งค่าได้ในแผงควบคุมแท็บ "Rank Rewards"
- `!payment [จำนวนเงิน]` — สร้างคำสั่งเติมเงิน + แสดง QR PromptPay อัตโนมัติ (ถ้าเปิดใช้งาน), `!my_orders` เช็คคำสั่งซื้อของตัวเอง, แอดมินใช้ `!confirm_payment [เลข]` ยืนยันแล้วเติมทองอัตโนมัติ (ยังไม่มี API ตรวจสลิปอัตโนมัติ ต้องแอดมินตรวจแล้วกดยืนยันเอง) ตั้งค่าเรทเงิน/บัญชีรับเงินได้ในแท็บ "Payment"
- `!menu` — โพสต์เมนูปุ่ม (กระเป๋า/ธนาคาร/โปรไฟล์/ใช้ไอเทม) ระบบเดียวกับคำสั่งพิมพ์ `!bag` `!bank` `!profile` `!use` เพียงแยกเป็นปุ่มให้กดสะดวกขึ้น คำสั่งพิมพ์เดิมยังใช้ได้ปกติ

## สร้าง .exe ในการแจกจ่าย

### แบบทั่วไป (PyInstaller)

```bash
pip install pyinstaller
pyinstaller build.spec
```

ผลลัพธ์คือ `dist/BotManager.exe` สามารถแจกจ่ายและใช้ได้เลย ต้องให้ `config.example.json` อยู่ในโฟลเดอร์เดียวกับ exe

### ทำเป็นชุดติดตั้งจริง (Install.bat + shortcut + ถอนการติดตั้งได้)

`dist/BotManager.exe` เฉยๆ เป็นแค่ portable exe (ดับเบิลคลิกรันตรงๆ ไม่มีขั้นตอน "ติดตั้ง") ถ้าต้องการให้ลูกค้าได้ประสบการณ์แบบติดตั้งแอปจริง (มีไอคอน Start Menu/Desktop, ถอนได้ผ่าน Windows Settings) ให้รันต่อ:

```bash
python make_installer_zip.py
```

ผลลัพธ์คือ `dist/BotManager-Setup.zip` — แตกไฟล์แล้วดับเบิลคลิก `Install.bat` เพื่อติดตั้ง (ไม่ต้องสิทธิ์แอดมิน ติดตั้งแบบ per-user ไปที่ `%LOCALAPPDATA%\BotManager`) สร้างช็อตคัต Start Menu + Desktop และลงทะเบียนถอนการติดตั้งใน Windows Settings > Apps ให้อัตโนมัติ (ใช้ PowerShell ที่มีอยู่ในเครื่องอยู่แล้ว ไม่ต้องลงทูลอินสตอลเลอร์เพิ่ม เช่น Inno Setup)

⚠️ PyInstaller ห่อแค่ Python bytecode — มีเครื่องมือ decompile แกะกลับเป็นซอร์สที่อ่านได้เกือบเป๊ะ ถ้าต้องการปกป้องซอร์สโค้ดจริงจัง (ห้ามผู้ซื้อดูโค้ด) ให้ใช้ Nuitka แทน:

### แบบป้องกันซอร์สโค้ด (Nuitka)

ต้องติดตั้ง C compiler ก่อน (Visual Studio Build Tools หรือ MinGW-w64) — Nuitka ไม่ได้ติดตั้งให้อัตโนมัติ

```bash
pip install nuitka
python build_nuitka.py
```

ผลลัพธ์คือ `dist_nuitka/BotManager.exe` — คอมไพล์ Python เป็นไบนารีเครื่องจริง ไม่มี bytecode ให้ decompile (ป้องกันได้มากกว่า PyInstaller มาก แต่ไม่มีระบบไหน "แกะไม่ได้ 100%")

## ระบบ License Key (กันแจกจ่ายต่อ)

ก่อนแจกจ่าย .exe ให้ลูกค้า:

1. แก้ `LICENSE_SERVER_URL` ใน `bot/license_client.py` ให้ชี้ไปที่เครื่อง/เซิร์ฟเวอร์ที่จะรัน License Server ของคุณ (ต้องแก้ก่อน build เพราะค่านี้ตั้งใจไม่ให้แก้ผ่านแผงควบคุม — ไม่งั้นลูกค้าชี้ไปเซิร์ฟเวอร์ปลอมแล้วบายพาสได้)
2. รัน License Server ทิ้งไว้บนเครื่องของคุณ (โปรแกรมแยกต่างหาก ไม่แจกจ่ายไปกับ BotManager.exe):
   ```bash
   python -m license_server.keygen_gui
   ```
   หน้าต่างนี้ทำหน้าที่ 2 อย่าง: (ก) เป็น API ให้บอทของลูกค้าเรียกมาเช็คคีย์ทุกครั้งที่สตาร์ท (ข) มีปุ่ม "สร้างคีย์ใหม่" ให้กดสร้างคีย์แจกลูกค้าแต่ละราย (1 คีย์ = 1 เครื่องเท่านั้น)
3. ต้องเปิดโปรแกรมนี้ทิ้งไว้ตลอดเวลา — ถ้าปิด ลูกค้าจะกด Start บอทไม่ได้ (เช็คคีย์ไม่ผ่าน)
4. ลูกค้ากรอกคีย์ที่ได้รับในแผงควบคุมแท็บ Setup ช่อง "License Key" แล้วกดบันทึก + Start บอท

### ขั้นแรกเมื่อรันครั้งแรก

1. เรียกใช้ `BotManager.exe`
2. แผงควบคุมจะเปิดที่ `http://localhost:8770`
3. แอปพลิเคชันจะสร้าง `config.json` อัตโนมัติจาก `config.example.json`
4. ตั้งค่า Discord token และค่าอื่น ๆ ผ่านแผงควบคุม
5. คลิก "Restart" ในแผงควบคุมเพื่อนำการตั้งค่าไปใช้

## หมายเหตุ

- การเปลี่ยนแปลงการตั้งค่าจะต้องคลิก "Restart" ในแผงควบคุมเพื่อให้มีผล
- ไฟล์ `config.json` (ที่มี token) ไม่ควรนำไปแจกจ่าย ให้ผู้ใช้สร้างไฟล์นี้เองบนเครื่องของตนเอง

## License / สัญญาอนุญาต

- **โค้ด / Code:** [PolyForm Noncommercial 1.0.0](LICENSE) — ใช้ ศึกษา แก้ไขได้ แต่**ห้ามขายหรือใช้เชิงพาณิชย์**
- **เสียง รูปภาพ วิดีโอ โมเดล / Media assets:** All Rights Reserved — **ห้ามดัดแปลง แก้ไข ขายต่อ หรือเผยแพร่** โดยไม่ได้รับอนุญาตเป็นลายลักษณ์อักษร

รายละเอียดเต็มดูที่ [LICENSE](LICENSE)
