/** Expenditure reports by period, supplier, section and payment method. */

import { api } from "../api.js";
import {
  amount,
  count,
  escapeHtml,
  formatDate,
  money,
  percent,
} from "../format.js";
import {
  categoryLabel,
  categoryParam,
  reportRange,
  state,
  writesEnabled,
} from "../store.js";
import {
  baseChartOptions,
  CHART_COLORS,
  createChart,
  emptyState,
  icon,
} from "../ui.js";

const PRESETS = [
  ["ytd", "Year to date"],
  ["this-month", "This month"],
  ["last-30", "Last 30 days"],
  ["last-12", "Last 12 months"],
  ["custom", "Custom range"],
];

export async function renderReports(view, params, context) {
  if (!state.report.from || !state.report.to) {
    const range = reportRange(state.report.preset || "ytd");
    state.report.from = range.from;
    state.report.to = range.to;
  }

  view.innerHTML = `
    <div class="view-inner">
      <div class="page-intro">
        <div>
          <h2>Spending overview</h2>
          <p class="lede">
            Group approved spending by period, supplier, school section and payment method.
            Change the school section with the selector in the top bar.
          </p>
        </div>
        <div class="page-intro-actions no-print">
          <a class="btn btn-ghost" href="#/purchases">${icon("receipt")}<span>Purchase register</span></a>
          <button class="btn btn-primary" type="button" id="print-report">${icon("print")}<span>Print report</span></button>
        </div>
      </div>

      <section class="card report-controls no-print" aria-label="Report controls">
        <div class="field">
          <label for="report-preset">Period</label>
          <select class="select" id="report-preset">
            ${PRESETS.map(
              ([value, label]) =>
                `<option value="${value}" ${state.report.preset === value ? "selected" : ""}>${label}</option>`,
            ).join("")}
          </select>
        </div>
        <div class="field">
          <label for="report-from">From</label>
          <input class="input" id="report-from" type="date" value="${escapeHtml(state.report.from)}">
        </div>
        <div class="field">
          <label for="report-to">To</label>
          <input class="input" id="report-to" type="date" value="${escapeHtml(state.report.to)}">
        </div>
        <div class="field">
          <label for="report-scope">Approval scope</label>
          <select class="select" id="report-scope">
            <option value="approved" ${state.report.status === "approved" ? "selected" : ""}>Approved only</option>
            <option value="active" ${state.report.status === "active" ? "selected" : ""}>All except rejected</option>
          </select>
        </div>
        <div class="toolbar-actions">
          <span class="small muted">Section: <strong>${escapeHtml(categoryLabel())}</strong></span>
        </div>
      </section>

      <div id="report-results" aria-live="polite">
        <div class="loading-panel">
          <span class="spinner" aria-hidden="true"></span>
          <p>Building the report…</p>
        </div>
      </div>
    </div>`;

  const results = view.querySelector("#report-results");
  const presetInput = view.querySelector("#report-preset");
  const fromInput = view.querySelector("#report-from");
  const toInput = view.querySelector("#report-to");
  const scopeInput = view.querySelector("#report-scope");
  let requestId = 0;

  function syncInputs() {
    presetInput.value = state.report.preset;
    fromInput.value = state.report.from;
    toInput.value = state.report.to;
    scopeInput.value = state.report.status;
  }

  function showDateError(message) {
    results.classList.remove("is-loading");
    results.innerHTML = `
      <div class="filter-error">
        <span class="empty-icon">${icon("alert")}</span>
        <div>
          <h3>Check the report dates</h3>
          <p>${escapeHtml(message)}</p>
        </div>
        <button class="btn btn-ghost btn-sm" type="button" data-focus-from>Adjust dates</button>
      </div>`;
    results.querySelector("[data-focus-from]").addEventListener("click", () => fromInput.focus());
  }

  async function load() {
    // Invalidate any in-flight request before validating, so a late response
    // cannot overwrite a date-range error.
    const id = ++requestId;
    if (!state.report.from || !state.report.to) {
      showDateError("Choose both a start and an end date for the report.");
      return;
    }
    if (state.report.from > state.report.to) {
      showDateError("The “From” date must be on or before the “To” date.");
      return;
    }
    results.classList.add("is-loading");
    try {
      const data = await api.reports({
        from: state.report.from,
        to: state.report.to,
        category: categoryParam(),
        status: state.report.status,
      });
      if (id !== requestId) return;
      renderReport(data, results);
    } catch (error) {
      if (id !== requestId) return;
      results.innerHTML = `
        <div class="error-panel" role="alert">
          <span class="empty-icon">${icon("alert")}</span>
          <h2>Could not build the report</h2>
          <p>${escapeHtml(error.message)}</p>
          <button class="btn btn-primary" type="button" data-report-retry>Try again</button>
        </div>`;
      results.querySelector("[data-report-retry]").addEventListener("click", load);
    } finally {
      if (id === requestId) results.classList.remove("is-loading");
    }
  }

  presetInput.addEventListener("change", () => {
    state.report.preset = presetInput.value;
    if (state.report.preset !== "custom") {
      const range = reportRange(state.report.preset);
      state.report.from = range.from;
      state.report.to = range.to;
      syncInputs();
    } else {
      fromInput.focus();
    }
    load();
  });

  for (const input of [fromInput, toInput]) {
    input.addEventListener("change", () => {
      state.report.preset = "custom";
      state.report.from = fromInput.value;
      state.report.to = toInput.value;
      presetInput.value = "custom";
      load();
    });
  }

  scopeInput.addEventListener("change", () => {
    state.report.status = scopeInput.value;
    load();
  });

  view.querySelector("#print-report").addEventListener("click", () => window.print());

  await load();
}

