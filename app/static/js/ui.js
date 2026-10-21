/** Shared interface pieces: icons, badges, dialogs, toasts and charts. */

import { escapeHtml } from "./format.js";

const ICONS = {
  wallet: '<path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H18a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6.5A2.5 2.5 0 0 1 4 17.5v-10Z"/><path d="M4 8h14.5A1.5 1.5 0 0 1 20 9.5v4h-4.5a2 2 0 0 1 0-4H20"/>',
  receipt: '<path d="M6 3.5h12v17l-3-2-3 2-3-2-3 2v-17Z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 1.8"/>',
  users: '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0"/><path d="M16 5.2a3 3 0 0 1 0 5.6M17.5 20a5.4 5.4 0 0 0-2-4.2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  download: '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5"/><path d="M4 17v2.5h16V17"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  alert: '<path d="M12 8v5M12 16.5v.2"/><path d="M10.3 4.2 3.2 17a2 2 0 0 0 1.7 3h14.2a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 10.5v6M12 7.4v.2"/>',
  arrowLeft: '<path d="m14.5 5-7 7 7 7"/>',
  arrowRight: '<path d="m9.5 5 7 7-7 7"/>',
  chevronLeft: '<path d="m14 6-6 6 6 6"/>',
  chevronRight: '<path d="m10 6 6 6-6 6"/>',
  print: '<path d="M7 9V4h10v5"/><rect x="4" y="9" width="16" height="8" rx="2"/><path d="M7 14h10v6H7z"/>',
  building: '<path d="M4 20h16M6 20V6l6-2v16M18 20V10l-6-2"/><path d="M9 8.5v.2M9 12v.2M9 15.5v.2M15 12v.2M15 15.5v.2"/>',
  calendar: '<rect x="4" y="5.5" width="16" height="15" rx="2"/><path d="M8 3.5v4M16 3.5v4M4 10h16"/>',
  phone: '<path d="M7 3.8 9.5 8 7.4 9.9a14 14 0 0 0 6.7 6.7l1.9-2.1 4.2 2.5-.9 2.6a2 2 0 0 1-2.1 1.3A17.5 17.5 0 0 1 3.4 6.2 2 2 0 0 1 4.7 4l2.3-.2Z"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.7"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 6.3"/><path d="M20 5v6h-6"/>',
  filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
  book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H19v16H6.5A2.5 2.5 0 0 0 4 21.5v-16Z"/><path d="M4 19a2 2 0 0 1 2.5-2H19"/>',
  chart: '<path d="M4 20V4M4 20h16M8 16v-4M12.5 16V7M17 16v-7"/>',
};

export function icon(name, className = "") {
  const body = ICONS[name] || ICONS.info;
  return `<svg viewBox="0 0 24 24" class="${escapeHtml(className)}" aria-hidden="true">${body}</svg>`;
}

export function statusBadge(status, label) {
  const safe = ["pending", "approved", "rejected"].includes(status) ? status : "pending";
  const text = label || safe.charAt(0).toUpperCase() + safe.slice(1);
  return `<span class="badge status-${safe}">${escapeHtml(text)}</span>`;
}

export function sectionBadge(category, label) {
  const safe = category === "jss" ? "jss" : "primary";
  return `<span class="badge section-${safe}">${escapeHtml(label || (safe === "jss" ? "JSS" : "Primary"))}</span>`;
}

export function demoBadge(isDemo) {
  return isDemo ? '<span class="badge-demo" title="Fictional demonstration record">Demo</span>' : "";
}

export function emptyState({ title, message, iconName = "receipt", href = "", action = "" }) {
  return `
    <div class="empty-state">
      <span class="empty-icon">${icon(iconName)}</span>
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(message)}</p>
      ${href && action ? `<a class="btn btn-primary" href="${escapeHtml(href)}">${escapeHtml(action)}</a>` : ""}
    </div>`;
}

export function readOnlyPanel(message = "Writing is disabled in this public demonstration.") {
  return `
    <div class="card">
      <div class="empty-state">
        <span class="empty-icon">${icon("book")}</span>
        <h3>Read-only demonstration</h3>
        <p>${escapeHtml(message)}</p>
        <p class="small muted">You can still explore the dashboard, purchase register, suppliers and reports.</p>
        <a class="btn btn-primary" href="#/purchases">Back to the purchase register</a>
      </div>
    </div>`;
}

export function errorPanel(error, { retry = true } = {}) {
  const message = error && error.message ? error.message : "Something went wrong.";
  return `
    <div class="error-panel" role="alert">
      <span class="empty-icon">${icon("alert")}</span>
      <h2>We could not load this page</h2>
      <p>${escapeHtml(message)}</p>
      ${retry ? '<button class="btn btn-primary" type="button" data-retry>Try again</button>' : ""}
    </div>`;
}

/* -------------------------------------------------------------------------- */
/* Toasts                                                                      */
/* -------------------------------------------------------------------------- */

