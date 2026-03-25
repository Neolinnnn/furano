# -*- coding: utf-8 -*-
"""
db.py - 資料存取層 (Data Access Layer)
所有 SQLite CRUD 操作都封裝在這裡。
"""
import sqlite3
import os
import csv
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "expenses.db")
CSV_FILE = os.path.join(BASE_DIR, "北海道花費(資料庫).csv")
MEMBERS_FILE = os.path.join(BASE_DIR, "人員.md")

JPY_TO_TWD = 0.2038  # 台銀 2026/03 中旬即期賣出

# 暱稱 → 全名 對應表
NICKNAME_MAP = {
    "翰": "林廷翰", "廷翰": "林廷翰", "林廷翰": "林廷翰",
    "君翰": "林君翰", "君": "林君翰", "林君翰": "林君翰",
    "定": "定定", "定定": "定定",
    "祥": "李鴻祥", "祥哥": "李鴻祥", "李鴻祥": "李鴻祥",
    "智": "張銘智", "阿智": "張銘智", "張銘智": "張銘智",
    "儒": "黃珮儒", "黃珮儒": "黃珮儒",
    "巧衣": "王巧衣", "王巧衣": "王巧衣",
    "大為": "林大為", "林大為": "林大為", "大維": "林大為",
    "雨玄": "王雨玄", "王雨玄": "王雨玄",
    "辣椒": "辣椒", "椒": "辣椒",
}


def get_db():
    """取得 DB 連線"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 允許併發讀取
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """建立資料表（如果不存在）"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            bank_name TEXT DEFAULT '',
            bank_account TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT DEFAULT '',
            item TEXT DEFAULT '',
            note TEXT DEFAULT '',
            payer TEXT DEFAULT '',
            debtors TEXT DEFAULT '',
            amount_twd REAL,
            amount_jpy REAL,
            category TEXT DEFAULT '',
            status TEXT DEFAULT 'ok',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


# ===== 暱稱解析 =====

def resolve_name(nickname):
    """暱稱轉全名"""
    nickname = nickname.strip()
    return NICKNAME_MAP.get(nickname, nickname)


def parse_payers(payer_str):
    """解析代墊人（可能有多人，如 '祥哥&阿智'）"""
    if not payer_str or payer_str.strip() == "各自負擔":
        return []
    parts = re.split(r"[&＆、]", payer_str)
    return [resolve_name(p.strip()) for p in parts if p.strip()]


def parse_debtors_str(debtor_str, all_members):
    """解析應付人員字串，回傳名單"""
    if not debtor_str or not debtor_str.strip():
        return list(all_members)
    parts = re.split(r"[\s,，、]+", debtor_str.strip())
    return [resolve_name(p) for p in parts if p.strip()]


def parse_amount_from_note(note):
    """從備註欄解析金額，回傳 (amount_twd, amount_jpy)"""
    if not note:
        return None, None

    jpy_patterns = [
        r"(\d[\d,]*)\s*(?:JPY|¥|日圓|日幣|円|yen|YEN|圓)(?!\w)",
        r"(?:JPY|¥|日圓|日幣|円|yen|YEN|圓)\s*(\d[\d,]*)",
    ]
    for pattern in jpy_patterns:
        m = re.search(pattern, note, re.IGNORECASE)
        if m:
            amount = int(m.group(1).replace(",", ""))
            return None, amount

    twd_patterns = [
        r"(\d[\d,]*)\s*(?:NTD|TWD|NT\$|台幣|元|塊)(?!\w)",
        r"(?:NTD|TWD|NT\$|台幣)\s*(\d[\d,]*)",
    ]
    for pattern in twd_patterns:
        m = re.search(pattern, note, re.IGNORECASE)
        if m:
            amount = int(m.group(1).replace(",", ""))
            return amount, None

    # Fallback: 純數字 > 5000 當日幣
    m = re.search(r"(?<!\S)(\d{4,})(?!\S)", note)
    if m:
        amount = int(m.group(1).replace(",", ""))
        if amount > 5000:
            return None, amount
        return amount, None

    return None, None


