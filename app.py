# -*- coding: utf-8 -*-
import csv
import io
import os
import re
import json
from flask import Flask, jsonify, request, send_file, send_from_directory

app = Flask(__name__, static_folder="static", static_url_path="")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMBERS_FILE = os.path.join(BASE_DIR, "人員.md")
CSV_FILE = os.path.join(BASE_DIR, "北海道花費(資料庫).csv")
BANK_FILE = os.path.join(BASE_DIR, "bank_accounts.json")
MD_FILE = os.path.join(BASE_DIR, "北海道花費.md")

JPY_TO_TWD = 0.2038  # 台銀 2026/03 中旬即期賣出

# 暱稱 → 全名 對應表
NICKNAME_MAP = {
    "翰": "林廷翰",
    "林廷翰": "林廷翰",
    "君翰": "林君翰",
    "君": "林君翰",
    "林君翰": "林君翰",
    "定": "定定",
    "定定": "定定",
    "祥": "李鴻祥",
    "祥哥": "李鴻祥",
    "李鴻祥": "李鴻祥",
    "智": "張銘智",
    "阿智": "張銘智",
    "張銘智": "張銘智",
    "儒": "黃珮儒",
    "黃珮儒": "黃珮儒",
    "巧衣": "王巧衣",
    "王巧衣": "王巧衣",
    "大為": "林大為",
    "林大為": "林大為",
    "雨玄": "王雨玄",
    "王雨玄": "王雨玄",
}


def read_members():
    """從人員.md讀取成員清單，含銀行帳號"""
    members = []
    bank_info = {}
    with open(MEMBERS_FILE, "r", encoding="utf-8") as f:
        current_member = None
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            # 檢查是否有銀行資訊格式: 姓名 | 銀行 | 帳號
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3:
                    name = parts[0]
                    members.append(name)
                    bank_info[name] = {"bank": parts[1], "account": parts[2]}
                elif len(parts) == 1:
                    members.append(parts[0])
            else:
                members.append(line)
    return members, bank_info