function renderReport(data, results) {
  const scopeLabel = data.status_scope === "approved" ? "Approved expenditure" : "Recorded expenditure";
  const topSupplier = data.by_supplier[0];
  const pendingNote =
    data.status_scope === "approved" && data.pending_total_cents > 0
      ? `<div class="report-note">${icon("info")} ${money(data.pending_total_cents)} in pending purchases is not included in this approved-only report.</div>`
      : "";

  if (!data.record_count) {
    results.innerHTML = `
      ${pendingNote}
      <div class="card">
        ${emptyState({
          title: "No purchases in this period",
          message: `There are no ${data.status_scope === "approved" ? "approved " : ""}purchases for ${categoryLabel().toLowerCase()} between ${formatDate(data.from)} and ${formatDate(data.to)}. Try a wider date range${writesEnabled() ? " or record a purchase" : ""}.`,
          iconName: "chart",
          href: writesEnabled() ? "#/purchases/new" : "",
          action: writesEnabled() ? "Record a purchase" : "",
        })}
      </div>`;
    return;
  }

  results.innerHTML = `
    <section class="kpi-grid report-kpis" aria-label="Report summary">
      <article class="card kpi">
        <div class="kpi-top">
          <span class="kpi-label">${escapeHtml(scopeLabel)}</span>
          <span class="kpi-icon">${icon("wallet")}</span>
        </div>
        <p class="kpi-value"><span class="currency">KSh</span>${amount(data.total_cents)}</p>
        <p class="kpi-note">${formatDate(data.from)} – ${formatDate(data.to)}</p>
      </article>
      <article class="card kpi kpi-count">
        <div class="kpi-top">
          <span class="kpi-label">Purchases</span>
          <span class="kpi-icon">${icon("receipt")}</span>
        </div>
        <p class="kpi-value">${count(data.record_count)}</p>
        <p class="kpi-note">Grouped by ${escapeHtml(data.granularity)}</p>
      </article>
      <article class="card kpi kpi-pending">
        <div class="kpi-top">
          <span class="kpi-label">Average purchase</span>
          <span class="kpi-icon">${icon("chart")}</span>
        </div>
        <p class="kpi-value"><span class="currency">KSh</span>${amount(data.average_cents)}</p>
        <p class="kpi-note">Average across ${count(data.record_count)} records</p>
      </article>
      <article class="card kpi kpi-suppliers">
        <div class="kpi-top">
          <span class="kpi-label">Top supplier</span>
          <span class="kpi-icon">${icon("users")}</span>
        </div>
        <p class="kpi-value"><span class="currency">KSh</span>${amount(topSupplier ? topSupplier.total_cents : 0)}</p>
        <p class="kpi-note">${topSupplier ? escapeHtml(topSupplier.supplier_name) : "No supplier activity"}</p>
      </article>
    </section>
    ${pendingNote}

    <div class="report-charts">
      <section class="card" aria-labelledby="period-chart-title">
        <div class="card-head">
          <div>
            <h3 id="period-chart-title">Expenditure over time</h3>
            <p>${escapeHtml(capitalise(data.granularity))} totals for the selected period</p>
          </div>
        </div>
        <div class="chart-wrap" id="period-chart-wrap">
          <canvas id="period-chart" aria-label="Expenditure over time" role="img"></canvas>
        </div>
      </section>

      <section class="card" aria-labelledby="supplier-chart-title">
        <div class="card-head">
          <div>
            <h3 id="supplier-chart-title">Spend by supplier</h3>
            <p>The largest suppliers in this period</p>
          </div>
        </div>
        <div class="chart-wrap" id="supplier-chart-wrap">
          <canvas id="supplier-chart" aria-label="Expenditure by supplier" role="img"></canvas>
        </div>
      </section>

      <section class="card" aria-labelledby="category-chart-title">
        <div class="card-head">
          <div>
            <h3 id="category-chart-title">Section split</h3>
            <p>Primary versus JSS in this period</p>
          </div>
        </div>
        <div class="chart-wrap" id="category-chart-wrap">
          <canvas id="category-chart" aria-label="Expenditure by school section" role="img"></canvas>
        </div>
      </section>
    </div>

    <div class="report-grid">
      ${periodCard(data)}
      ${supplierCard(data)}
      ${categoryCard(data)}
      ${paymentCard(data)}
    </div>`;

  drawPeriodChart(data);
  drawSupplierChart(data);
  drawCategoryChart(data);
}

