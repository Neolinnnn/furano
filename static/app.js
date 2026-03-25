// ===== State =====
let currentUser = null;
let allExpenses = [];
let filteredExpenses = [];
let allMembers = [];
let userDetails = {};

// Sorting state
let currentSort = { column: 'id', order: 'asc' };

// ===== Init =====
document.addEventListener("DOMContentLoaded", () => {
  loadMembers();
});

function showLoader(show) {
  document.getElementById("loaderOverlay").style.display = show ? "flex" : "none";
}

async function loadMembers() {
  showLoader(true);
  try {
    const res = await fetch("/api/members");
    allMembers = await res.json();
    const select = document.getElementById("memberSelect");
    const addPayerSelect = document.getElementById("addPayer");
    const filterPayerSelect = document.getElementById("filterPayer");

    allMembers.forEach((m) => {
      const opt = document.createElement("option"); opt.value = m; opt.textContent = m;
      select.appendChild(opt);

      const optPayer = document.createElement("option"); optPayer.value = m; optPayer.textContent = m;
      addPayerSelect.appendChild(optPayer);

      const optFilter = document.createElement("option"); optFilter.value = m; optFilter.textContent = m;
      filterPayerSelect.appendChild(optFilter);
    });
  } catch (err) {
    showToast("載入人員失敗", "error");
  } finally {
    showLoader(false);
  }
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
  document.getElementById("userAvatar").textContent = name.charAt(name.length - 1);

  loadBankAccount();
  loadAllBankAccounts();
  loadDashboard();
  loadExpenses();
  loadSettlement();
}

function logout() {
  currentUser = null;
  document.getElementById("loginScreen").style.display = "flex";
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

  if (tabName === "settlement") loadSettlement();
  else if (tabName === "expenses") { loadDashboard(); loadExpenses(); }
}

// ===== Bank Account =====
async function loadBankAccount() {
  const res = await fetch("/api/bank-account");
  const accounts = await res.json();
  const info = accounts[currentUser];
  if (info) {
    document.getElementById("bankName").value = info.bank || "";
    document.getElementById("bankAccount").value = info.account || "";
    document.getElementById("btnDeleteBank").style.display = "block";
    showQrCode(currentUser, info);
  } else {
    document.getElementById("bankName").value = "";
    document.getElementById("bankAccount").value = "";
    document.getElementById("btnDeleteBank").style.display = "none";
    document.getElementById("qrSection").style.display = "none";
  }
}