const toastHost = () => document.getElementById("toasts");

export function toast(message, { title = "Saved", type = "success", timeout = 4600 } = {}) {
  const host = toastHost();
  if (!host) return;
  const element = document.createElement("div");
  element.className = `toast${type === "error" ? " toast-error" : type === "info" ? " toast-info" : ""}`;
  element.setAttribute("role", type === "error" ? "alert" : "status");
  element.innerHTML = `
    <div>
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(message)}</span>
    </div>
    <button class="toast-close" type="button" aria-label="Dismiss notification">&times;</button>`;
  const remove = () => {
    element.remove();
  };
  element.querySelector(".toast-close").addEventListener("click", remove);
  host.appendChild(element);
  window.setTimeout(remove, timeout);
}

/* -------------------------------------------------------------------------- */
/* Modal dialogs                                                               */
/* -------------------------------------------------------------------------- */

let activeModal = null;

export function openModal({ title, subtitle = "", body = "", footer = "", size = "", onClose = null }) {
  closeModal();
  const previousFocus = document.activeElement;
  const root = document.getElementById("modal-root") || document.body;
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `
    <div class="modal ${size}" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-head">
        <div>
          <h2 id="modal-title">${escapeHtml(title)}</h2>
          ${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ""}
        </div>
        <button class="modal-close" type="button" aria-label="Close dialog">${icon("close")}</button>
      </div>
      <div class="modal-body">${body}</div>
      ${footer ? `<div class="modal-foot">${footer}</div>` : ""}
    </div>`;
  root.appendChild(overlay);

  const dialog = overlay.querySelector(".modal");
  const close = () => {
    if (activeModal && activeModal.overlay === overlay) activeModal = null;
    document.removeEventListener("keydown", onKeydown);
    overlay.remove();
    document.body.style.overflow = "";
    if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
    if (typeof onClose === "function") onClose();
  };
  const onKeydown = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = dialog.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  overlay.querySelector(".modal-close").addEventListener("click", close);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) close();
  });
  document.addEventListener("keydown", onKeydown);
  document.body.style.overflow = "hidden";
  activeModal = { overlay, close, dialog };

  const autofocus = dialog.querySelector("[autofocus]");
  const initial = autofocus || dialog.querySelector("input, select, textarea, button");
  window.setTimeout(() => initial && initial.focus(), 30);

  return { overlay, dialog, close };
}

export function closeModal() {
  if (activeModal) activeModal.close();
}

export function confirmDialog({
  title,
  message,
  details = [],
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "primary",
}) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    const detailHtml = details.length
      ? `<dl class="confirm-summary">${details
          .map(
            (item) => `
              <div>
                <dt class="label">${escapeHtml(item.label)}</dt>
                <dd class="value">${escapeHtml(item.value)}</dd>
              </div>`,
          )
          .join("")}</dl>`
      : "";
    const { close } = openModal({
      title,
      size: "modal-sm",
      body: `
        <div class="confirm-body">
          <p>${escapeHtml(message)}</p>
          ${detailHtml}
        </div>`,
      footer: `
        <button class="btn btn-ghost" type="button" data-confirm-cancel>${escapeHtml(cancelLabel)}</button>
        <button class="btn btn-${tone === "danger" ? "danger" : "primary"}" type="button" data-confirm-ok>${escapeHtml(confirmLabel)}</button>`,
      onClose: () => finish(false),
    });
    const overlay = activeModal ? activeModal.overlay : null;
    if (overlay) {
      overlay.querySelector("[data-confirm-cancel]").addEventListener("click", () => {
        finish(false);
        close();
      });
      overlay.querySelector("[data-confirm-ok]").addEventListener("click", () => {
        finish(true);
        close();
      });
      overlay.querySelector("[data-confirm-ok]").focus();
    }
  });
}

/* -------------------------------------------------------------------------- */
/* Forms                                                                       */
/* -------------------------------------------------------------------------- */

export function setButtonBusy(button, busy, busyLabel = "Saving…") {
  if (!button) return;
  if (busy) {
    if (!button.dataset.originalHtml) button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    button.classList.add("is-busy");
    button.innerHTML = `<span class="spinner" aria-hidden="true"></span><span>${escapeHtml(busyLabel)}</span>`;
  } else {
    button.disabled = false;
    button.classList.remove("is-busy");
    if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
      delete button.dataset.originalHtml;
    }
  }
}

export function clearFieldErrors(container) {
  if (!container) return;
  container.querySelectorAll(".is-invalid").forEach((element) => element.classList.remove("is-invalid"));
  container.querySelectorAll(".field-error").forEach((element) => element.remove());
}