function periodCard(data) {
  return `
    <section class="card" aria-labelledby="period-table-title">
      <div class="card-head">
        <div>
          <h3 id="period-table-title">By period</h3>
          <p>${escapeHtml(capitalise(data.granularity))} totals</p>
        </div>
      </div>
      ${breakdownTable(
        data.by_period.map((row) => ({
          label: row.label,
          count: row.count,
          total_cents: row.total_cents,
        })),
        "Period",
        data.total_cents,
      )}
    </section>`;
}

function supplierCard(data) {
  return `
    <section class="card" aria-labelledby="supplier-table-title">
      <div class="card-head">
        <div>
          <h3 id="supplier-table-title">By supplier</h3>
          <p>Ranked by expenditure</p>
        </div>
      </div>
      ${breakdownTable(
        data.by_supplier.map((row) => ({
          label: row.supplier_name,
          href: `#/suppliers/${row.supplier_id}`,
          count: row.count,
          total_cents: row.total_cents,
        })),
        "Supplier",
        data.total_cents,
      )}
    </section>`;
}

function categoryCard(data) {
  return `
    <section class="card" aria-labelledby="category-table-title">
      <div class="card-head">
        <div>
          <h3 id="category-table-title">By school section</h3>
          <p>Primary and JSS kept separate</p>
        </div>
      </div>
      ${breakdownTable(
        data.by_category.map((row) => ({
          label: row.label,
          count: row.count,
          total_cents: row.total_cents,
        })),
        "Section",
        data.total_cents,
      )}
    </section>`;
}

function paymentCard(data) {
  return `
    <section class="card" aria-labelledby="payment-table-title">
      <div class="card-head">
        <div>
          <h3 id="payment-table-title">By payment method</h3>
          <p>How the school paid</p>
        </div>
      </div>
      ${breakdownTable(
        data.by_payment.map((row) => ({
          label: row.label,
          count: row.count,
          total_cents: row.total_cents,
        })),
        "Method",
        data.total_cents,
      )}
    </section>`;
}

function breakdownTable(rows, labelHeader, total) {
  if (!rows.length || !rows.some((row) => row.count)) {
    return `<div class="table-empty">No records in this period.</div>`;
  }
  return `
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th>${escapeHtml(labelHeader)}</th>
            <th class="num">Records</th>
            <th class="num">Amount (KSh)</th>
            <th class="num">Share</th>
          </tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (row) => `
                <tr>
                  <td>${row.href ? `<a class="row-link" href="${row.href}">${escapeHtml(row.label)}</a>` : escapeHtml(row.label)}</td>
                  <td class="num">${count(row.count)}</td>
                  <td class="num amount">${amount(row.total_cents)}</td>
                  <td class="num nowrap"><span class="share-bar" aria-hidden="true"><span style="width:${percent(row.total_cents, total)}%"></span></span>${percent(row.total_cents, total)}%</td>
                </tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </div>
    <div class="report-table-total">
      <span>${rows.length} ${rows.length === 1 ? "group" : "groups"}</span>
      <span>Total <strong>${money(total)}</strong></span>
    </div>`;
}

