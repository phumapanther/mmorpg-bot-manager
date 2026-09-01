# บอท + เว็บเกม รันบนคลาวด์ 24 ชม. (Oracle Cloud Always Free)
FROM python:3.12-slim

# tzdata: ให้เวลาในเกม/backup ตรงกับไทย ไม่งั้น container เป็น UTC
ENV TZ=Asia/Bangkok \
    PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends tzdata curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ลง dependency ก่อนก๊อปโค้ด — แก้โค้ดแล้ว build ใหม่ไม่ต้องลงใหม่ทั้งหมด
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ข้อมูลที่ต้องอยู่รอดตอน deploy ใหม่ (ผูก volume ทับ)
RUN mkdir -p /app/data /app/license_server/web_uploads

EXPOSE 8790
CMD ["python", "-m", "license_server.serve"]
