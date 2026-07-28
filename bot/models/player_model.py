# player_model.py
import sqlite3
import json
import time # อย่าลืม import time เข้ามานะครับ

DB_NAME = "game_data.db"

NEW_PLAYER_DEFAULTS = {
    "level": 1,
    "exp": 0,
    "rank": "F",
    "hp": 100,
    "max_hp": 100,
    "cash": 20000,
    "bank": 0,
    "inventory": "[]",
    "armor": "None",
    "armor_dur": 100,      
    "weapon": "Wooden_Weapon",
    "weapon_dur": 50,    
    "current_state": "village",
    "last_event": "none",
    "last_death": None,
    "village_cooldown": 0,
    "dungeon_steps": 0,
    "total_online_time": 0,
    "arrest_until": 0,
    "total_text": 0,
    "event_text": 0,
    "bag": "Medium_Bag",
    "capacity": 50,
    "sanity": 100,
    "last_reward_claim": 0,
    "continent": "main",
    "status_effects": "{}",
    "profile_color": 0,
    "race": "",        # P8: เผ่าจาก DB (ใช้เมื่อไม่มียศ เช่นเซิร์ฟรอง)
    "class_name": "",  # P8: คลาสจาก DB
    "title": ""        # C8: ตำแหน่งอวดที่ติดอยู่ (ปลดจากความสำเร็จ)
}
    
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. สร้างตารางพื้นฐาน
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            rank TEXT DEFAULT 'F',
            hp INTEGER DEFAULT 100,
            max_hp INTEGER DEFAULT 100,
            cash INTEGER DEFAULT 20000,
            bank INTEGER DEFAULT 0,
            inventory TEXT DEFAULT '[]',
            armor TEXT DEFAULT 'None',
            armor_dur INTEGER DEFAULT 100,
            weapon TEXT DEFAULT 'Wooden_Weapon',
            weapon_dur INTEGER DEFAULT 50,
            current_state TEXT DEFAULT 'village',
            last_event TEXT DEFAULT 'none',
            last_death TEXT,
            village_cooldown INTEGER DEFAULT 0,
            dungeon_steps INTEGER DEFAULT 0,
            total_online_time INTEGER DEFAULT 0,
            arrest_until INTEGER DEFAULT 0,
            total_text INTEGER DEFAULT 0,
            event_text INTEGER DEFAULT 0,
            bag TEXT DEFAULT 'Medium_Bag',
            capacity INTEGER DEFAULT 10,
            sanity INTEGER DEFAULT 100
        )
    """)

    # 2. 🤖 เพิ่มตารางสมองกลบอทตรงนี้! (แยกตาราง แต่ไฟล์ db เดียวกัน)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_data (
            bot_name TEXT PRIMARY KEY,
            memory TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    
    # 2. รันระบบอัปเดตโครงสร้างคอลัมน์ให้อัตโนมัติ (ขยายตาม NEW_PLAYER_DEFAULTS)
    auto_update_schema()

def get_player(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row is None:
        # 🤖 ลอจิกอัจฉริยะ: ประกอบร่างคำสั่ง INSERT อัตโนมัติตาม NEW_PLAYER_DEFAULTS บนสุด
        fields = ["user_id"] + list(NEW_PLAYER_DEFAULTS.keys())
        placeholders = ["?"] * len(fields)
        
        # ดึงค่าจากตัวแปรด้านบนมาเตรียมยัดลง DB
        values = [user_id]
        for key, val in NEW_PLAYER_DEFAULTS.items():
            # ดักเคสพิเศษพวกตัวแปรเลขที่อยากให้ยืดหยุ่นในโค้ด
            if key == "cash": val = NEW_PLAYER_DEFAULTS["cash"]
            values.append(val)
            
        sql_insert = f"INSERT INTO players ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        
        cursor.execute(sql_insert, values)
        conn.commit()
        conn.close()
        
        init_profile = NEW_PLAYER_DEFAULTS.copy()
        
        # 🛠️ จุดที่ 1: ยกเลิกการใช้ json.loads สำหรับผู้เล่นใหม่
        raw_inv = str(init_profile.get("inventory", ""))
        for char in ["(", ")", "[", "]", "'", '"', " "]:
            raw_inv = raw_inv.replace(char, "")
        init_profile["inventory"] = raw_inv
        
        return init_profile
    
    conn.close()
    
    p_dict = dict(row)
    
    # 🛠️ จุดที่ 2: ยกเลิกการใช้ json.loads สำหรับผู้เล่นเก่า (แก้บั๊กที่ทำบอทดับ)
    raw_inv = str(p_dict.get("inventory", ""))
    for char in ["(", ")", "[", "]", "'", '"', " "]:
        raw_inv = raw_inv.replace(char, "")
    p_dict["inventory"] = raw_inv
    
    return p_dict

# ─── 💾 โซนฟังก์ชันจัดการสเตตัสความปลอดภัย ───

def update_player_field(user_id, field, value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if isinstance(value, list) or isinstance(value, dict):
        value = json.dumps(value)
    cursor.execute(f"UPDATE players SET {field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

def increment_player_field(user_id, field, amount=1):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE players SET {field} = {field} + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def update_player_fields(user_id, updates: dict):
    if not updates: return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    set_clauses = []
    values = []
    for field, value in updates.items():
        if isinstance(value, list) or isinstance(value, dict):
            value = json.dumps(value)
        set_clauses.append(f"{field} = ?")
        values.append(value)
        
    values.append(user_id)
    sql = f"UPDATE players SET {', '.join(set_clauses)} WHERE user_id = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()

def add_exp(user_id, exp_to_add):
    player = get_player(user_id)
    # 🗓️ C3 + 🎟️ C2: EXP ทุกทางไหลผ่านที่นี่ที่เดียว — แบ่งไปเป็นแต้มรายสัปดาห์และแต้มซีซั่นด้วย
    try:
        add_weekly_points(user_id, exp_to_add)
        add_season_points(user_id, exp_to_add)
    except Exception as e:
        print(f"⚠️ [score] เก็บแต้มไม่สำเร็จ: {e}")     # ห้ามพังการอัป EXP หลัก
    current_exp = player.get("exp", 0) + exp_to_add
    current_level = player.get("level", 1)
    max_hp = player.get("max_hp", 100)
    level_up_occurred = False
    
    while True:
        if current_level >= 100:
            current_exp = 0
            break
        required_exp = (current_level ** 2) * 70
        if current_exp >= required_exp:
            current_exp -= required_exp
            current_level += 1
            max_hp += 20 
            level_up_occurred = True
        else:
            break
            
    update_player_field(user_id, "exp", current_exp)
    update_player_field(user_id, "level", current_level)
    if level_up_occurred:
        update_player_field(user_id, "max_hp", max_hp)
        update_player_field(user_id, "hp", max_hp) 
    return level_up_occurred, current_level, current_exp

def calculate_rank(level):
    if level >= 100: return "SSS"
    elif level >= 80: return "A"
    elif level >= 50: return "B"
    elif level >= 20: return "C"
    elif level >= 10: return "D"
    elif level >= 5: return "E"
    else: return "F"

def check_and_update_rank(user_id, current_level):
    player = get_player(user_id)
    if not player: return False, "F"
    old_rank = player.get("rank", "F")
    new_rank = calculate_rank(current_level)
    if old_rank != new_rank:
        update_player_field(user_id, "rank", new_rank)
        return True, new_rank
    return False, old_rank

# ─── ⚙️ โซนระบบขยายข้อมูลอัตโนมัติสำหรับอนาคต (Scalability Zone) ───

def auto_update_schema():
    """ระบบตรวจจับคอลัมน์อัตโนมัติ อิงจากตาราง NEW_PLAYER_DEFAULTS"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(players);")
    columns = [row[1] for row in cursor.fetchall()]
    
    # ดักจับคอลัมน์เผื่อเก่าที่จำเป็นต้องมี
    if "exp" not in columns:
        try: cursor.execute("ALTER TABLE players ADD COLUMN exp INTEGER DEFAULT 0;")
        except: pass
    if "rank" not in columns:
        try: cursor.execute("ALTER TABLE players ADD COLUMN rank TEXT DEFAULT 'F';")
        except: pass

    # ลูปสแกนหาตัวแปรใหม่ ๆ ในคลังจอง NEW_PLAYER_DEFAULTS ถ้าไม่มีในเครื่องคลาวด์ จะยัดคำสั่งงอกคอลัมน์ให้เองทันที
    for col_name, default_val in NEW_PLAYER_DEFAULTS.items():
        if col_name not in columns:
            col_type = "TEXT" if isinstance(default_val, str) else "INTEGER"
            d_val = f"'{default_val}'" if isinstance(default_val, str) else default_val
            if default_val is None: d_val = "NULL"
            
            try:
                cursor.execute(f"ALTER TABLE players ADD COLUMN {col_name} {col_type} DEFAULT {d_val};")
                print(f"⚙️ [FUTURE-MIGRATION] งอกคอลัมน์ใหม่ '{col_name}' สำเร็จ!")
            except Exception as e:
                print(f"⚠️ [MIGRATION ERROR] ไม่สามารถงอกฟิลด์ {col_name} ได้: {e}")
                
    conn.commit()
    conn.close()