# ===== Members CRUD =====

def get_members():
    """取得所有成員名稱列表"""
    conn = get_db()
    rows = conn.execute("SELECT name FROM members ORDER BY id").fetchall()
    conn.close()
    return [r["name"] for r in rows]


def get_bank_accounts():
    """取得所有銀行帳號"""
    conn = get_db()
    rows = conn.execute(
        "SELECT name, bank_name, bank_account FROM members WHERE bank_name != '' OR bank_account != ''"
    ).fetchall()
    conn.close()
    return {r["name"]: {"bank": r["bank_name"], "account": r["bank_account"]} for r in rows}


def save_bank_account(name, bank, account):
    """儲存銀行帳號"""
    conn = get_db()
    conn.execute(
        "UPDATE members SET bank_name=?, bank_account=? WHERE name=?",
        (bank, account, name)
    )
    conn.commit()
    conn.close()
    # 同步更新 人員.md
    _sync_members_md()


def delete_bank_account(name):
    """刪除銀行帳號"""
    conn = get_db()
    conn.execute(
        "UPDATE members SET bank_name='', bank_account='' WHERE name=?",
        (name,)
    )
    conn.commit()
    conn.close()
    _sync_members_md()


def _sync_members_md():
    """將 DB 的人員資訊同步回 人員.md"""
    conn = get_db()
    rows = conn.execute("SELECT name, bank_name, bank_account FROM members ORDER BY id").fetchall()
    conn.close()

    lines = ["# 成員名單\n"]
    for r in rows:
        if r["bank_name"] and r["bank_account"]:
            lines.append(f"{r['name']} | {r['bank_name']} | {r['bank_account']}")
        else:
            lines.append(r["name"])

    with open(MEMBERS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ===== Expenses CRUD =====

def get_expenses():
    """取得所有花費，含計算欄位"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()
    conn.close()
    all_members = get_members()

    expenses = []
    for row in rows:
        payer_str = row["payer"]
        debtor_str = row["debtors"]

        # 各自負擔
        if payer_str == "各自負擔":
            expenses.append({
                "id": row["id"],
                "date": row["date"] or "",
                "item": row["item"] or "",
                "payer": "各自負擔",
                "payers": [],
                "note": row["note"] or "",
                "debtors": [],
                "debtor_str": debtor_str,
                "amount_twd": row["amount_twd"],
                "amount_jpy": row["amount_jpy"],
                "amount_twd_total": None,
                "category": row["category"] or "",
                "status": "各自負擔",
            })
            continue

        payers = parse_payers(payer_str)
        debtors = parse_debtors_str(debtor_str, all_members)

        amount_twd = row["amount_twd"]
        amount_jpy = row["amount_jpy"]

        # 若兩個都空，從 note 解析
        if amount_twd is None and amount_jpy is None:
            note_twd, note_jpy = parse_amount_from_note(row["note"] or "")
            amount_twd = note_twd
            amount_jpy = note_jpy

        # 算台幣總額
        amount_twd_total = None
        status = row["status"] or "ok"
        if status not in ("各自負擔", "待確認"):
            if amount_twd is not None and amount_jpy is not None:
                amount_twd_total = amount_twd + amount_jpy * JPY_TO_TWD
            elif amount_twd is not None:
                amount_twd_total = amount_twd
            elif amount_jpy is not None:
                amount_twd_total = amount_jpy * JPY_TO_TWD
            else:
                status = "待確認"

        expenses.append({
            "id": row["id"],
            "date": row["date"] or "",
            "item": row["item"] or "",
            "payer": payer_str,
            "payers": payers,
            "note": row["note"] or "",
            "debtors": debtors,
            "debtor_str": debtor_str,
            "amount_twd": amount_twd,
            "amount_jpy": amount_jpy,
            "amount_twd_total": amount_twd_total,
            "category": row["category"] or "",
            "status": status,
        })

    return expenses


def add_expense(data):
    """新增一筆花費"""
    conn = get_db()
    conn.execute("""
        INSERT INTO expenses (date, item, note, payer, debtors, amount_twd, amount_jpy, category, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("日期", ""),
        data.get("項目", ""),
        data.get("備註", ""),
        data.get("代墊人", ""),
        data.get("應付人員", ""),
        _parse_num(data.get("金額-台幣")),
        _parse_num(data.get("金額-日幣")),
        data.get("類別", ""),
        "ok",
    ))
    conn.commit()
    conn.close()