function drawPeriodChart(data) {
  const canvas = document.getElementById("period-chart");
  if (!canvas) return;
  if (!data.by_period.length) {
    emptyChart("period-chart-wrap", "No data", "Choose a wider period.");
    return;
  }
  const options = baseChartOptions();
  options.plugins.tooltip.callbacks.label = (contextValue) => money(contextValue.raw * 100);
  createChart(canvas, {
    type: "bar",
    data: {
      labels: data.by_period.map((row) => row.label),
      datasets: [
        {
          label: "Expenditure",
          data: data.by_period.map((row) => row.total_cents / 100),
          backgroundColor: CHART_COLORS.green,
          borderRadius: 4,
          maxBarThickness: 42,
        },
      ],
    },
    options,
  });
}

function drawSupplierChart(data) {
  const canvas = document.getElementById("supplier-chart");
  if (!canvas) return;
  const rows = data.by_supplier.slice(0, 8);
  if (!rows.length) {
    emptyChart("supplier-chart-wrap", "No suppliers", "No supplier activity in this period.");
    return;
  }
  const labels = rows.map((row) => truncate(row.supplier_name, 24));
  const options = baseChartOptions({ horizontal: true });
  options.scales.y.ticks.callback = (value, index) => labels[index] || value;
  options.plugins.tooltip.callbacks.label = (contextValue) => money(contextValue.raw * 100);
  createChart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Expenditure",
          data: rows.map((row) => row.total_cents / 100),
          backgroundColor: CHART_COLORS.gold,
          borderRadius: 4,
          maxBarThickness: 24,
        },
      ],
    },
    options,
  });
}

function drawCategoryChart(data) {
  const canvas = document.getElementById("category-chart");
  if (!canvas) return;
  const rows = data.by_category.filter((row) => row.total_cents > 0);
  if (!rows.length) {
    emptyChart("category-chart-wrap", "No data", "No approved spend in this period.");
    return;
  }
  createChart(canvas, {
    type: "doughnut",
    data: {
      labels: rows.map((row) => (row.category === "jss" ? "JSS" : "Primary")),
      datasets: [
        {
          data: rows.map((row) => row.total_cents / 100),
          backgroundColor: rows.map((row) =>
            row.category === "jss" ? CHART_COLORS.categoryJss : CHART_COLORS.categoryPrimary,
          ),
          borderColor: CHART_COLORS.surface,
          borderWidth: 3,
          hoverOffset: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "64%",
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: CHART_COLORS.muted,
            boxWidth: 9,
            boxHeight: 9,
            usePointStyle: true,
            padding: 16,
            font: { family: "Segoe UI, system-ui, sans-serif", size: 11 },
          },
        },
        tooltip: {
          backgroundColor: "#173f32",
          padding: 10,
          cornerRadius: 8,
          callbacks: { label: (contextValue) => `${contextValue.label}: ${money(contextValue.raw * 100)}` },
        },
      },
    },
  });
}

function emptyChart(wrapperId, title, message) {
  const wrapper = document.getElementById(wrapperId);
  if (!wrapper) return;
  wrapper.innerHTML = `
    <div class="chart-empty">
      ${icon("chart")}
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(message)}</span>
    </div>`;
}

function capitalise(value) {
  return String(value || "").charAt(0).toUpperCase() + String(value || "").slice(1);
}

function truncate(value, limit) {
  const text = String(value || "");
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
}