# นำไปวางล่างสุดของไฟล์ฐานข้อมูล (player_model.py)
def get_top_text_players(limit=10):
    """ดึงข้อมูลผู้เล่นที่พิมพ์เยอะที่สุด 10 อันดับแรก (ไม่นับคนที่ยังไม่เคยพิมพ์)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # ดึงข้อมูลและเรียงลำดับจาก total_text มากไปน้อย จำกัดจำนวนตาม limit
    cursor.execute("""
        SELECT user_id, total_text, event_text 
        FROM players 
        WHERE total_text > 0 
        ORDER BY total_text DESC 
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_players():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # ดึงเฉพาะสิ่งที่ต้องใช้มาครับ
    cursor.execute("SELECT user_id, total_online_time FROM players")
    rows = cursor.fetchall()
    conn.close()
    
    # แปลงกลับเป็น list ของ dict
    players = []
    for row in rows:
        players.append({
            "user_id": row[0],
            "total_online_time": row[1]
        })
    return players

def execute_custom_game_logic(user_id, action_type, **kwargs):
    """
    🔮 [จุดเตรียมพร้อมเพิ่มคำสั่งใหม่ในอนาคต]
    คุณอาเธอร์สามารถมาเขียนดักพวกคำสั่ง Event แปลก ๆ หรือเงื่อนไขใหม่ที่นี่ได้เลยโดยไม่กระทบโครงสร้างหลัก
    """
    player = get_player(user_id)
    if not player: return False
    
    if action_type == "custom_buff":
        # ตัวอย่างลอจิก: สั่งเพิ่มพลังงานหรือบัฟในอนาคต
        pass
        
    return True