def update_expense(expense_id, data):
    """更新一筆花費的指定欄位"""
    # 前端欄位名 → DB 欄位名
    field_map = {
        "日期": "date",
        "項目": "item",
        "備註": "note",
        "代墊人": "payer",
        "應付人員": "debtors",
        "金額-台幣": "amount_twd",
        "金額-日幣": "amount_jpy",
        "類別": "category",
    }

    conn = get_db()
    for zh_key, value in data.items():
        db_col = field_map.get(zh_key)
        if db_col:
            if db_col in ("amount_twd", "amount_jpy"):
                value = _parse_num(value)
            conn.execute(f"UPDATE expenses SET {db_col}=? WHERE id=?", (value, expense_id))
    conn.commit()
    conn.close()


def delete_expense(expense_id):
    """刪除一筆花費"""
    conn = get_db()
    result = conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    deleted = result.rowcount
    conn.close()
    return deleted > 0


def get_summary():
    """Dashboard 統計"""
    expenses = get_expenses()
    total_twd = 0
    total_jpy = 0
    calculated_twd = 0
    count = 0

    for exp in expenses:
        if exp["status"] != "各自負擔":
            count += 1
            if exp["amount_twd"] is not None:
                total_twd += exp["amount_twd"]
            if exp["amount_jpy"] is not None:
                total_jpy += exp["amount_jpy"]
            if exp["amount_twd_total"] is not None:
                calculated_twd += exp["amount_twd_total"]

    return {
        "count": count,
        "total_twd": round(total_twd, 0),
        "total_jpy": round(total_jpy, 0),
        "calculated_twd": round(calculated_twd, 0),
    }


# ===== Settlement =====

def calculate_settlement():
    """計算拆帳結果"""
    expenses = get_expenses()
    all_members = get_members()

    balance = {m: 0.0 for m in all_members}
    user_details = {m: [] for m in all_members}

    for exp in expenses:
        if exp["status"] in ("各自負擔", "待確認"):
            continue
        if not exp["payers"] or exp["amount_twd_total"] is None:
            continue

        total = exp["amount_twd_total"]
        payers = exp["payers"]
        debtors = exp["debtors"]

        if not debtors:
            debtors = list(all_members)

        per_person = total / len(debtors)
        per_payer_paid = total / len(payers)

        for p in payers:
            if p in balance:
                balance[p] += per_payer_paid
                user_details[p].append({
                    "id": exp["id"],
                    "date": exp.get("date", "-"),
                    "item": exp.get("item", ""),
                    "note": exp["note"],
                    "category": exp.get("category", "-"),
                    "type": "pay",
                    "amount": per_payer_paid,
                    "desc": f"代墊 ({len(payers)}人平分)" if len(payers) > 1 else "代墊全額"
                })

        for d in debtors:
            if d in balance:
                balance[d] -= per_person
                user_details[d].append({
                    "id": exp["id"],
                    "date": exp.get("date", "-"),
                    "item": exp.get("item", ""),
                    "note": exp["note"],
                    "category": exp.get("category", "-"),
                    "type": "owe",
                    "amount": per_person,
                    "desc": f"應付 ({len(debtors)}人平分)"
                })

    transfers = _minimize_transfers(balance)

    return {
        "balance": {k: round(v, 0) for k, v in balance.items()},
        "transfers": transfers,
        "user_details": user_details,
    }