async function loadAllBankAccounts() {
  const res = await fetch("/api/bank-account");
  const accounts = await res.json();
  const container = document.getElementById("allBankAccounts");

  if (Object.keys(accounts).length === 0) {
    container.innerHTML = '<p style="color:var(--text-muted);font-size:14px;">目前還沒有人設定帳號</p>';
    return;
  }

  let html = '<div class="settlement-grid">';
  for (const [name, info] of Object.entries(accounts)) {
    html += `
      <div class="balance-card positive" style="cursor:pointer" onclick="showQrModal('${name}', '${info.bank}', '${info.account}')">
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
  if (!bank || !account) { showToast("請填寫銀行名稱和帳號", "error"); return; }

  showLoader(true);
  try {
    const res = await fetch("/api/bank-account", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: currentUser, bank, account }),
    });
    if (res.ok) {
      showToast("帳號已儲存！", "success");
      document.getElementById("btnDeleteBank").style.display = "block";
      showQrCode(currentUser, { bank, account });
      loadAllBankAccounts();
    } else { showToast("儲存失敗", "error"); }
  } finally { showLoader(false); }
}

async function deleteBankAccount() {
  if (!confirm("確定要刪除您的銀行帳號嗎？")) return;
  showLoader(true);
  try {
    const res = await fetch("/api/bank-account", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: currentUser }),
    });
    if (res.ok) {
      showToast("帳號已刪除", "success");
      loadBankAccount();
      loadAllBankAccounts();
    } else { showToast("刪除失敗", "error"); }
  } finally { showLoader(false); }
}

function showQrCode(name, info) {
  const section = document.getElementById("qrSection");
  section.style.display = "flex";
  document.getElementById("qrCodeImg").src = `/api/qrcode/${encodeURIComponent(name)}?t=${Date.now()}`;
  document.getElementById("qrBankDisplay").textContent = `🏦 ${info.bank}`;
  document.getElementById("qrAccountDisplay").textContent = `📄 ${info.account}`;
}

function showQrModal(name, bank, account) {
  const modal = document.getElementById("qrModal");
  modal.style.display = "flex";
  document.getElementById("modalTitle").textContent = `${name} 的收款帳號`;
  document.getElementById("modalQrImg").src = `/api/qrcode/${encodeURIComponent(name)}?t=${Date.now()}`;
}

// ===== Dashboard & Expenses =====
async function loadDashboard() {
  const res = await fetch("/api/summary");
  const data = await res.json();
  document.getElementById("dashCount").textContent = data.count;
  document.getElementById("dashTwd").textContent = `NT$ ${formatNum(data.total_twd)}`;
  document.getElementById("dashJpy").textContent = `¥ ${formatNum(data.total_jpy)}`;
  document.getElementById("dashCalcTwd").textContent = `NT$ ${formatNum(data.calculated_twd)}`;
}

async function loadExpenses() {
  showLoader(true);
  try {
    const res = await fetch("/api/expenses");
    allExpenses = await res.json();
    applyFilterAndSort();
  } finally { showLoader(false); }
}

// Table Sort & Filter
function toggleSort(col) {
  if (currentSort.column === col) {
    currentSort.order = currentSort.order === 'asc' ? 'desc' : 'asc';
  } else {
    currentSort.column = col;
    currentSort.order = 'asc';
  }
  applyFilterAndSort();
}

function applyFilterAndSort() {
  const catFilter = document.getElementById("filterCategory").value;
  const payerFilter = document.getElementById("filterPayer").value;

  filteredExpenses = allExpenses.filter(e => {
    if (catFilter && e.category !== catFilter) return false;
    if (payerFilter && !e.payers.includes(payerFilter) && e.payer !== payerFilter) return false;
    return true;
  });

  filteredExpenses.sort((a, b) => {
    let valA = a[currentSort.column];
    let valB = b[currentSort.column];

    if (valA === null || valA === undefined) valA = '';
    if (valB === null || valB === undefined) valB = '';

    if (typeof valA === 'string') valA = valA.toLowerCase();
    if (typeof valB === 'string') valB = valB.toLowerCase();

    if (valA < valB) return currentSort.order === 'asc' ? -1 : 1;
    if (valA > valB) return currentSort.order === 'asc' ? 1 : -1;
    return 0;
  });

  renderExpenseTable();
}

function renderExpenseTable() {
  const tbody = document.getElementById("expenseBody");
  const headers = document.querySelectorAll("#expenseTable th");

  // Update sort icons
  headers.forEach(th => {
    if (!th.textContent.includes('↕') && !th.textContent.includes('↑') && !th.textContent.includes('↓')) return;
    let text = th.textContent.replace(/[↕↑↓]/g, '').trim();
    if (th.getAttribute('onclick')?.includes(currentSort.column)) {
      th.textContent = text + (currentSort.order === 'asc' ? ' ↑' : ' ↓');
    } else {
      th.textContent = text + ' ↕';
    }
  });

  let html = "";
  filteredExpenses.forEach((exp) => {
    const statusClass = exp.status === "ok" ? "badge-ok" : exp.status === "各自負擔" ? "badge-self" : "badge-pending";
    const statusText = exp.status === "ok" ? "✓ 已確認" : exp.status === "各自負擔" ? "各自負擔" : "⚠ 待確認";
    const catIcon = { 住宿: "🏨", 交通: "🚌", 餐飲: "🍜", 雪場: "⛷️", 移動: "✈️", "門票/活動": "🎫" }[exp.category] || "📌";

    html += `<tr data-id="${exp.id}">
      <td>${exp.id}</td>
      <td class="editable" data-field="日期" data-id="${exp.id}" ondblclick="startEdit(this)">${escapeHtml(exp.date || "-")}</td>
      <td class="editable" data-field="項目" data-id="${exp.id}" ondblclick="startEdit(this)">${escapeHtml(exp.item || "-")}</td>
      <td class="editable" data-field="備註" data-id="${exp.id}" ondblclick="startEdit(this)"
          style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"
          title="${escapeHtml(exp.note)}">${escapeHtml(exp.note)}</td>
      <td class="editable" data-field="代墊人" data-id="${exp.id}" ondblclick="startEdit(this)">${escapeHtml(exp.payer)}</td>
      <td class="editable" data-field="應付人員" data-id="${exp.id}" ondblclick="startEdit(this)">${exp.debtors.length ? exp.debtors.join(", ") : escapeHtml(exp.debtor_str)}</td>
      <td class="editable" data-field="金額-台幣" data-id="${exp.id}" ondblclick="startEdit(this)">${exp.amount_twd != null ? formatNum(exp.amount_twd) : "-"}</td>
      <td class="editable" data-field="金額-日幣" data-id="${exp.id}" ondblclick="startEdit(this)">${exp.amount_jpy != null ? formatNum(exp.amount_jpy) : "-"}</td>
      <td style="font-weight:600;color:var(--warning);">${exp.amount_twd_total != null ? "NT$ " + formatNum(exp.amount_twd_total) : "-"}</td>
      <td><span class="category-tag">${catIcon} ${exp.category || "-"}</span></td>
      <td><span class="badge ${statusClass}">${statusText}</span></td>
      <td>
        <div class="row-actions">
           <button class="btn-icon" onclick="showExpenseDetailModal(${exp.id})" title="檢視詳細分攤">👁️</button>
           <button class="btn-icon" onclick="deleteExpense(${exp.id})" title="刪除">🗑️</button>
        </div>
      </td>
    </tr>`;
  });

  tbody.innerHTML = html;
}

// ===== Add / Delete Expenses =====
function showAddExpenseModal() {
  document.getElementById("expenseModal").style.display = "flex";
}
function closeExpenseModal() {
  document.getElementById("expenseModal").style.display = "none";
}

async function submitAddExpense() {
  const date = document.getElementById("addDate").value;
  const item = document.getElementById("addItem").value;
  const note = document.getElementById("addNote").value;
  const payer = document.getElementById("addPayer").value;
  const debtors = document.getElementById("addDebtors").value;
  const twd = document.getElementById("addTwd").value;
  const jpy = document.getElementById("addJpy").value;
  const category = document.getElementById("addCategory").value;

  if ((!item && !note) || !payer) { showToast("項目/備註 和 代墊人為必填", "error"); return; }

  const payload = {
    "項目": item,
    "日期": date,
    "備註": note,
    "代墊人": payer,
    "應付人員": debtors,
    "金額-台幣": twd,
    "金額-日幣": jpy,
    "類別": category
  };

  showLoader(true);
  try {
    const res = await fetch("/api/expenses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      showToast("新增成功", "success");
      closeExpenseModal();
      loadDashboard();
      loadExpenses();
      if (document.getElementById("tab-settlement").classList.contains("active")) loadSettlement();
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(err.error || "新增失敗", "error");
    }
  } finally { showLoader(false); }
}

async function deleteExpense(id) {
  if (!confirm("確定要刪除這筆花費嗎？")) return;
  showLoader(true);
  try {
    const res = await fetch(`/api/expenses/${id}`, { method: "DELETE" });
    if (res.ok) {
      showToast("已刪除花費", "success");
      loadDashboard();
      loadExpenses();
      if (document.getElementById("tab-settlement").classList.contains("active")) loadSettlement();
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(err.error || "刪除失敗", "error");
    }
  } finally { showLoader(false); }
}

// ===== Expense Detail Modal (Per-Tx Split) =====
function showExpenseDetailModal(id) {
  const exp = allExpenses.find(e => e.id === id);
  if (!exp) return;
  if (!exp.amount_twd_total || exp.status === "各自負擔" || exp.status === "待確認") {
    showToast("此款項無須分攤或尚未確認", "warning");
    return;
  }

  // Populate Debtors array
  const debtors = (!exp.debtors || exp.debtors.length === 0) ? allMembers : exp.debtors;
  const payers = exp.payers || [exp.payer];
  
  const perPerson = Math.round(exp.amount_twd_total / debtors.length);
  const perPayer = Math.round(exp.amount_twd_total / payers.length);

  let html = `
    <div style="margin-bottom:15px; padding:15px; background:rgba(255,255,255,0.05); border-radius:8px;">
      <h3 style="margin:0 0 10px 0; color:var(--accent); font-size:24px;">💰 總額：NT$ ${formatNum(exp.amount_twd_total)}</h3>
      <div style="font-size:14px; color:var(--text-secondary); line-height:1.6;">
        <div><strong>📌 項目：</strong> ${escapeHtml(exp.item || "-")}</div>
        <div><strong>📝 備註：</strong> ${escapeHtml(exp.note || "-")}</div>
        <div><strong>📅 日期：</strong> ${escapeHtml(exp.date || "-")}</div>
      </div>
    </div>
    
    <div style="margin-bottom:15px;">
      <h4 style="margin:0 0 8px 0; color:var(--text-primary); border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:5px; font-size:15px;">
        🎯 應付人員 <span style="font-size:13px; font-weight:normal; color:var(--warning); float:right;">(每人分攤 NT$ ${formatNum(perPerson)})</span>
      </h4>
      <div style="display:flex; flex-wrap:wrap; gap:8px;">
  `;
  
  debtors.forEach(d => {
    html += `<span class="badge badge-pending">${d}</span>`;
  });
  
  html += `
      </div>
    </div>
    
    <div style="margin-bottom:5px;">
      <h4 style="margin:0 0 8px 0; color:var(--text-primary); border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:5px; font-size:15px;">
        💳 代墊人員 <span style="font-size:13px; font-weight:normal; color:var(--accent); float:right;">(每人代墊 NT$ ${formatNum(perPayer)})</span>
      </h4>
      <div style="display:flex; flex-wrap:wrap; gap:8px;">
  `;
  
  payers.forEach(p => {
    html += `<span class="badge badge-ok">${p}</span>`;
  });
  
  html += `
      </div>
    </div>
  `;
  
  document.getElementById("detailModalContent").innerHTML = html;
  document.getElementById("expenseDetailModal").style.display = "flex";
}

function closeExpenseDetailModal() {
  document.getElementById("expenseDetailModal").style.display = "none";
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
    if (e.key === "Enter") finishEdit(td, input, field, id);
    else if (e.key === "Escape") cancelEdit(td, currentValue);
  });
  input.addEventListener("blur", () => finishEdit(td, input, field, id));

  td.textContent = "";
  td.appendChild(input);
  input.focus(); input.select();
}

async function finishEdit(td, input, field, id) {
  const newValue = input.value.trim();
  td.classList.remove("editing");
  td.textContent = newValue || "-";

  showLoader(true);
  try {
    const res = await fetch(`/api/expenses/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: newValue }),
    });
    if (res.ok) {
      showToast("已更新並同步", "success");
      loadExpenses();
      loadDashboard();
    } else {
      const err = await res.json().catch(() => ({}));
      showToast(err.error || "更新失敗", "error");
    }
  } finally { showLoader(false); }
}

