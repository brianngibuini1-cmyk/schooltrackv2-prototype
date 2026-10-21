/** Formatting and small pure helpers shared by every view. */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const decimal = new Intl.NumberFormat("en-KE", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const whole = new Intl.NumberFormat("en-KE", { maximumFractionDigits: 0 });

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** 123456 -> "1,234.56" */
export function amount(cents) {
  return decimal.format((Number(cents) || 0) / 100);
}

/** 123456 -> "KSh 1,234.56" */
export function money(cents) {
  return `KSh ${amount(cents)}`;
}

/** 123456789 -> "1.2M" for compact chart axes. */
export function compactMoney(cents) {
  const value = (Number(cents) || 0) / 100;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(value >= 10_000_000 ? 0 : 1)}M`;
  if (Math.abs(value) >= 1_000) return `${Math.round(value / 1_000)}K`;
  return whole.format(value);
}

export function count(value) {
  return whole.format(Number(value) || 0);
}

export function formatDate(iso) {
  if (!iso) return "—";
  const [year, month, day] = String(iso).split("-").map(Number);
  if (!year || !month || !day) return escapeHtml(iso);
  return `${day} ${MONTHS[month - 1]} ${year}`;
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return escapeHtml(iso);
  const date = `${parsed.getDate()} ${MONTHS[parsed.getMonth()]} ${parsed.getFullYear()}`;
  const hours = String(parsed.getHours()).padStart(2, "0");
  const minutes = String(parsed.getMinutes()).padStart(2, "0");
  return `${date}, ${hours}:${minutes}`;
}

export function initials(name) {
  return String(name || "?")
    .replace(/[^A-Za-z0-9 ]/g, " ")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

export function plural(value, singular, pluralForm = `${singular}s`) {
  return Number(value) === 1 ? singular : pluralForm;
}

export function statusClass(status) {
  return ["pending", "approved", "rejected"].includes(status) ? `status-${status}` : "status-pending";
}

export function sectionClass(category) {
  return category === "jss" ? "section-jss" : "section-primary";
}

export function debounce(fn, wait = 300) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), wait);
  };
}

export function todayISO() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/** Keep empty values out of query strings. */
export function buildQuery(params) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value === undefined || value === null || value === "" || value === "all") continue;
    query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export function percent(part, total) {
  if (!total) return 0;
  return Math.round((Number(part) / Number(total)) * 100);
}

export function sum(values) {
  return values.reduce((total, value) => total + Number(value || 0), 0);
}
