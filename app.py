# -*- coding: utf-8 -*-
"""
app.py - Flask 路由層
所有資料操作委派給 db.py。
"""
import io
import webbrowser
import threading
import time
from flask import Flask, jsonify, request, send_file, send_from_directory

import db

app = Flask(__name__, static_folder="static", static_url_path="")


# ===== Static =====

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ===== Members API =====

@app.route("/api/members")
def api_members():
    return jsonify(db.get_members())


# ===== Bank Account API =====

@app.route("/api/bank-account", methods=["GET"])
def api_get_bank_accounts():
    return jsonify(db.get_bank_accounts())


@app.route("/api/bank-account", methods=["POST"])
def api_save_bank_account():
    data = request.json
    name = data.get("name")
    bank = data.get("bank", "")
    account = data.get("account", "")

    if not name:
        return jsonify({"error": "缺少姓名"}), 400

    db.save_bank_account(name, bank, account)
    return jsonify({"ok": True})


@app.route("/api/bank-account", methods=["DELETE"])
def api_delete_bank_account():
    data = request.json
    name = data.get("name")
    if not name:
        return jsonify({"error": "缺少姓名"}), 400

    db.delete_bank_account(name)
    return jsonify({"ok": True})


@app.route("/api/qrcode/<name>")
def api_qrcode(name):
    accounts = db.get_bank_accounts()
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


# ===== Expenses API =====

@app.route("/api/expenses")
def api_expenses():
    expenses = db.get_expenses()
    return jsonify(expenses)


@app.route("/api/expenses", methods=["POST"])
def api_add_expense():
    data = request.json
    db.add_expense(data)
    db.generate_expense_md()
    return jsonify({"ok": True})


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
def api_update_expense(expense_id):
    data = request.json
    db.update_expense(expense_id, data)
    db.generate_expense_md()
    return jsonify({"ok": True})


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
def api_delete_expense(expense_id):
    ok = db.delete_expense(expense_id)
    if not ok:
        return jsonify({"error": "找不到該筆資料"}), 404
    db.generate_expense_md()
    return jsonify({"ok": True})


# ===== Summary & Settlement API =====

@app.route("/api/summary")
def api_summary():
    return jsonify(db.get_summary())


@app.route("/api/settlement")
def api_settlement():
    return jsonify(db.calculate_settlement())


@app.route("/api/exchange-rate")
def api_exchange_rate():
    return jsonify({"jpy_to_twd": db.JPY_TO_TWD})


# ===== Export API =====

@app.route("/api/export-csv")
def api_export_csv():
    csv_bytes = db.export_csv()
    buf = io.BytesIO(csv_bytes)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name="北海道花費_匯出.csv"
    )


# ===== Startup =====

# DB 初始化 + CSV 匯入（gunicorn 和直接執行都會觸發）
db.init_db()
imported = db.import_csv_to_db()
if imported:
    print("✅ CSV 資料已匯入 SQLite！")
db.generate_expense_md()


if __name__ == "__main__":
    # 本機開發時自動開瀏覽器
    def open_browser():
        time.sleep(1)
        webbrowser.open("http://127.0.0.1:5000")
    threading.Thread(target=open_browser).start()

    app.run(debug=True, port=5000, use_reloader=False)
