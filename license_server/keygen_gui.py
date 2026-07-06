"""โปรแกรมเจนคีย์ + License Server — รันแยกต่างหากบนเครื่องผู้พัฒนา/แอดมิน (ไม่แจกจ่ายให้ลูกค้า)

ต้องเปิดโปรแกรมนี้ทิ้งไว้เสมอ: ตัวบอทของลูกค้าจะเช็คคีย์ผ่าน API นี้ทุกครั้งที่สตาร์ท
ถ้าปิดโปรแกรมนี้ บอทของลูกค้าจะสตาร์ทไม่ได้ (เช็คคีย์ไม่ผ่าน)

ถ้ามี license_server/tools/cloudflared.exe จะเปิด quick tunnel ให้อัตโนมัติ และโชว์ลิงก์ปัจจุบัน
ในหน้าต่างนี้ (ลิงก์จะเปลี่ยนทุกครั้งที่เปิดโปรแกรมใหม่ — ต้องเอาไปแก้ LICENSE_SERVER_URL ใน
bot/license_client.py แล้ว build ใหม่ทุกครั้งที่ลิงก์เปลี่ยน จนกว่าจะมี tunnel แบบถาวร)

รัน: python -m license_server.keygen_gui
"""
import asyncio
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from license_server import db
from license_server.api import create_app, get_or_create_admin_secret

PORT = 8790
_HERE = os.path.dirname(os.path.abspath(__file__))
CLOUDFLARED_PATH = os.path.join(_HERE, "tools", "cloudflared.exe")
TUNNEL_URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def run_server_in_background():
    import uvicorn

    app = create_app()
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="warning")
    server = uvicorn.Server(config)

    def _run():
        asyncio.run(server.serve())

    threading.Thread(target=_run, daemon=True).start()


class KeygenApp:
    def __init__(self, root):
        self.root = root
        self.tunnel_proc = None
        root.title("License Server / Key Generator")
        root.geometry("820x460")
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        info = f"🟢 API กำลังรันที่พอร์ต {PORT}  |  Admin Secret (สำหรับเรียก API จากระยะไกล): {get_or_create_admin_secret()}"
        tk.Label(root, text=info, anchor="w", justify="left", wraplength=800).pack(fill="x", padx=8, pady=6)

        tunnel_row = tk.Frame(root)
        tunnel_row.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(tunnel_row, text="ลิงก์สำหรับใส่ใน LICENSE_SERVER_URL ตอนนี้:").pack(side="left")
        self.tunnel_var = tk.StringVar(value="กำลังเปิด tunnel...")
        tk.Entry(tunnel_row, textvariable=self.tunnel_var, width=55, state="readonly").pack(side="left", padx=6)
        tk.Button(tunnel_row, text="📋 คัดลอก", command=self.copy_tunnel_url).pack(side="left")

        btn_row = tk.Frame(root)
        btn_row.pack(fill="x", padx=8)
        tk.Button(btn_row, text="+ สร้างคีย์ใหม่", command=self.generate_key).pack(side="left")
        tk.Button(btn_row, text="🔄 รีเฟรช", command=self.refresh).pack(side="left", padx=6)

        columns = ("key", "used", "machine_id", "bot_token_hash", "used_at", "last_seen_at", "note")
        self.tree = ttk.Treeview(root, columns=columns, show="headings")
        for col, width in zip(columns, (150, 50, 160, 120, 140, 140, 120)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        self.refresh()
        self.start_tunnel()

    def start_tunnel(self):
        if not os.path.exists(CLOUDFLARED_PATH):
            self.tunnel_var.set(f"ไม่พบ cloudflared.exe — ใช้ได้เฉพาะเครื่องนี้ (http://localhost:{PORT})")
            return

        self.tunnel_proc = subprocess.Popen(
            [CLOUDFLARED_PATH, "tunnel", "--url", f"http://localhost:{PORT}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
        )
        threading.Thread(target=self._watch_tunnel_output, daemon=True).start()

    def _watch_tunnel_output(self):
        for line in iter(self.tunnel_proc.stdout.readline, ""):
            match = TUNNEL_URL_PATTERN.search(line)
            if match:
                url = match.group(0)
                print(f"[Tunnel URL] {url}", flush=True)
                self.root.after(0, lambda: self.tunnel_var.set(url))

    def copy_tunnel_url(self):
        url = self.tunnel_var.get()
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        messagebox.showinfo("คัดลอกแล้ว", f"คัดลอกลิงก์แล้ว:\n{url}\n\nเอาไปแทนใน LICENSE_SERVER_URL (bot/license_client.py) แล้ว build ใหม่")

    def on_close(self):
        if self.tunnel_proc and self.tunnel_proc.poll() is None:
            self.tunnel_proc.terminate()
        self.root.destroy()

    def generate_key(self):
        note = simpledialog.askstring("หมายเหตุ", "หมายเหตุกำกับคีย์ (ใครซื้อ/ชื่อลูกค้า) — ไม่ใส่ก็ได้:", parent=self.root) or ""
        key = db.generate_key(note)
        self.refresh()
        messagebox.showinfo("สร้างคีย์สำเร็จ", f"คีย์ใหม่:\n\n{key}\n\nคัดลอกไปให้ลูกค้ากรอกตอนสตาร์ทบอทได้เลย (ใช้ได้ 1 ครั้ง/1 เครื่องเท่านั้น)")

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for row in db.list_keys():
            self.tree.insert("", "end", values=(
                row["key"],
                "✅" if row["used"] else "—",
                row["machine_id"] or "",
                (row["bot_token_hash"] or "")[:12],
                _fmt(row["used_at"]),
                _fmt(row["last_seen_at"]),
                row["note"] or "",
            ))


def _fmt(ts):
    if not ts:
        return ""
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def main():
    db.init_db()
    run_server_in_background()

    root = tk.Tk()
    KeygenApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