export function applyFieldErrors(container, fields) {
  if (!container || !fields) return;
  for (const [key, message] of Object.entries(fields)) {
    const input = container.querySelector(`[data-field="${key}"]`);
    if (!input) continue;
    input.classList.add("is-invalid");
    const target = input.closest("[data-error-target]") || input.closest(".field") || input.parentElement;
    const note = document.createElement("p");
    note.className = "field-error";
    note.textContent = message;
    target.appendChild(note);
  }
  const first = container.querySelector(".is-invalid");
  if (first) {
    first.scrollIntoView({ block: "center", behavior: "smooth" });
    first.focus({ preventScroll: true });
  }
}

/* -------------------------------------------------------------------------- */
/* Charts                                                                      */
/* -------------------------------------------------------------------------- */

export const CHART_COLORS = {
  green: "#24604a",
  greenSoft: "#7fa78f",
  greenPale: "#c9dacd",
  gold: "#c99b43",
  goldSoft: "#e4bd6a",
  ink: "#182620",
  muted: "#6b766e",
  grid: "#e9e3d5",
  surface: "#fffdf8",
  categoryPrimary: "#24604a",
  categoryJss: "#c99b43",
};

const chartInstances = new Set();

export function destroyCharts() {
  for (const chart of chartInstances) {
    try {
      chart.destroy();
    } catch {
      // A canvas that was already removed is harmless to ignore.
    }
  }
  chartInstances.clear();
}

export function createChart(canvas, config) {
  if (!canvas || typeof window.Chart === "undefined") return null;
  const chart = new window.Chart(canvas, config);
  chartInstances.add(chart);
  return chart;
}

export function moneyTooltip(context) {
  const value = context.raw;
  const numeric = typeof value === "object" && value !== null ? value.y ?? value.x ?? 0 : value;
  return `KSh ${new Intl.NumberFormat("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(numeric) || 0)}`;
}

export function baseChartOptions({ horizontal = false } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    animation: { duration: 500 },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#173f32",
        titleFont: { family: "Segoe UI, system-ui, sans-serif", size: 12, weight: "600" },
        bodyFont: { family: "Segoe UI, system-ui, sans-serif", size: 12 },
        padding: 10,
        cornerRadius: 8,
        displayColors: true,
        boxPadding: 4,
        callbacks: { label: moneyTooltip },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        border: { display: false },
        ticks: {
          color: CHART_COLORS.muted,
          font: { family: "Segoe UI, system-ui, sans-serif", size: 11 },
          maxRotation: 0,
          autoSkip: true,
        },
      },
      y: {
        beginAtZero: true,
        grid: { color: CHART_COLORS.grid, drawTicks: false },
        border: { display: false },
        ticks: {
          color: CHART_COLORS.muted,
          font: { family: "Segoe UI, system-ui, sans-serif", size: 10 },
          padding: 8,
          callback: (value) => compactTick(value),
        },
      },
    },
    ...(horizontal
      ? {
          indexAxis: "y",
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: CHART_COLORS.grid, drawTicks: false },
              border: { display: false },
              ticks: {
                color: CHART_COLORS.muted,
                font: { family: "Segoe UI, system-ui, sans-serif", size: 10 },
                callback: (value) => compactTick(value),
              },
            },
            y: {
              grid: { display: false },
              border: { display: false },
              ticks: {
                color: CHART_COLORS.ink,
                font: { family: "Segoe UI, system-ui, sans-serif", size: 11 },
                autoSkip: false,
              },
            },
          },
        }
      : {}),
  };
}

function compactTick(value) {
  const numeric = Number(value) || 0;
  if (Math.abs(numeric) >= 1_000_000) return `${(numeric / 1_000_000).toFixed(numeric >= 10_000_000 ? 0 : 1)}M`;
  if (Math.abs(numeric) >= 1_000) return `${Math.round(numeric / 1_000)}K`;
  return String(numeric);
}

/* -------------------------------------------------------------------------- */
/* Pagination                                                                  */
/* -------------------------------------------------------------------------- */

export function pagination({ page, pages }) {
  if (!pages || pages <= 1) {
    return `<div class="pagination"><span>Page 1 of 1</span></div>`;
  }
  const windowSize = 2;
  const numbers = [];
  for (let number = 1; number <= pages; number += 1) {
    if (number === 1 || number === pages || Math.abs(number - page) <= windowSize) {
      numbers.push(number);
    }
  }
  const parts = [];
  let last = 0;
  for (const number of numbers) {
    if (last && number - last > 1) parts.push('<span class="ellipsis">…</span>');
    parts.push(
      `<button type="button" data-page="${number}" ${number === page ? 'aria-current="page"' : ""} aria-label="Page ${number}">${number}</button>`,
    );
    last = number;
  }
  return `
    <div class="pagination">
      <span>Page ${page} of ${pages}</span>
      <div class="pager">
        <button type="button" data-page="${page - 1}" ${page <= 1 ? "disabled" : ""} aria-label="Previous page">${icon("chevronLeft")}</button>
        ${parts.join("")}
        <button type="button" data-page="${page + 1}" ${page >= pages ? "disabled" : ""} aria-label="Next page">${icon("chevronRight")}</button>
      </div>
    </div>`;
}
