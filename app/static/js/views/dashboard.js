/** Dashboard: headline figures, trends, recent records and approval queue. */

import { api } from "../api.js";
import { amount, count, escapeHtml, formatDate, money, percent } from "../format.js";
import { categoryLabel, categoryParam, state, writesEnabled } from "../store.js";
import {
  baseChartOptions,
  CHART_COLORS,
  confirmDialog,
  createChart,
  emptyState,
  icon,
  demoBadge,
  sectionBadge,
  statusBadge,
  toast,
} from "../ui.js";

export async function renderDashboard(view, params, context) {
  const data = await api.dashboard(categoryParam());
  if (context && !context.isCurrent()) return;

  const refresh = () => renderDashboard(view, params, context);
  const canWrite = writesEnabled();
  const approvedTotal = data.approved_total_cents;
  const scope = categoryLabel();
  const rejectedNote = data.rejected_count
    ? ` ${count(data.rejected_count)} rejected ${data.rejected_count === 1 ? "record is" : "records are"} excluded.`
    : "";

  view.innerHTML = `
    <div class="view-inner">
      <div class="page-intro">
        <div>
          <h2>Purchases at a glance</h2>
          <p class="lede">
            Approved expenditure, pending decisions and recent activity for <strong>${escapeHtml(scope.toLowerCase())}</strong>.
            Figures are calculated by the server from recorded line items.
          </p>
        </div>
        <div class="page-intro-actions">
          <a class="btn btn-ghost" href="#/reports">${icon("chart")}<span>Open reports</span></a>
          ${canWrite ? `<a class="btn btn-primary" href="#/purchases/new">${icon("plus")}<span>Record purchase</span></a>` : ""}
        </div>
      </div>

      <section class="kpi-grid" aria-label="Headline figures">
        <article class="card kpi">
          <div class="kpi-top">
            <span class="kpi-label">Approved expenditure</span>
            <span class="kpi-icon">${icon("wallet")}</span>
          </div>
          <p class="kpi-value"><span class="currency">KSh</span>${amount(approvedTotal)}</p>
          <p class="kpi-note">Across <strong>${count(data.approved_count)}</strong> approved ${data.approved_count === 1 ? "purchase" : "purchases"}</p>
        </article>

        <article class="card kpi kpi-count">
          <div class="kpi-top">
            <span class="kpi-label">Purchase records</span>
            <span class="kpi-icon">${icon("receipt")}</span>
          </div>
          <p class="kpi-value">${count(data.record_count)}</p>
          <p class="kpi-note">${money(data.record_total_cents)} recorded in total.${escapeHtml(rejectedNote)}</p>
        </article>

        <article class="card kpi kpi-pending">
          <div class="kpi-top">
            <span class="kpi-label">Pending approvals</span>
            <span class="kpi-icon">${icon("clock")}</span>
          </div>
          <p class="kpi-value">${count(data.pending_count)}</p>
          <p class="kpi-note"><strong>${money(data.pending_total_cents)}</strong> awaiting a decision</p>
          ${data.pending_count ? '<button class="kpi-link" type="button" data-review-pending>Review queue →</button>' : ""}
        </article>

        <article class="card kpi kpi-suppliers">
          <div class="kpi-top">
            <span class="kpi-label">Suppliers used</span>
            <span class="kpi-icon">${icon("users")}</span>
          </div>
          <p class="kpi-value">${count(data.supplier_count)}</p>
          <p class="kpi-note">Suppliers with active purchases in this view</p>
        </article>
      </section>

      <div class="dashboard-charts">
        <section class="card" aria-labelledby="trend-title">
          <div class="card-head">
            <div>
              <h3 id="trend-title">Expenditure trend</h3>
              <p>Approved purchases over the last six months</p>
            </div>
            <div class="chart-legend" aria-hidden="true">
              <span class="legend-item"><span class="legend-swatch"></span> Primary</span>
              <span class="legend-item"><span class="legend-swatch gold"></span> JSS</span>
            </div>
          </div>
          <div class="chart-wrap" id="trend-wrap">
            <canvas id="trend-chart" aria-label="Monthly approved expenditure" role="img"></canvas>
          </div>
        </section>

        <section class="card" aria-labelledby="split-title">
          <div class="card-head">
            <div>
              <h3 id="split-title">Spend by section</h3>
              <p>Approved expenditure, all time</p>
            </div>
          </div>
          <div class="chart-wrap chart-sm" id="split-wrap">
            <canvas id="split-chart" aria-label="Approved expenditure by school section" role="img"></canvas>
          </div>
          <div class="category-legend" id="split-legend"></div>
        </section>
      </div>

      <div class="dashboard-lists">
        <section class="card" aria-labelledby="recent-title">
          <div class="card-head">
            <div>
              <h3 id="recent-title">Recent purchases</h3>
              <p>The latest records in the purchase register</p>
            </div>
            <a href="#/purchases">View register →</a>
          </div>
          ${recentTable(data.recent, canWrite)}
        </section>

        <section class="card" aria-labelledby="queue-title">
          <div class="card-head">
            <div>
              <h3 id="queue-title">Awaiting approval</h3>
              <p>${data.pending_count ? `${count(data.pending_count)} ${data.pending_count === 1 ? "record needs" : "records need"} a decision` : "Nothing in the queue"}</p>
            </div>
          </div>
          ${pendingList(data.pending, canWrite)}
        </section>
      </div>
    </div>`;

  drawTrend(data.monthly);
  drawSplit(data.category_breakdown, approvedTotal);

  view.querySelector("[data-review-pending]")?.addEventListener("click", () => {
    state.purchaseFilters.status = "pending";
    state.purchaseFilters.page = 1;
    window.location.hash = "#/purchases";
  });

  if (canWrite) view.querySelectorAll("[data-quick-approve]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = Number(button.dataset.quickApprove);
      const reference = button.dataset.reference;
      const supplier = button.dataset.supplier;
      const total = Number(button.dataset.total);
      const confirmed = await confirmDialog({
        title: "Approve this purchase?",
        message: "The purchase will be marked as approved and counted in approved expenditure.",
        details: [
          { label: "Reference", value: reference },
          { label: "Supplier", value: supplier },
          { label: "Amount", value: money(total) },
        ],
        confirmLabel: "Approve purchase",
      });
      if (!confirmed) return;
      button.disabled = true;
      button.textContent = "Approving…";
      try {
        await api.updatePurchaseStatus(id, "approved");
        toast(`${reference} has been approved.`, { title: "Purchase approved" });
        await refresh();
      } catch (error) {
        button.disabled = false;
        button.textContent = "Approve";
        toast(error.message, { title: "Could not approve", type: "error" });
      }
    });
  });
}