# เพิ่มฟังก์ชันนี้ใน player_model.py
def check_jail_status(user_id):
    player = get_player(user_id)
    if player and player["current_state"] == "arrested":
        # ถ้าเวลาปัจจุบัน เกินกว่าเวลาที่กำหนดใน DB
        if time.time() >= player["arrest_until"]:
            update_player_fields(user_id, {"current_state": "idle", "arrest_until": 0})
            return True # หลุดจากคุกแล้ว
    return False # ยังติดคุกอยู่


def execute_raw_sql(sql, params=()):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()  # ต้องมีบรรทัดนี้ ไม่งั้นข้อมูลไม่เซฟ
    conn.close()

def load_inventory(raw_inv):
    """ฟังก์ชันสำหรับโหลดและแปลงกระเป๋าเป็น List เสมอ"""
    # 1. ถ้าเป็น List อยู่แล้ว ส่งคืนทันที
    if isinstance(raw_inv, list):
        return raw_inv
    
    # 2. ถ้าเป็นค่าว่างหรือค่าที่อ่านไม่ได้
    if not raw_inv or raw_inv in ["None", "null", ""]:
        return []
    
    # 3. ลองอ่านแบบ JSON — การันตีคืน list เสมอ (inventory ชิ้นเดียวเช่น "15" ต้องได้ ["15"] ไม่ใช่ int)
    try:
        parsed = json.loads(raw_inv)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        return [str(parsed)]
    except (json.JSONDecodeError, TypeError):
        # 4. ถ้าไม่ใช่ JSON ให้ใช้วิธีล้าง String แล้ว Split
        clean_inv = str(raw_inv).replace("[", "").replace("]", "").replace("'", "").replace('"', "").replace(" ", "")
        return [x for x in clean_inv.split(",") if x]