def _minimize_transfers(balance):
    """最小化轉帳次數的貪心演算法"""
    creditors = []
    debtors = []

    for name, amount in balance.items():
        if amount > 1:
            creditors.append([name, amount])
        elif amount < -1:
            debtors.append([name, -amount])

    creditors.sort(key=lambda x: -x[1])
    debtors.sort(key=lambda x: -x[1])

    transfers = []
    i, j = 0, 0
    while i < len(creditors) and j < len(debtors):
        c_name, c_amt = creditors[i]
        d_name, d_amt = debtors[j]
        transfer = min(c_amt, d_amt)

        transfers.append({
            "from": d_name,
            "to": c_name,
            "amount": round(transfer, 0),
        })

        creditors[i][1] -= transfer
        debtors[j][1] -= transfer

        if creditors[i][1] < 1:
            i += 1
        if debtors[j][1] < 1:
            j += 1

    return transfers


# ===== MD 生成 =====

def generate_expense_md():
    """根據 DB 資料重新生成 北海道花費.md"""
    expenses = get_expenses()
    all_members = get_members()

    categories_order = ["住宿", "交通", "移動", "雪場", "門票/活動", "餐飲"]
    grouped = {}
    for exp in expenses:
        cat = exp.get("category", "") or "其他"
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(exp)

    lines = [
        "# 北海道花費明細\n",
        "",
        f"> 匯率：1 JPY = {JPY_TO_TWD} TWD（台銀 2026/03 中旬）\n",
        "",
    ]

    idx = 1
    for cat in categories_order:
        if cat not in grouped:
            continue
        items = grouped.pop(cat)
        lines.append(f"## {cat}\n")
        lines.append("")
        lines.append("| # | 日期 | 項目 | 備註 | 代墊人 | 應付人員 | 台幣 | 日幣 | 類別 | 狀態 |")
        lines.append("|---|------|------|------|--------|----------|------|------|------|------|")
        for exp in items:
            item = exp.get("item", "-") or "-"
            note = exp["note"]
            note = re.sub(r'\s*\(https://www\.notion\.so/[^)]*\)', '', note)
            note = re.sub(r'\s*https://www\.notion\.so/\S+', '', note)
            note = note.strip().replace('|', '｜').replace('\n', ' ')

            payers = exp.get("payers", [])
            payer_str = exp["payer"]
            if payers:
                payer_display = "、".join(payers)
            elif payer_str == "各自負擔":
                payer_display = "各自負擔"
            else:
                payer_display = payer_str

            debtors = exp.get("debtors", [])
            debtor_str_raw = exp.get("debtor_str", "")
            if exp["status"] == "各自負擔":
                debtor_display = "-"
            elif debtor_str_raw == "待確認":
                debtor_display = "待確認"
            elif not debtors or len(debtors) >= len(all_members):
                debtor_display = "全員"
            else:
                debtor_display = "、".join(debtors)

            twd = f"{int(exp['amount_twd']):,}" if exp.get("amount_twd") is not None else "-"
            jpy = f"{int(exp['amount_jpy']):,}" if exp.get("amount_jpy") is not None else "-"

            if exp["status"] == "ok":
                status = "✓"
            elif exp["status"] == "各自負擔":
                status = "各自負擔"
            else:
                status = "⚠ 待確認"

            date = exp.get("date", "-") or "-"
            lines.append(
                f"| {idx} | {date} | {item} | {note} | {payer_display} | {debtor_display} | {twd} | {jpy} | {exp.get('category', '-')} | {status} |"
            )
            idx += 1
        lines.append("")

    # 剩餘未分類
    for cat, items in grouped.items():
        lines.append(f"## {cat}\n")
        lines.append("")
        lines.append("| # | 日期 | 項目 | 備註 | 代墊人 | 應付人員 | 台幣 | 日幣 | 類別 | 狀態 |")
        lines.append("|---|------|------|------|--------|----------|------|------|------|------|")
        for exp in items:
            item = exp.get("item", "-") or "-"
            note = re.sub(r'\s*\(https://www\.notion\.so/[^)]*\)', '', exp["note"])
            note = note.strip().replace('|', '｜').replace('\n', ' ')
            date = exp.get("date", "-") or "-"
            payers = exp.get("payers", [])
            payer_display = "、".join(payers) if payers else exp["payer"]
            debtors = exp.get("debtors", [])
            debtor_display = "全員" if not debtors or len(debtors) >= len(all_members) else "、".join(debtors)
            twd = f"{int(exp['amount_twd']):,}" if exp.get("amount_twd") is not None else "-"
            jpy = f"{int(exp['amount_jpy']):,}" if exp.get("amount_jpy") is not None else "-"
            status = "✓" if exp["status"] == "ok" else "⚠ 待確認"
            lines.append(
                f"| {idx} | {date} | {item} | {note} | {payer_display} | {debtor_display} | {twd} | {jpy} | {cat} | {status} |"
            )
            idx += 1
        lines.append("")

    md_path = os.path.join(BASE_DIR, "北海道花費.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ===== CSV Import / Export =====

def import_csv_to_db():
    """將 CSV 匯入到 SQLite（僅在 DB 為空時執行）"""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    if count > 0:
        conn.close()
        return False  # 已有資料，不重複匯入

    # 先匯入成員
    _import_members_from_md(conn)

    all_members = [r["name"] for r in conn.execute("SELECT name FROM members ORDER BY id").fetchall()]

    # 匯入花費
    if not os.path.exists(CSV_FILE):
        conn.close()
        return False

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            payer_str = (row.get("代墊人") or "").strip()

            # 解析金額
            amount_twd = None
            amount_jpy = None
            twd_str = (row.get("金額-台幣") or "").replace(",", "").strip()
            jpy_str = (row.get("金額-日幣") or "").replace(",", "").strip()

            if twd_str:
                try:
                    amount_twd = float(twd_str)
                except ValueError:
                    pass
            if jpy_str:
                try:
                    amount_jpy = float(jpy_str)
                except ValueError:
                    pass

            # 若金額欄都空，從備註/內容解析
            note_text = row.get("備註", "") or row.get("內容", "") or ""
            if amount_twd is None and amount_jpy is None:
                note_twd, note_jpy = parse_amount_from_note(note_text)
                amount_twd = note_twd
                amount_jpy = note_jpy

            # 判斷狀態
            status = "ok"
            if payer_str == "各自負擔":
                status = "各自負擔"
            elif amount_twd is None and amount_jpy is None:
                status = "待確認"

            # 解析應付人員
            debtor_str = (row.get("應付人員") or "").strip()

            conn.execute("""
                INSERT INTO expenses (date, item, note, payer, debtors, amount_twd, amount_jpy, category, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                (row.get("日期") or "").strip(),
                (row.get("項目") or "").strip(),
                note_text.strip(),
                payer_str,
                debtor_str,
                amount_twd,
                amount_jpy,
                (row.get("類別") or "").strip(),
                status,
            ))

    conn.commit()
    conn.close()
    return True


def _import_members_from_md(conn):
    """從 人員.md 匯入成員到 DB"""
    if not os.path.exists(MEMBERS_FILE):
        return

    with open(MEMBERS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                name = parts[0]
                bank = parts[1] if len(parts) >= 2 else ""
                account = parts[2] if len(parts) >= 3 else ""
            else:
                name = line
                bank = ""
                account = ""

            try:
                conn.execute(
                    "INSERT INTO members (name, bank_name, bank_account) VALUES (?, ?, ?)",
                    (name, bank, account)
                )
            except sqlite3.IntegrityError:
                pass  # 重複名字跳過


def export_csv():
    """將 DB 資料匯出成 CSV 格式的 bytes"""
    expenses = get_expenses()
    import io

    output = io.StringIO()
    fieldnames = ["項目", "日期", "代墊人", "應付人員", "備註", "類別", "金額-台幣", "金額-日幣"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for exp in expenses:
        writer.writerow({
            "項目": exp["item"],
            "日期": exp["date"],
            "代墊人": exp["payer"],
            "應付人員": exp["debtor_str"],
            "備註": exp["note"],
            "類別": exp["category"],
            "金額-台幣": exp["amount_twd"] if exp["amount_twd"] is not None else "",
            "金額-日幣": exp["amount_jpy"] if exp["amount_jpy"] is not None else "",
        })

    return output.getvalue().encode("utf-8-sig")


# ===== Helpers =====

def _parse_num(val):
    """安全解析數字"""
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None