function cancelEdit(td, originalValue) {
  td.classList.remove("editing");
  td.textContent = originalValue;
}

// ===== Settlement =====
async function loadSettlement() {
  showLoader(true);
  try {
    const res = await fetch("/api/settlement");
    const data = await res.json();
    userDetails = data.user_details || {};
    populateDetailMemberSelect();
    renderBalance(data.balance);
    renderTransfers(data.transfers);
    updatePersonalSummary(data.balance);
    renderPersonalDetails();
  } finally { showLoader(false); }
}

function populateDetailMemberSelect() {
  const select = document.getElementById("detailMemberSelect");
  if (!select) return;
  select.innerHTML = "";
  Object.keys(userDetails).forEach(m => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    if (m === currentUser) opt.selected = true;
    select.appendChild(opt);
  });
}

function renderPersonalDetails() {
  const select = document.getElementById("detailMemberSelect");
  if (!select) return;
  const member = select.value;
  if (!member || !userDetails[member]) return;
  
  const list = userDetails[member];
  const tbody = document.getElementById("personalDetailBody");
  
  let html = "";
  let totalPay = 0;
  let totalOwe = 0;

  list.forEach(tx => {
    const isPay = tx.type === "pay";
    const amount = Number(tx.amount);
    const catIcon = { "住宿": "🏨", "交通": "🚌", "餐飲": "🍜", "雪場": "⛷️", "移動": "✈️", "門票/活動": "🎫" }[tx.category] || "📌";
    const sign = isPay ? "+" : "-";
    const color = isPay ? "var(--accent)" : "var(--warning)";

    if(isPay) totalPay += amount; else totalOwe += amount;

    html += `<tr>
      <td>${formatDate(tx.date)}</td>
      <td><span class="category-tag">${catIcon} ${escapeHtml(tx.category || "-")}</span></td>
      <td>
        <div style="font-weight:600">${escapeHtml(tx.item || "-")}</div>
        <div style="font-size:12px;color:var(--text-muted);font-weight:normal">${escapeHtml(tx.note || "-")}</div>
      </td>
      <td style="font-size:13px;">${escapeHtml((tx.payers || []).join("、") || "-")}</td>
      <td style="font-size:13px;">${escapeHtml((tx.debtors || []).join("、") || "-")}</td>
      <td><span class="badge ${isPay ? 'badge-ok' : 'badge-pending'}">${escapeHtml(tx.desc)}</span></td>
      <td style="color:${color}; font-weight:bold; text-align:right;">${sign} NT$ ${formatNum(amount)}</td>
    </tr>`;
  });

  if (list.length === 0) {
    html = `<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px;">無相關明細</td></tr>`;
  }

  tbody.innerHTML = html;
  
  const net = totalPay - totalOwe;
  const netColor = net > 0 ? "var(--accent)" : (net < 0 ? "var(--error)" : "var(--text-primary)");
  const netSign = net > 0 ? "+" : "";
  
  document.getElementById("personalDetailTotal").innerHTML = `
    <div style="color:var(--text-secondary); margin-bottom:5px;">
      代墊總計: <span style="color:var(--accent)">+NT$ ${formatNum(totalPay)}</span> &nbsp;&nbsp;|&nbsp;&nbsp; 
      應付總計: <span style="color:var(--warning)">-NT$ ${formatNum(totalOwe)}</span>
    </div>
    <div style="font-size:1.4em; color:${netColor}; margin-top:10px; border-top:1px solid rgba(255,255,255,0.1); padding-top:10px;">
      最終結算淨額: ${netSign}NT$ ${formatNum(net)}
    </div>
  `;
}

