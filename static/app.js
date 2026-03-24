// ===== State =====
let currentUser = null;
let allExpenses = [];
let allMembers = [];

// ===== Init =====
document.addEventListener("DOMContentLoaded", () => {
  loadMembers();
});

async function loadMembers() {
  const res = await fetch("/api/members");
  allMembers = await res.json();
  const select = document.getElementById("memberSelect");
  allMembers.forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    select.appendChild(opt);
  });
}

// ===== Login / Logout =====
function login() {
  const select = document.getElementById("memberSelect");
  const name = select.value;
  if (!name) {
    showToast("請選擇成員", "error");
    return;
  }
  currentUser = name;

  document.getElementById("loginScreen").style.display = "none";
  document.getElementById("appContainer").style.display = "block";
  document.getElementById("userName").textContent = name;
  document.getElementById("userAvatar").textContent = name.charAt(
    name.length - 1
  );

  loadBankAccount();
  loadAllBankAccounts();
  loadExpenses();
  loadSettlement();
}

function logout() {
  currentUser = null;
  document.getElementById("loginScreen").style.display = "";
  document.getElementById("appContainer").style.display = "none";
  switchTab("account");
}

// ===== Tab Switching =====
function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-content").forEach((tc) => {
    tc.classList.toggle("active", tc.id === `tab-${tabName}`);
  });

  // Reload data when switching to settlement
  if (tabName === "settlement") {
    loadSettlement();
  } else if (tabName === "expenses") {
    loadExpenses();
  }
}

// ===== Bank Account =====
async function loadBankAccount() {
  const res = await fetch("/api/bank-account");
  const accounts = await res.json();
  const info = accounts[currentUser];
  if (info) {
    document.getElementById("bankName").value = info.bank || "";
    document.getElementById("bankAccount").value = info.account || "";
    showQrCode(currentUser, info);
  }
}

async function loadAllBankAccounts() {
  const res = await fetch("/api/bank-account");
  const accounts = await res.json();
  const container = document.getElementById("allBankAccounts");

  if (Object.keys(accounts).length === 0) {
    container.innerHTML =
      '<p style="color:var(--text-muted);font-size:14px;">目前還沒有人設定帳號</p>';
    return;
  }

  let html = '<div class="settlement-grid">';
  for (const [name, info] of Object.entries(accounts)) {
    html += `
      <div class="balance-card positive" style="cursor:pointer" onclick="showQrModal('${name}')">
        <div class="balance-avatar">${name.charAt(name.length - 1)}</div>
        <div class="balance-info">
          <div class="balance-name">${name}</div>
          <div style="font-size:13px;color:var(--text-secondary);">
            ${info.bank} ${info.account ? "••••" + info.account.slice(-4) : ""}
          </div>
        </div>
      </div>
    `;
  }
  html += "</div>";
  container.innerHTML = html;
}

async function saveBankAccount() {
  const bank = document.getElementById("bankName").value.trim();
  const account = document.getElementById("bankAccount").value.trim();

  if (!bank || !account) {
    showToast("請填寫銀行名稱和帳號", "error");
    return;
  }

  const res = await fetch("/api/bank-account", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: currentUser, bank, account }),
  });

  if (res.ok) {
    showToast("帳號已儲存！", "success");
    showQrCode(currentUser, { bank, account });
    loadAllBankAccounts();
  } else {
    showToast("儲存失敗", "error");
  }
}

function showQrCode(name, info) {
  const section = document.getElementById("qrSection");
  section.style.display = "flex";
  document.getElementById("qrCodeImg").src = `/api/qrcode/${encodeURIComponent(name)}?t=${Date.now()}`;
  document.getElementById("qrBankDisplay").textContent = `🏦 ${info.bank}`;
  document.getElementById("qrAccountDisplay").textContent = `📄 ${info.account}`;
}

// ===== QR Modal =====
function showQrModal(name) {
  const modal = document.getElementById("qrModal");
  modal.style.display = "flex";
  document.getElementById("modalTitle").textContent = `${name} 的收款帳號`;
  document.getElementById("modalQrImg").src = `/api/qrcode/${encodeURIComponent(name)}?t=${Date.now()}`;
  document.getElementById("modalInfo").textContent = "掃描 QR Code 查看帳號資訊";
}

function closeModal(event) {
  if (event.target === event.currentTarget) {
    document.getElementById("qrModal").style.display = "none";
  }
}

// ===== Expenses =====
async function loadExpenses() {
  const res = await fetch("/api/expenses");
  allExpenses = await res.json();
  renderExpenseTable();
}

