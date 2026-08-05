"""โปรแกรมเจนคีย์ + License Server — รันแยกต่างหากบนเครื่องผู้พัฒนา/แอดมิน (ไม่แจกจ่ายให้ลูกค้า)

ต้องเปิดโปรแกรมนี้ทิ้งไว้เสมอ: ตัวบอทของลูกค้าจะเช็คคีย์ผ่าน API นี้ทุกครั้งที่สตาร์ท
ถ้าปิดโปรแกรมนี้ บอทของลูกค้าจะสตาร์ทไม่ได้ (เช็คคีย์ไม่ผ่าน)

ถ้ามี license_server/tools/cloudflared.exe จะเปิด quick tunnel ให้อัตโนมัติ และโชว์ลิงก์ปัจจุบัน
ในหน้าต่างนี้ (ลิงก์เปลี่ยนทุกครั้งที่เปิดโปรแกรมใหม่ — โปรแกรมจะเขียนลิงก์ใหม่ลง
LICENSE_SERVER_URL.txt ที่ root โปรเจ็คให้อัตโนมัติ เหลือแค่กด build ใหม่แจกลูกค้า)

รัน: python -m license_server.keygen_gui
"""
import asyncio
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ตอนเปิดด้วย pythonw (เช่นจาก shortcut หน้าเดสก์ทอป) จะไม่มี console → sys.stdout/stderr เป็น None
# แล้ว uvicorn เรียก sys.stdout.isatty() ตอนตั้ง logging ทำให้ crash เงียบทั้งโปรแกรมก่อนหน้าต่างเปิด
# จึงแทนด้วย devnull ก่อนใครแตะ stdio
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from license_server import db
from license_server.api import create_app, get_or_create_admin_secret