function updatePersonalSummary(balance) {
  const psDiv = document.getElementById("personalSummary");
  const myBal = balance[currentUser] || 0;
  if (myBal === 0) {
    psDiv.innerHTML = `
      <div><h2>👋 嗨，${currentUser}</h2><p style="color:var(--text-secondary)">所有的帳務都已經結清拉！無須支付或收取款項。</p></div>
      <div class="ps-amount ps-zero">NT$ 0</div>`;
  } else if (myBal > 0) {
    psDiv.innerHTML = `
      <div><h2>👋 嗨，${currentUser}</h2><p style="color:var(--text-secondary)">太棒了！你目前可收回的總金額為</p></div>
      <div class="ps-amount ps-positive">+ NT$ ${formatNum(myBal)}</div>`;
  } else {
    psDiv.innerHTML = `
      <div><h2>👋 嗨，${currentUser}</h2><p style="color:var(--text-secondary)">哎呀！你目前還需要支付款項給其他人</p></div>
      <div class="ps-amount ps-negative">- NT$ ${formatNum(Math.abs(myBal))}</div>`;
  }
  psDiv.style.display = "flex";
}

function renderBalance(balance) {
  const grid = document.getElementById("balanceGrid");
  let html = "";
  const sorted = Object.entries(balance).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  sorted.forEach(([name, amount]) => {
    const cls = amount > 0 ? "positive" : amount < 0 ? "negative" : "zero";
    const label = amount > 0 ? "可收回" : amount < 0 ? "需支付" : "已結清";
    const sign = amount > 0 ? "+" : amount < 0 ? "-" : "";
    html += `
      <div class="balance-card ${cls}" style="cursor:pointer;" onclick="selectMemberForDetail('${name}')" title="點擊查看 ${name} 的詳細帳單">
        <div class="balance-avatar">${name.charAt(name.length - 1)}</div>
        <div class="balance-info">
          <div class="balance-name">${name}</div>
          <div class="balance-amount">${sign}NT$ ${formatNum(Math.abs(amount))}</div>
          <div class="balance-label">${label}</div>
        </div>
      </div>`;
  });
  grid.innerHTML = html;
}