function renderExpenseTable() {
  const tbody = document.getElementById("expenseBody");
  let html = "";

  allExpenses.forEach((exp, idx) => {
    const statusClass =
      exp.status === "ok"
        ? "badge-ok"
        : exp.status === "各自負擔"
          ? "badge-self"
          : "badge-pending";
    const statusText =
      exp.status === "ok"
        ? "✓ 已確認"
        : exp.status === "各自負擔"
          ? "各自負擔"
          : "⚠ 待確認";

    const categoryIcons = {
      住宿: "🏨",
      交通: "🚌",
      餐飲: "🍜",
      雪場: "⛷️",
      移動: "✈️",
      "門票/活動": "🎫",
    };
    const catIcon = categoryIcons[exp.category] || "📌";

    html += `<tr data-id="${exp.id}">
      <td>${idx + 1}</td>
      <td class="editable" data-field="備註" data-id="${exp.id}" ondblclick="startEdit(this)"
          style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
          title="${escapeHtml(exp.note)}">${escapeHtml(exp.note)}</td>
      <td class="editable" data-field="代墊人" data-id="${exp.id}" ondblclick="startEdit(this)">${escapeHtml(exp.payer)}</td>
      <td class="editable" data-field="應付人員" data-id="${exp.id}" ondblclick="startEdit(this)">${exp.debtors.length ? exp.debtors.join(", ") : escapeHtml(exp.debtor_str)}</td>
      <td class="editable" data-field="金額-台幣" data-id="${exp.id}" ondblclick="startEdit(this)">${exp.amount_twd != null ? formatNum(exp.amount_twd) : "-"}</td>
      <td class="editable" data-field="金額-日幣" data-id="${exp.id}" ondblclick="startEdit(this)">${exp.amount_jpy != null ? formatNum(exp.amount_jpy) : "-"}</td>
      <td style="font-weight:600;color:var(--warning);">${exp.amount_twd_total != null ? "NT$ " + formatNum(exp.amount_twd_total) : "-"}</td>
      <td><span class="category-tag">${catIcon} ${exp.category || "-"}</span></td>
      <td><span class="badge ${statusClass}">${statusText}</span></td>
    </tr>`;
  });

  tbody.innerHTML = html;
}

// ===== Inline Editing =====
function startEdit(td) {
  if (td.classList.contains("editing")) return;

  const field = td.dataset.field;
  const id = td.dataset.id;
  const currentValue = td.textContent.trim();

  td.classList.add("editing");
  const input = document.createElement("input");
  input.type = "text";
  input.value = currentValue === "-" ? "" : currentValue;
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      finishEdit(td, input, field, id);
    } else if (e.key === "Escape") {
      cancelEdit(td, currentValue);
    }
  });
  input.addEventListener("blur", () => {
    finishEdit(td, input, field, id);
  });

  td.textContent = "";
  td.appendChild(input);
  input.focus();
  input.select();
}

async function finishEdit(td, input, field, id) {
  const newValue = input.value.trim();
  td.classList.remove("editing");
  td.textContent = newValue || "-";

  // Save to backend
  const res = await fetch(`/api/expenses/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ [field]: newValue }),
  });

  if (res.ok) {
    showToast("已更新並儲存到 CSV", "success");
    // Refresh data
    loadExpenses();
    loadSettlement();
  } else {
    showToast("更新失敗", "error");
  }
}

function cancelEdit(td, originalValue) {
  td.classList.remove("editing");
  td.textContent = originalValue;
}

// ===== Settlement =====
async function loadSettlement() {
  const res = await fetch("/api/settlement");
  const data = await res.json();
  renderBalance(data.balance);
  renderTransfers(data.transfers);
}

function renderBalance(balance) {
  const grid = document.getElementById("balanceGrid");
  let html = "";

  // Sort: biggest absolute value first
  const sorted = Object.entries(balance).sort(
    (a, b) => Math.abs(b[1]) - Math.abs(a[1])
  );

  sorted.forEach(([name, amount]) => {
    const cls = amount > 0 ? "positive" : amount < 0 ? "negative" : "zero";
    const label =
      amount > 0 ? "可拿回" : amount < 0 ? "需付出" : "不需轉帳";
    const sign = amount > 0 ? "+" : "";
    const avatar = name.charAt(name.length - 1);

    html += `
      <div class="balance-card ${cls}">
        <div class="balance-avatar">${avatar}</div>
        <div class="balance-info">
          <div class="balance-name">${name}</div>
          <div class="balance-amount">${sign}NT$ ${formatNum(Math.abs(amount))}</div>
          <div class="balance-label">${label}</div>
        </div>
      </div>
    `;
  });

  grid.innerHTML = html;
}

function renderTransfers(transfers) {
  const list = document.getElementById("transferList");

  if (!transfers.length) {
    list.innerHTML =
      '<p style="color:var(--text-muted);text-align:center;padding:20px;">沒有需要轉帳的項目</p>';
    return;
  }

  let html = "";
  transfers.forEach((t) => {
    html += `
      <div class="transfer-item">
        <span class="transfer-from">${t.from}</span>
        <span class="transfer-arrow">→</span>
        <span class="transfer-to">${t.to}</span>
        <span class="transfer-amount">NT$ ${formatNum(t.amount)}</span>
        <button class="transfer-qr-btn" onclick="showQrModal('${t.to}')">
          📱 QR Code
        </button>
      </div>
    `;
  });

  list.innerHTML = html;
}

// ===== Utilities =====
function formatNum(n) {
  if (n == null) return "-";
  return Math.round(n).toLocaleString();
}

function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function showToast(msg, type = "success") {
  const existing = document.querySelector(".toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}