function recentTable(items, canWrite) {
  if (!items.length) {
    return emptyState({
      title: "No purchases recorded yet",
      message: canWrite
        ? "Record the first purchase to start building the expenditure history."
        : "No purchase records are available in this demonstration yet.",
      iconName: "receipt",
      href: canWrite ? "#/purchases/new" : "",
      action: canWrite ? "Record a purchase" : "",
    });
  }
  return `
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th>Reference</th>
            <th>Supplier</th>
            <th>Section</th>
            <th class="num">Amount</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${items
            .map(
              (item) => `
                <tr>
                  <td>
                    <a class="row-link mono" href="#/purchases/${item.id}">${escapeHtml(item.reference)}</a>
                    <div class="secondary small muted">${formatDate(item.purchase_date)} ${demoBadge(item.is_demo)}</div>
                  </td>
                  <td><div class="cell-stack"><span class="primary">${escapeHtml(item.supplier_name)}</span><span class="secondary">${escapeHtml(item.items_summary)}</span></div></td>
                  <td>${sectionBadge(item.category, item.category === "jss" ? "JSS" : "Primary")}</td>
                  <td class="num amount">${amount(item.total_cents)}</td>
                  <td>${statusBadge(item.status, item.status_label)}</td>
                </tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </div>`;
}

function pendingList(items, canWrite) {
  if (!items.length) {
    return `<div class="pending-empty">All caught up — no purchases are waiting for approval.</div>`;
  }
  return `
    <div class="pending-list">
      ${items
        .map(
          (item) => `
            <div class="pending-item">
              <div>
                <a class="ref" href="#/purchases/${item.id}">${escapeHtml(item.reference)}</a>
                <p class="who">${escapeHtml(item.supplier_name)}</p>
                <p class="when">${formatDate(item.purchase_date)} · ${escapeHtml(item.category === "jss" ? "JSS" : "Primary")} ${demoBadge(item.is_demo)}</p>
              </div>
              <div class="right">
                <span class="amount">${money(item.total_cents)}</span>
                ${
                  canWrite
                    ? `<button
                         class="btn btn-ghost btn-sm"
                         type="button"
                         data-quick-approve="${item.id}"
                         data-reference="${escapeHtml(item.reference)}"
                         data-supplier="${escapeHtml(item.supplier_name)}"
                         data-total="${item.total_cents}"
                       >Approve</button>`
                    : `<a class="btn btn-subtle btn-sm" href="#/purchases/${item.id}">Review</a>`
                }
              </div>
            </div>`,
        )
        .join("")}
    </div>`;
}

function drawTrend(monthly) {
  const canvas = document.getElementById("trend-chart");
  if (!canvas) return;
  const hasData = monthly.some((point) => point.total_cents > 0);
  if (!hasData) {
    showChartEmpty("trend-wrap", "No approved expenditure yet", "Approve a purchase to see the trend.");
    return;
  }
  const options = baseChartOptions();
  options.scales.x.stacked = true;
  options.scales.y.stacked = true;
  options.scales.x.ticks.maxRotation = 0;
  options.plugins.tooltip.callbacks.label = (contextValue) =>
    `${contextValue.dataset.label}: ${money(contextValue.raw)}`;

  createChart(canvas, {
    type: "bar",
    data: {
      labels: monthly.map((point) => point.label),
      datasets: [
        {
          label: "Primary",
          data: monthly.map((point) => point.primary_cents / 100),
          backgroundColor: CHART_COLORS.green,
          borderRadius: 4,
          maxBarThickness: 38,
        },
        {
          label: "JSS",
          data: monthly.map((point) => point.jss_cents / 100),
          backgroundColor: CHART_COLORS.gold,
          borderRadius: 4,
          maxBarThickness: 38,
        },
      ],
    },
    options,
  });
}

function drawSplit(breakdown, total) {
  const canvas = document.getElementById("split-chart");
  const legend = document.getElementById("split-legend");
  if (!canvas || !legend) return;
  const visible = breakdown.filter((item) => item.total_cents > 0);
  if (!visible.length) {
    showChartEmpty("split-wrap", "No approved spend yet", "The section split appears after approval.");
    legend.innerHTML = "";
    return;
  }
  const labels = visible.map((item) => (item.category === "jss" ? "JSS" : "Primary"));
  const values = visible.map((item) => item.total_cents / 100);
  createChart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: values,
          backgroundColor: visible.map((item) =>
            item.category === "jss" ? CHART_COLORS.categoryJss : CHART_COLORS.categoryPrimary,
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
      cutout: "67%",
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#173f32",
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (contextValue) => `${contextValue.label}: ${money(contextValue.raw * 100)}`,
          },
        },
      },
    },
  });

  legend.innerHTML = visible
    .map(
      (item) => `
        <div class="category-legend-row">
          <span class="legend-swatch ${item.category === "jss" ? "gold" : ""}"></span>
          <span class="category-name">${escapeHtml(item.label)}</span>
          <span class="category-share">${percent(item.total_cents, total)}%</span>
          <strong>${money(item.total_cents)}</strong>
        </div>`,
    )
    .join("");
}

function showChartEmpty(wrapperId, title, message) {
  const wrapper = document.getElementById(wrapperId);
  if (!wrapper) return;
  wrapper.innerHTML = `
    <div class="chart-empty">
      ${icon("chart")}
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(message)}</span>
    </div>`;
}