# ===== 📕 สมุดสะสมมอนสเตอร์ (Bestiary) =====

def _ensure_bestiary(cursor):
    """สร้างตารางสมุดล่าถ้ายังไม่มี — เรียกซ้ำได้ปลอดภัย (IF NOT EXISTS)"""
    cursor.execute("""CREATE TABLE IF NOT EXISTS bestiary (
        user_id INTEGER, continent TEXT, rank TEXT, kills INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, continent, rank))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS bestiary_rewards (
        user_id INTEGER, reward_key TEXT,
        PRIMARY KEY (user_id, reward_key))""")


def record_bestiary_kill(user_id, continent, rank):
    """จดมอนที่ล้มลงสมุด — ช่อง (ทวีป, แรงค์) ละแถว นับจำนวนสะสม"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_bestiary(cursor)
    cursor.execute("""INSERT INTO bestiary (user_id, continent, rank, kills) VALUES (?, ?, ?, 1)
                      ON CONFLICT(user_id, continent, rank) DO UPDATE SET kills = kills + 1""",
                   (user_id, continent, rank))
    conn.commit()
    conn.close()


def get_bestiary(user_id):
    """คืนสมุดทั้งเล่ม: {(continent, rank): kills}"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_bestiary(cursor)
    cursor.execute("SELECT continent, rank, kills FROM bestiary WHERE user_id = ?", (user_id,))
    rows = {(c, r): k for c, r, k in cursor.fetchall()}
    conn.close()
    return rows


def get_claimed_rewards(user_id):
    """คีย์รางวัลทั้งหมดที่ผู้เล่นเคยรับแล้ว (ใช้เช็คว่าปลดความสำเร็จอะไรไปบ้าง)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_bestiary(cursor)
    cursor.execute("SELECT reward_key FROM bestiary_rewards WHERE user_id = ?", (user_id,))
    keys = {r[0] for r in cursor.fetchall()}
    conn.close()
    return keys


def claim_bestiary_reward(user_id, reward_key):
    """จองรางวัลครั้งเดียวต่อ key — True = เพิ่งได้สิทธิ์ (ยังไม่เคยรับ), False = รับไปแล้ว

    เป็นสมุดจอง "ครั้งเดียวต่อคีย์" ทั่วไป ไม่ผูกกับสมุดล่าอย่างเดียว —
    ความสำเร็จ (C8) ใช้ตัวนี้ด้วยผ่านชื่อ claim_once() คีย์ขึ้นต้น "ach:"
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_bestiary(cursor)
    cursor.execute("INSERT OR IGNORE INTO bestiary_rewards (user_id, reward_key) VALUES (?, ?)",
                   (user_id, reward_key))
    is_new = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return is_new


# ===== ⚖️ ล่าค่าหัว (Bounty) — P4 =====

def get_outlaws():
    """รายชื่อผู้เล่นสติติดลบ (อาชญากรมีค่าหัว) เรียงจากคลั่งหนักสุด — [(user_id, sanity), ...]"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, sanity FROM players WHERE sanity < 0 ORDER BY sanity ASC")
    rows = cursor.fetchall()
    conn.close()
    return rows


# ===== ⚔️ แต้มสงครามฝ่าย (Faction War) — P5 =====

def _war_week():
    """คีย์สัปดาห์ ISO ปัจจุบัน เช่น '2026-W31' — แต้มสงครามนับแยกรายสัปดาห์"""
    import datetime
    y, w, _ = datetime.date.today().isocalendar()
    return f"{y}-W{w:02d}"


def _ensure_war_table(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS faction_war_score (
        week TEXT, faction TEXT, points INTEGER DEFAULT 0,
        PRIMARY KEY (week, faction))""")


def add_faction_war_point(faction, week=None):
    """+1 แต้มให้ฝ่าย แล้วคืนสกอร์ล่าสุดของสัปดาห์นั้น"""
    week = week or _war_week()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_war_table(cursor)
    cursor.execute("""INSERT INTO faction_war_score (week, faction, points) VALUES (?, ?, 1)
                      ON CONFLICT(week, faction) DO UPDATE SET points = points + 1""",
                   (week, faction))
    conn.commit()
    conn.close()
    return get_faction_war_scores(week)


