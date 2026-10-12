# Dockerfile สำหรับ Synology NAS ที่ DNS องค์กรบล็อก pypi/discord
# ติดตั้ง Python package จาก wheel ออฟไลน์ (ไม่พึ่ง pypi ตอน build) + ตั้ง timezone ไทยโดยไม่ใช้ apt
# เป้า: x86_64 (DS720+ Intel Celeron) · วิธีสร้าง wheels ใหม่: ดู docs/nas-deploy.md
# base image python:3.12-slim ยังต้องดึงจาก Docker Hub ครั้งเดียว (DNS องค์กร resolve Docker Hub ได้)
FROM python:3.12-slim

ENV TZ=Asia/Bangkok \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ติดตั้งจาก wheel ที่เตรียมไว้ (--no-index = ไม่ออกเน็ตเลย) ก่อนก๊อปโค้ด
# + ตั้ง timezone ไทยด้วยไฟล์ TZif ของ pip tzdata แทน apt (datetime.now() เป็นเวลาไทย)
COPY wheels ./wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/app/wheels -r requirements.txt tzdata \
    && ln -sf /usr/local/lib/python3.12/site-packages/tzdata/zoneinfo/Asia/Bangkok /etc/localtime

COPY . .

RUN mkdir -p /app/data /app/license_server/web_uploads

EXPOSE 8790
CMD ["python", "-m", "license_server.serve"]