PORT = 8790
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_HERE)
CLOUDFLARED_PATH = os.path.join(_HERE, "tools", "cloudflared.exe")
URL_FILE = os.path.join(PROJECT_ROOT, "LICENSE_SERVER_URL.txt")
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
        self.launcher_proc = None
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

        self.url_status_var = tk.StringVar(value="")
        tk.Label(root, textvariable=self.url_status_var, anchor="w", fg="#006400", wraplength=800).pack(fill="x", padx=8)

        btn_row = tk.Frame(root)
        btn_row.pack(fill="x", padx=8)
        tk.Button(btn_row, text="+ สร้างคีย์ใหม่", command=self.generate_key).pack(side="left")
        tk.Button(btn_row, text="🔄 รีเฟรช", command=self.refresh).pack(side="left", padx=6)
        self.build_btn = tk.Button(btn_row, text="🔨 Build ชุดแจกลูกค้า", command=self.start_build)
        self.build_btn.pack(side="left", padx=6)
        tk.Button(btn_row, text="📂 เปิดโฟลเดอร์ dist", command=self.open_dist).pack(side="left")
        tk.Button(btn_row, text="🚀 รันบอท (เปิด Panel)", command=self.launch_bot_manager).pack(side="left", padx=6)
        tk.Button(btn_row, text="🌐 เปิดเว็บไซต์", command=self.open_website).pack(side="left")

        self.build_status_var = tk.StringVar(value="")
        tk.Label(root, textvariable=self.build_status_var, anchor="w", wraplength=800).pack(fill="x", padx=8)

        columns = ("key", "used", "machine_id", "bot_token_hash", "used_at", "last_seen_at", "note")
        self.tree = ttk.Treeview(root, columns=columns, show="headings")
        for col, width in zip(columns, (150, 50, 160, 120, 140, 140, 120)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width)
        self.tree.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.tree.bind("<<TreeviewSelect>>", self._on_select_row)
        self.tree.bind("<Double-1>", lambda _e: self.copy_selected_key())

        key_row = tk.Frame(root)
        key_row.pack(fill="x", padx=8, pady=(0, 8))
        tk.Label(key_row, text="คีย์ที่เลือก:").pack(side="left")
        self.selected_key_var = tk.StringVar(value="")
        tk.Entry(key_row, textvariable=self.selected_key_var, width=45, state="readonly").pack(side="left", padx=6)
        tk.Button(key_row, text="📋 คัดลอกคีย์", command=self.copy_selected_key).pack(side="left")
        self.copy_feedback = tk.Label(key_row, text="", fg="#006400")
        self.copy_feedback.pack(side="left", padx=6)

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
                status = self._save_url_file(url)
                self.root.after(0, lambda u=url, s=status: (self.tunnel_var.set(u), self.url_status_var.set(s)))

    def _save_url_file(self, url):
        """เขียน tunnel URL ล่าสุดทับ LICENSE_SERVER_URL.txt — คืนข้อความสถานะไว้โชว์ในหน้าต่าง"""
        try:
            with open(URL_FILE, "w", encoding="utf-8") as f:
                f.write(url + "\n")
            return "💾 บันทึกลิงก์ลง LICENSE_SERVER_URL.txt ให้แล้วอัตโนมัติ — กด Build เพื่อสร้างชุดแจกลูกค้าด้วยลิงก์ใหม่"
        except OSError as e:
            return f"⚠️ เขียน LICENSE_SERVER_URL.txt ไม่สำเร็จ: {e} — ต้องแก้ไฟล์เองก่อน build"

    def open_website(self):
        """เปิดเว็บไซต์เกมในเบราว์เซอร์ — ใช้ลิงก์ tunnel ปัจจุบัน (ยังไม่มี tunnel = localhost)"""
        import webbrowser
        url = self.tunnel_var.get().strip()
        if not url.startswith("http"):
            url = f"http://localhost:{PORT}"
        webbrowser.open(url)

    def copy_tunnel_url(self):
        url = self.tunnel_var.get()
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        messagebox.showinfo("คัดลอกแล้ว", f"คัดลอกลิงก์แล้ว:\n{url}\n\n(ลิงก์นี้ถูกบันทึกลง LICENSE_SERVER_URL.txt ให้อัตโนมัติแล้ว)")

    def start_build(self):
        """กดปุ่ม Build — ทำเหมือน build_release.bat แต่รันเบื้องหลัง หน้าต่างไม่ค้าง"""
        current = self.tunnel_var.get()
        if current.startswith("https://"):
            try:
                with open(URL_FILE, encoding="utf-8") as f:
                    saved = f.read().strip()
            except OSError:
                saved = ""
            if saved != current:
                messagebox.showwarning(
                    "ลิงก์ยังไม่ถูกบันทึก",
                    "ลิงก์ tunnel ปัจจุบันยังไม่ตรงกับ LICENSE_SERVER_URL.txt — แก้ไฟล์ให้ตรงก่อนแล้วค่อย build",
                )
                return
        elif os.path.exists(CLOUDFLARED_PATH):
            if not messagebox.askyesno(
                "ยังไม่มีลิงก์ tunnel",
                "tunnel ยังไม่ขึ้น — ถ้า build ตอนนี้จะได้ลิงก์เก่าใน LICENSE_SERVER_URL.txt\nbuild ต่อเลยไหม?",
            ):
                return

        self.build_btn.config(state="disabled")
        threading.Thread(target=self._run_build, daemon=True).start()

    def _run_build(self):
        def status(msg):
            self.root.after(0, lambda: self.build_status_var.set(msg))

        steps = [
            ("🔨 [1/2] กำลัง build exe ด้วย PyInstaller... (ขั้นนี้ใช้เวลาหลายนาที)",
             [sys.executable, "-m", "PyInstaller", "build.spec", "--noconfirm"]),
            ("📦 [2/2] กำลังแพ็ก installer zip...",
             [sys.executable, "make_installer_zip.py"]),
        ]
        try:
            build_dir = os.path.join(PROJECT_ROOT, "build")
            if os.path.exists(build_dir):
                shutil.rmtree(build_dir)
            for label, cmd in steps:
                status(label)
                result = subprocess.run(
                    cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                )
                if result.returncode != 0:
                    tail = "\n".join((result.stdout + "\n" + result.stderr).strip().splitlines()[-15:])
                    raise RuntimeError(f"{label}\nล้มเหลว:\n{tail}")
            status("✅ Build เสร็จ — dist\\BotManager-Setup.zip พร้อมส่งลูกค้า")
            self.root.after(0, self._ask_open_dist)
        except Exception as e:
            status("❌ Build ล้มเหลว")
            err = str(e)
            self.root.after(0, lambda: messagebox.showerror("Build ล้มเหลว", err[-2000:]))
        finally:
            self.root.after(0, lambda: self.build_btn.config(state="normal"))

    def launch_bot_manager(self):
        """เปิด launcher.py (Panel ของบอทตัวเอง) เป็นโปรเซสแยก — ปิดหน้าต่าง keygen บอทก็ยังรันต่อ"""
        import json
        import webbrowser

        try:
            with open(os.path.join(PROJECT_ROOT, "config.json"), encoding="utf-8") as f:
                port = json.load(f).get("panel_port", 8770)
        except (OSError, ValueError):
            port = 8770

        if self.launcher_proc and self.launcher_proc.poll() is None:
            webbrowser.open(f"http://localhost:{port}")  # รันอยู่แล้ว — เปิดหน้า Panel ให้แทน
            return

        # ถ้าตัวเราถูกเปิดด้วย pythonw (ไม่มี console) ให้สลับไป python.exe เพื่อให้ launcher
        # ได้หน้าต่าง console ของตัวเอง — ผู้ใช้เห็น log และปิดหน้าต่างเพื่อหยุด Panel ได้
        py = sys.executable
        if os.path.basename(py).lower() == "pythonw.exe":
            candidate = os.path.join(os.path.dirname(py), "python.exe")
            if os.path.exists(candidate):
                py = candidate

        flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
        self.launcher_proc = subprocess.Popen(
            [py, os.path.join(PROJECT_ROOT, "launcher.py")],
            cwd=PROJECT_ROOT, creationflags=flags,
        )

    def _ask_open_dist(self):
        if messagebox.askyesno("Build เสร็จ", "ได้ไฟล์ dist\\BotManager-Setup.zip แล้ว ส่งไฟล์นี้ให้ลูกค้าได้เลย\n\nเปิดโฟลเดอร์ dist เลยไหม?"):
            self.open_dist()

    def open_dist(self):
        dist_dir = os.path.join(PROJECT_ROOT, "dist")
        if not os.path.isdir(dist_dir):
            messagebox.showwarning("ยังไม่มีโฟลเดอร์ dist", "ยังไม่เคย build — กดปุ่ม \"🔨 Build ชุดแจกลูกค้า\" ก่อน")
            return
        os.startfile(dist_dir)

    def on_close(self):
        if self.tunnel_proc and self.tunnel_proc.poll() is None:
            self.tunnel_proc.terminate()
        self.root.destroy()

    def generate_key(self):
        note = simpledialog.askstring("หมายเหตุ", "หมายเหตุกำกับคีย์ (ใครซื้อ/ชื่อลูกค้า) — ไม่ใส่ก็ได้:", parent=self.root) or ""
        key = db.generate_key(note)
        self.refresh()
        for iid in self.tree.get_children():
            if self.tree.item(iid, "values")[0] == key:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                break
        self.selected_key_var.set(key)
        self.root.clipboard_clear()
        self.root.clipboard_append(key)
        messagebox.showinfo("สร้างคีย์สำเร็จ", f"คีย์ใหม่:\n\n{key}\n\n📋 คัดลอกเข้าคลิปบอร์ดให้แล้ว วางส่งลูกค้าได้เลย (1 คีย์ = 1 เครื่องเท่านั้น)")

    def _on_select_row(self, _event=None):
        sel = self.tree.selection()
        if sel:
            self.selected_key_var.set(self.tree.item(sel[0], "values")[0])

    def copy_selected_key(self):
        key = self.selected_key_var.get()
        if not key:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(key)
        self.copy_feedback.config(text="✅ คัดลอกแล้ว")
        self.root.after(2000, lambda: self.copy_feedback.config(text=""))

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