def get_faction_war_scores(week=None):
    """สกอร์สัปดาห์นี้: {"human": x, "demon": y} (ไม่มีแต้ม = 0)"""
    week = week or _war_week()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_war_table(cursor)
    cursor.execute("SELECT faction, points FROM faction_war_score WHERE week = ?", (week,))
    scores = {"human": 0, "demon": 0}
    scores.update(dict(cursor.fetchall()))
    conn.close()
    return scores


# ===== 🏰 ระบบกิลด์ (Guild) — P6 =====

def _ensure_guild_tables(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS guilds (
        guild_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, icon TEXT,
        leader_id INTEGER UNIQUE,
        role_id INTEGER, channel_id INTEGER,
        treasury INTEGER DEFAULT 0)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS guild_members (
        user_id INTEGER PRIMARY KEY,   -- 1 คนอยู่ได้กิลด์เดียว บังคับที่ PK
        guild_id INTEGER)""")


def create_guild(name, icon, leader_id, role_id, channel_id):
    """สร้างกิลด์ + หัวหน้าเข้าเป็นสมาชิกแถวแรก — คืน guild_id หรือ None ถ้าชื่อ/หัวหน้าซ้ำ"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_tables(cursor)
    try:
        cursor.execute("INSERT INTO guilds (name, icon, leader_id, role_id, channel_id) VALUES (?, ?, ?, ?, ?)",
                       (name, icon, leader_id, role_id, channel_id))
        gid = cursor.lastrowid
        cursor.execute("INSERT OR REPLACE INTO guild_members (user_id, guild_id) VALUES (?, ?)", (leader_id, gid))
        conn.commit()
        return gid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def _guild_row_to_dict(row):
    if not row:
        return None
    keys = ("guild_id", "name", "icon", "leader_id", "role_id", "channel_id", "treasury")
    return dict(zip(keys, row))


def get_guild_of(user_id):
    """กิลด์ที่ผู้เล่นสังกัด — ไม่มี = None"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_tables(cursor)
    cursor.execute("""SELECT g.guild_id, g.name, g.icon, g.leader_id, g.role_id, g.channel_id, g.treasury
                      FROM guilds g JOIN guild_members m ON m.guild_id = g.guild_id
                      WHERE m.user_id = ?""", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return _guild_row_to_dict(row)


def get_guild_by_name(name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_tables(cursor)
    cursor.execute("""SELECT guild_id, name, icon, leader_id, role_id, channel_id, treasury
                      FROM guilds WHERE name = ?""", (name,))
    row = cursor.fetchone()
    conn.close()
    return _guild_row_to_dict(row)


def add_guild_member(user_id, guild_id):
    """เพิ่มสมาชิก — False ถ้าเขาอยู่กิลด์อื่นแล้ว"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_tables(cursor)
    cursor.execute("INSERT OR IGNORE INTO guild_members (user_id, guild_id) VALUES (?, ?)", (user_id, guild_id))
    ok = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def remove_guild_member(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_tables(cursor)
    cursor.execute("DELETE FROM guild_members WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_guild_members(guild_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_tables(cursor)
    cursor.execute("SELECT user_id FROM guild_members WHERE guild_id = ?", (guild_id,))
    rows = [r[0] for r in cursor.fetchall()]
    conn.close()
    return rows


def guild_add_treasury(guild_id, delta):
    """บวก/ลบคลังกิลด์ — คืนยอดใหม่ หรือ None ถ้าจะติดลบ (ห้ามถอนเกิน)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_tables(cursor)
    cursor.execute("SELECT treasury FROM guilds WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    if row is None or row[0] + delta < 0:
        conn.close()
        return None
    new_total = row[0] + delta
    cursor.execute("UPDATE guilds SET treasury = ? WHERE guild_id = ?", (new_total, guild_id))
    conn.commit()
    conn.close()
    return new_total


def delete_guild(guild_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_tables(cursor)
    cursor.execute("DELETE FROM guild_members WHERE guild_id = ?", (guild_id,))
    cursor.execute("DELETE FROM guilds WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()


# ===== ⚔️ เดิมพันกิลด์วอร์ (P7) — จดลง DB กันเงินหายถ้าบอทรีสตาร์ทกลางศึก =====

def _ensure_war_stakes(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS guild_war_stakes (
        channel_id INTEGER PRIMARY KEY, guild_a INTEGER, guild_b INTEGER, stake INTEGER)""")


def record_war_stake(channel_id, guild_a, guild_b, stake):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_war_stakes(cursor)
    cursor.execute("INSERT OR REPLACE INTO guild_war_stakes VALUES (?, ?, ?, ?)",
                   (channel_id, guild_a, guild_b, stake))
    conn.commit()
    conn.close()


def pop_war_stake(channel_id):
    """ดึง+ลบเดิมพันของศึกนี้ — คืน (guild_a, guild_b, stake) หรือ None"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_war_stakes(cursor)
    cursor.execute("SELECT guild_a, guild_b, stake FROM guild_war_stakes WHERE channel_id = ?", (channel_id,))
    row = cursor.fetchone()
    cursor.execute("DELETE FROM guild_war_stakes WHERE channel_id = ?", (channel_id,))
    conn.commit()
    conn.close()
    return row


def pop_all_war_stakes():
    """ดึง+ลบเดิมพันค้างทั้งหมด (ศึกที่ตายเพราะรีสตาร์ท) — [(channel_id, guild_a, guild_b, stake), ...]"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_war_stakes(cursor)
    cursor.execute("SELECT channel_id, guild_a, guild_b, stake FROM guild_war_stakes")
    rows = cursor.fetchall()
    cursor.execute("DELETE FROM guild_war_stakes")
    conn.commit()
    conn.close()
    return rows


def rename_guild(guild_id, new_name):
    """เปลี่ยนชื่อกิลด์ — False ถ้าชื่อใหม่ซ้ำกับกิลด์อื่น"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_tables(cursor)
    try:
        cursor.execute("UPDATE guilds SET name = ? WHERE guild_id = ?", (new_name, guild_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# ===== 🌍 ห้องผจญภัยรายเซิร์ฟ (P8) — เซิร์ฟรองตั้งได้หลายห้อง =====

def _ensure_guild_settings(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS guild_adv_channels (
        guild_id INTEGER, channel_id INTEGER,
        PRIMARY KEY (guild_id, channel_id))""")


def add_adv_channel(guild_id, channel_id):
    """เพิ่มห้องเล่นของเซิร์ฟนั้น — False = มีอยู่แล้ว"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_settings(cursor)
    cursor.execute("INSERT OR IGNORE INTO guild_adv_channels VALUES (?, ?)", (guild_id, channel_id))
    added = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return added


def remove_adv_channel(guild_id, channel_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_settings(cursor)
    cursor.execute("DELETE FROM guild_adv_channels WHERE guild_id = ? AND channel_id = ?",
                   (guild_id, channel_id))
    removed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return removed


def get_adv_channels(guild_id):
    """ห้องเล่นทั้งหมดของเซิร์ฟนี้ — ว่าง = ยังไม่ตั้ง"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_guild_settings(cursor)
    cursor.execute("SELECT channel_id FROM guild_adv_channels WHERE guild_id = ?", (guild_id,))
    rows = [r[0] for r in cursor.fetchall()]
    conn.close()
    return rows


# ===== 🏆 อันดับรวม (O6) — ดึงทุกหมวดผ่านฟังก์ชันเดียว =====

LEADERBOARD_SQL = {
    "rich":  "SELECT user_id, (bank + cash) FROM players ORDER BY (bank + cash) DESC LIMIT ?",
    "level": "SELECT user_id, level FROM players ORDER BY level DESC, exp DESC LIMIT ?",
    "text":  "SELECT user_id, total_text FROM players ORDER BY total_text DESC LIMIT ?",
    "time":  "SELECT user_id, total_online_time FROM players ORDER BY total_online_time DESC LIMIT ?",
}


def get_leaderboard(kind, limit=10):
    """อันดับตามหมวด — คืน [(user_id, ค่า), ...] เรียงมากไปน้อย"""
    if kind == "weekly":
        return get_weekly_top(limit)          # อยู่คนละตาราง (รีเซ็ตทุกสัปดาห์)
    if kind not in LEADERBOARD_SQL:
        return []
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(LEADERBOARD_SQL[kind], (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_my_rank(user_id, kind):
    """อันดับของเราในหมวดนั้น — คืน (อันดับ, ค่าของเรา, จำนวนผู้เล่นทั้งหมด) หรือ None"""
    if kind == "weekly":
        return get_my_weekly_rank(user_id)
    if kind not in LEADERBOARD_SQL:
        return None
    col = {"rich": "(bank + cash)", "level": "level", "text": "total_text", "time": "total_online_time"}[kind]
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"SELECT {col} FROM players WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return None
    my_value = row[0] or 0
    cursor.execute(f"SELECT COUNT(*) FROM players WHERE {col} > ?", (my_value,))
    better = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM players")
    total = cursor.fetchone()[0]
    conn.close()
    return better + 1, my_value, total


# ===== 🗓️ อันดับรายสัปดาห์ (C3) =====
# แต้ม = EXP ที่หาได้ในสัปดาห์นั้น (ยิงจาก add_exp จุดเดียว ครอบคลุมทั้งล่ามอน/บอส/เควส)
# ไม่ต้องรีเซ็ตอะไรเลย — ขึ้นสัปดาห์ใหม่ = คีย์ใหม่ = เริ่มนับศูนย์เอง

def week_key(when=None):
    """คีย์สัปดาห์ ISO เช่น '2026-W31' — ต้องตรงกับที่ cog weekly_event ใช้เป๊ะ"""
    import datetime
    year, week, _ = (when or datetime.date.today()).isocalendar()
    return f"{year}-W{week}"


def _ensure_weekly(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS weekly_score (
        week TEXT, user_id INTEGER, points INTEGER DEFAULT 0,
        PRIMARY KEY (week, user_id))""")


def add_weekly_points(user_id, points, week=None):
    if points <= 0:
        return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_weekly(cursor)
    cursor.execute("""INSERT INTO weekly_score (week, user_id, points) VALUES (?, ?, ?)
                      ON CONFLICT(week, user_id) DO UPDATE SET points = points + ?""",
                   (week or week_key(), user_id, int(points), int(points)))
    conn.commit()
    conn.close()


def get_weekly_top(limit=10, week=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_weekly(cursor)
    cursor.execute("""SELECT user_id, points FROM weekly_score
                      WHERE week = ? AND points > 0 ORDER BY points DESC LIMIT ?""",
                   (week or week_key(), limit))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_my_weekly_rank(user_id, week=None):
    """คืน (อันดับ, แต้ม, จำนวนคนที่ลงแข่งสัปดาห์นี้) — ยังไม่มีแต้ม = อันดับบ๊วยสุด"""
    week = week or week_key()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_weekly(cursor)
    cursor.execute("SELECT points FROM weekly_score WHERE week = ? AND user_id = ?", (week, user_id))
    row = cursor.fetchone()
    mine = (row[0] if row else 0) or 0
    cursor.execute("SELECT COUNT(*) FROM weekly_score WHERE week = ? AND points > ?", (week, mine))
    better = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM weekly_score WHERE week = ? AND points > 0", (week,))
    total = cursor.fetchone()[0]
    conn.close()
    return better + 1, mine, max(total, 1 if mine else total)


# ===== 🎟️ Season Pass รายเดือน (C2) =====
# แต้มซีซั่นมาจาก add_exp จุดเดียวกับอันดับรายสัปดาห์ — ขึ้นเดือนใหม่ = คีย์ใหม่ = เริ่มใหม่เอง
# สถานะ premium + ตำแหน่งที่รับรางวัลไปแล้ว เก็บในสมุด claim_once ไม่ต้องมีตารางเพิ่ม

def season_key(when=None):
    """คีย์ซีซั่น = เดือนปฏิทิน เช่น '2026-07'"""
    import datetime
    return (when or datetime.date.today()).strftime("%Y-%m")


def _ensure_season(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS season_score (
        season TEXT, user_id INTEGER, points INTEGER DEFAULT 0,
        PRIMARY KEY (season, user_id))""")


def add_season_points(user_id, points, season=None):
    if points <= 0:
        return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_season(cursor)
    cursor.execute("""INSERT INTO season_score (season, user_id, points) VALUES (?, ?, ?)
                      ON CONFLICT(season, user_id) DO UPDATE SET points = points + ?""",
                   (season or season_key(), user_id, int(points), int(points)))
    conn.commit()
    conn.close()


def get_season_points(user_id, season=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_season(cursor)
    cursor.execute("SELECT points FROM season_score WHERE season = ? AND user_id = ?",
                   (season or season_key(), user_id))
    row = cursor.fetchone()
    conn.close()
    return (row[0] if row else 0) or 0


# ===== 📅 เควสรายวัน + Login Streak (C1) =====

def _today():
    import datetime
    return datetime.date.today().isoformat()


def _ensure_daily(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS daily_quests (
        user_id INTEGER, day TEXT, quest_key TEXT, progress INTEGER DEFAULT 0,
        claimed INTEGER DEFAULT 0, PRIMARY KEY (user_id, day, quest_key))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS login_streak (
        user_id INTEGER PRIMARY KEY, last_day TEXT, streak INTEGER DEFAULT 0, best INTEGER DEFAULT 0)""")


def get_daily_progress(user_id, day=None):
    """ความคืบหน้าเควสวันนี้ — {quest_key: (progress, claimed)}"""
    day = day or _today()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_daily(cursor)
    cursor.execute("SELECT quest_key, progress, claimed FROM daily_quests WHERE user_id = ? AND day = ?",
                   (user_id, day))
    rows = {k: (p, bool(c)) for k, p, c in cursor.fetchall()}
    conn.close()
    return rows


def add_daily_progress(user_id, quest_key, amount=1, day=None):
    """+ความคืบหน้าเควส — คืนค่าสะสมใหม่ (เควสที่รับรางวัลแล้วไม่นับต่อ)"""
    day = day or _today()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_daily(cursor)
    cursor.execute("""INSERT INTO daily_quests (user_id, day, quest_key, progress) VALUES (?, ?, ?, ?)
                      ON CONFLICT(user_id, day, quest_key) DO UPDATE SET progress = progress + ?""",
                   (user_id, day, quest_key, amount, amount))
    cursor.execute("SELECT progress FROM daily_quests WHERE user_id = ? AND day = ? AND quest_key = ?",
                   (user_id, day, quest_key))
    total = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return total


def claim_daily(user_id, quest_key, day=None):
    """รับรางวัลเควส — True = เพิ่งรับสำเร็จ, False = รับไปแล้ว"""
    day = day or _today()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_daily(cursor)
    cursor.execute("UPDATE daily_quests SET claimed = 1 WHERE user_id = ? AND day = ? AND quest_key = ? AND claimed = 0",
                   (user_id, day, quest_key))
    ok = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def touch_login_streak(user_id, day=None):
    """เช็คอินรายวัน — คืน (streak, best, เพิ่งเช็คอินวันนี้ครั้งแรก?)"""
    import datetime
    day = day or _today()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_daily(cursor)
    cursor.execute("SELECT last_day, streak, best FROM login_streak WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row[0] == day:
        conn.close()
        return row[1], row[2], False        # เช็คอินไปแล้ววันนี้
    if row:
        yesterday = (datetime.date.fromisoformat(day) - datetime.timedelta(days=1)).isoformat()
        streak = row[1] + 1 if row[0] == yesterday else 1   # ขาดวัน = เริ่มนับใหม่
        best = max(row[2], streak)
    else:
        streak, best = 1, 1
    cursor.execute("INSERT OR REPLACE INTO login_streak (user_id, last_day, streak, best) VALUES (?, ?, ?, ?)",
                   (user_id, day, streak, best))
    conn.commit()
    conn.close()
    return streak, best, True


def get_best_streak(user_id):
    """สถิติล็อกอินต่อเนื่องสูงสุด — อ่านอย่างเดียว ไม่เช็คอินให้ (ต่างจาก touch_login_streak)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    _ensure_daily(cursor)
    cursor.execute("SELECT best FROM login_streak WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return (row[0] if row else 0) or 0


# สมุดจอง "ครั้งเดียวต่อคีย์" ใช้ร่วมกันได้ทุกระบบ — ความสำเร็จ (C8) เรียกผ่านชื่อนี้
claim_once = claim_bestiary_reward
