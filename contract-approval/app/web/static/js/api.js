// 统一 API 调用与展示辅助
async function apiCall(url, method = "GET", body = null) {
  const resp = await fetch(url, {
    method,
    headers: body !== null ? { "Content-Type": "application/json" } : {},
    body: body !== null ? JSON.stringify(body) : undefined,
  });
  return await resp.json();
}

const TASK_STATUS_ZH = { pending: "待处理", parsing: "解析中", reviewing: "审查中", blocked: "已阻塞", done: "已完成" };
const WRITE_STATUS_ZH = { not_written: "未回写", writing: "回写中", success: "回写成功", failed: "回写失败" };
const RISK_ZH = { high: "高", medium: "中", low: "低" };

function taskBadge(status) {
  return `<span class="badge badge-${status}">${TASK_STATUS_ZH[status] || status}</span>`;
}
function writeBadge(status) {
  return `<span class="badge badge-write-${status}">${WRITE_STATUS_ZH[status] || status}</span>`;
}
function riskBadge(level) {
  if (!level) return "";
  const zh = RISK_ZH[level] || level;
  return `<span class="badge badge-risk-${level}">${zh}</span>`;
}
function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function showMsg(el, type, text) {
  el.innerHTML = `<div class="msg msg-${type}">${esc(text)}</div>`;
}