function selectMemberForDetail(name) {
  const select = document.getElementById("detailMemberSelect");
  if (select) {
    select.value = name;
    renderPersonalDetails();
    select.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function renderTransfers(transfers) {
  const list = document.getElementById("transferList");
  if (!transfers.length) {
    list.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px;">沒有需要轉帳的項目</p>';
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
        <button class="transfer-qr-btn" onclick="showQrModal('${t.to}', '', '')">📱 QR Code</button>
      </div>`;
  });
  list.innerHTML = html;
}

// ===== Utilities =====
function formatNum(n) { return n == null ? "-" : Math.round(n).toLocaleString(); }
function formatDate(d) {
  if (!d || d === "-") return "-";
  // 嘗試解析各種日期格式，輸出 mm/dd
  const s = String(d).trim();
  // 已經是 m/dd 或 mm/dd 格式
  const slashMatch = s.match(/^(\d{1,2})\/(\d{1,2})/);
  if (slashMatch) return `${slashMatch[1].padStart(2, '0')}/${slashMatch[2].padStart(2, '0')}`;
  // X月X日
  const cnMatch = s.match(/(\d{1,2})月(\d{1,2})日?/);
  if (cnMatch) return `${cnMatch[1].padStart(2, '0')}/${cnMatch[2].padStart(2, '0')}`;
  // ISO or Date string
  const parsed = new Date(s);
  if (!isNaN(parsed.getTime())) {
    return `${String(parsed.getMonth()+1).padStart(2,'0')}/${String(parsed.getDate()).padStart(2,'0')}`;
  }
  return d;
}
function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div"); div.textContent = str; return div.innerHTML;
}
function showToast(msg, type = "success") {
  const t = document.createElement("div"); t.className = `toast toast-${type}`; t.textContent = msg;
  document.body.appendChild(t); setTimeout(() => t.remove(), 3000);
}

function exportCSV() {
  window.location.href = "/api/export-csv";
}