def load_bank_accounts():
    """從 bank_accounts.json 讀取銀行帳號"""
    if os.path.exists(BANK_FILE):
        with open(BANK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_bank_accounts(accounts):
    """儲存銀行帳號到 bank_accounts.json"""
    with open(BANK_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


def update_members_md(name, bank, account):
    """更新人員.md加入銀行帳號"""
    lines = []
    with open(MEMBERS_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    updated = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        # 若該行是這個人的名字（可能已有銀行資訊）
        if stripped.startswith(name):
            new_lines.append(f"{name} | {bank} | {account}\n")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"{name} | {bank} | {account}\n")

    with open(MEMBERS_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def resolve_name(nickname):
    """暱稱轉全名"""
    nickname = nickname.strip()
    return NICKNAME_MAP.get(nickname, nickname)


def parse_amount_from_note(note):
    """從備註欄解析金額，回傳 (amount_twd, amount_jpy)"""
    if not note:
        return None, None

    # 嘗試匹配日圓金額
    jpy_patterns = [
        r"(\d[\d,]*)\s*(?:日圓|日幣|円|yen|YEN|圓)",
        r"(\d[\d,]*)\s*(?:日)",
    ]
    for pattern in jpy_patterns:
        m = re.search(pattern, note)
        if m:
            amount = int(m.group(1).replace(",", ""))
            return None, amount

    # 嘗試匹配台幣金額
    twd_patterns = [
        r"(\d[\d,]*)\s*(?:台幣|TWD|元|塊)",
        r"(?:台幣|TWD)\s*(\d[\d,]*)",
    ]
    for pattern in twd_patterns:
        m = re.search(pattern, note)
        if m:
            amount = int(m.group(1).replace(",", ""))
            return amount, None

    # 嘗試匹配純數字（如 39750）
    m = re.search(r"(?:總額|共|合計)?\s*(\d{4,})", note)
    if m:
        amount = int(m.group(1).replace(",", ""))
        # 超過 5000 的大數字推測是日幣
        if amount > 5000:
            return None, amount
        return amount, None

    return None, None


def parse_payers(payer_str):
    """解析代墊人（可能有多人，如 '祥哥&阿智'）"""
    if not payer_str or payer_str.strip() == "各自負擔":
        return []
    # 用 & 或 、分隔
    parts = re.split(r"[&＆、]", payer_str)
    return [resolve_name(p.strip()) for p in parts if p.strip()]


def parse_debtors(debtor_str, all_members):
    """解析應付人員"""
    if not debtor_str or not debtor_str.strip():
        return list(all_members)  # 空的表示全員分攤
    parts = re.split(r"[\s,，、]+", debtor_str.strip())
    return [resolve_name(p) for p in parts if p.strip()]


def read_expenses():
    """讀取並解析 CSV"""
    expenses = []
    all_members, _ = read_members()

    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            payer_str = row.get("代墊人", "").strip()

            # 跳過「各自負擔」
            if payer_str == "各自負擔":
                expenses.append({
                    "id": i,
                    "item": row.get("項目", ""),
                    "payer": "各自負擔",
                    "payers": [],
                    "note": row.get("備註", ""),
                    "debtors": [],
                    "debtor_str": row.get("應付人員", ""),
                    "amount_twd": None,
                    "amount_jpy": None,
                    "amount_twd_total": None,
                    "category": row.get("類別", ""),
                    "status": "各自負擔",
                    "raw": dict(row),
                })
                continue

            payers = parse_payers(payer_str)
            debtors = parse_debtors(row.get("應付人員", ""), all_members)

            # 解析金額
            amount_twd = None
            amount_jpy = None
            twd_str = row.get("金額-台幣", "").strip()
            jpy_str = row.get("金額-日幣", "").strip()

            if twd_str:
                try:
                    amount_twd = float(twd_str.replace(",", ""))
                except ValueError:
                    pass
            if jpy_str:
                try:
                    amount_jpy = float(jpy_str.replace(",", ""))
                except ValueError:
                    pass

            # 若兩個金額欄都空，從備註解析
            if amount_twd is None and amount_jpy is None:
                note_twd, note_jpy = parse_amount_from_note(row.get("備註", ""))
                amount_twd = note_twd
                amount_jpy = note_jpy

            # 算出台幣總額
            amount_twd_total = None
            status = "ok"
            if amount_twd is not None and amount_jpy is not None:
                amount_twd_total = amount_twd + amount_jpy * JPY_TO_TWD
            elif amount_twd is not None:
                amount_twd_total = amount_twd
            elif amount_jpy is not None:
                amount_twd_total = amount_jpy * JPY_TO_TWD
            else:
                status = "待確認"

            expenses.append({
                "id": i,
                "item": row.get("項目", ""),
                "payer": payer_str,
                "payers": payers,
                "note": row.get("備註", ""),
                "debtors": debtors,
                "debtor_str": row.get("應付人員", ""),
                "amount_twd": amount_twd,
                "amount_jpy": amount_jpy,
                "amount_twd_total": amount_twd_total,
                "category": row.get("類別", ""),
                "status": status,
                "raw": dict(row),
            })

    return expenses


def generate_expense_md():
    """根據當前 CSV 資料重新生成乾淨的 北海道花費.md"""
    expenses = read_expenses()

    # 依類別分組
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
        lines.append("| # | 備註 | 代墊人 | 應付人員 | 台幣 | 日幣 | 類別 | 狀態 |")
        lines.append("|---|------|--------|----------|------|------|------|------|")
        for exp in items:
            note = exp["note"]
            # 清除 Notion URLs
            note = re.sub(r'\s*\(https://www\.notion\.so/[^)]*\)', '', note)
            note = re.sub(r'\s*https://www\.notion\.so/\S+', '', note)
            note = note.strip().replace('|', '｜').replace('\n', ' ')

            payer_str = exp["payer"]
            payers = exp.get("payers", [])
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
            elif not debtors or len(debtors) >= 7:
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

            lines.append(
                f"| {idx} | {note} | {payer_display} | {debtor_display} | {twd} | {jpy} | {exp.get('category', '-')} | {status} |"
            )
            idx += 1
        lines.append("")

    # 剩餘未分類
    for cat, items in grouped.items():
        lines.append(f"## {cat}\n")
        lines.append("")
        lines.append("| # | 備註 | 代墊人 | 應付人員 | 台幣 | 日幣 | 類別 | 狀態 |")
        lines.append("|---|------|--------|----------|------|------|------|------|")
        for exp in items:
            note = re.sub(r'\s*\(https://www\.notion\.so/[^)]*\)', '', exp["note"])
            note = note.strip().replace('|', '｜').replace('\n', ' ')
            payers = exp.get("payers", [])
            payer_display = "、".join(payers) if payers else exp["payer"]
            debtors = exp.get("debtors", [])
            debtor_display = "全員" if not debtors or len(debtors) >= 7 else "、".join(debtors)
            twd = f"{int(exp['amount_twd']):,}" if exp.get("amount_twd") is not None else "-"
            jpy = f"{int(exp['amount_jpy']):,}" if exp.get("amount_jpy") is not None else "-"
            status = "✓" if exp["status"] == "ok" else "⚠ 待確認"
            lines.append(
                f"| {idx} | {note} | {payer_display} | {debtor_display} | {twd} | {jpy} | {cat} | {status} |"
            )
            idx += 1
        lines.append("")

    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def calculate_settlement(expenses, all_members):
    """計算拆帳結果"""
    # 每人淨額：正數 = 可以拿回錢，負數 = 要付錢
    balance = {m: 0.0 for m in all_members}

    details = []  # 每筆的分攤明細

    for exp in expenses:
        if exp["status"] == "各自負擔" or exp["status"] == "待確認":
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

        # 代墊人先加上全額（他們付了錢）
        for p in payers:
            if p in balance:
                balance[p] += per_payer_paid

        # 應付人員扣除分攤金額
        for d in debtors:
            if d in balance:
                balance[d] -= per_person

        details.append({
            "note": exp["note"],
            "payers": payers,
            "debtors": debtors,
            "total": round(total, 0),
            "per_person": round(per_person, 0),
        })

    # 最小交易數演算法
    transfers = minimize_transfers(balance)

    return {
        "balance": {k: round(v, 0) for k, v in balance.items()},
        "transfers": transfers,
        "details": details,
    }


def minimize_transfers(balance):
    """最小化轉帳次數的貪心演算法"""
    # 分成債權人和債務人
    creditors = []  # (name, amount) 正數
    debtors = []    # (name, amount) 負數（取絕對值）

    for name, amount in balance.items():
        if amount > 1:  # 忽略極小金額
            creditors.append([name, amount])
        elif amount < -1:
            debtors.append([name, -amount])

    # 排序：大的先處理
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


# ===== API Routes =====

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/members")
def api_members():
    members, _ = read_members()
    return jsonify(members)


@app.route("/api/bank-account", methods=["GET"])
def api_get_bank_accounts():
    accounts = load_bank_accounts()
    return jsonify(accounts)


@app.route("/api/bank-account", methods=["POST"])
def api_save_bank_account():
    data = request.json
    name = data.get("name")
    bank = data.get("bank", "")
    account = data.get("account", "")

    if not name:
        return jsonify({"error": "缺少姓名"}), 400

    accounts = load_bank_accounts()
    accounts[name] = {"bank": bank, "account": account}
    save_bank_accounts(accounts)

    # 同步更新 人員.md
    update_members_md(name, bank, account)

    return jsonify({"ok": True})


@app.route("/api/qrcode/<name>")
def api_qrcode(name):
    accounts = load_bank_accounts()
    info = accounts.get(name)
    if not info:
        return jsonify({"error": "找不到帳號"}), 404

    import qrcode
    qr_text = f"銀行: {info['bank']}\n帳號: {info['account']}"
    img = qrcode.make(qr_text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/expenses")
def api_expenses():
    expenses = read_expenses()
    # 移除 raw 欄位中的大量資料以減少回傳
    result = []
    for exp in expenses:
        e = {k: v for k, v in exp.items() if k != "raw"}
        result.append(e)
    return jsonify(result)


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
def api_update_expense(expense_id):
    """更新單筆花費並回寫 CSV"""
    data = request.json

    # 讀取現有 CSV
    rows = []
    fieldnames = []
    with open(CSV_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(dict(row))

    if expense_id < 0 or expense_id >= len(rows):
        return jsonify({"error": "找不到該筆資料"}), 404

    # 更新欄位
    for key, value in data.items():
        if key in fieldnames:
            rows[expense_id][key] = value

    # 回寫 CSV
    with open(CSV_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    # 同步更新 MD 檔案
    generate_expense_md()

    return jsonify({"ok": True})


@app.route("/api/settlement")
def api_settlement():
    members, _ = read_members()
    expenses = read_expenses()
    result = calculate_settlement(expenses, members)
    return jsonify(result)


@app.route("/api/exchange-rate")
def api_exchange_rate():
    return jsonify({"jpy_to_twd": JPY_TO_TWD})


if __name__ == "__main__":
    # 啟動時先同步一次 MD 檔案
    generate_expense_md()
    app.run(debug=True, port=5000)
