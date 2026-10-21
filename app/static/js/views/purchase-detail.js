/** Purchase voucher: line items, totals and approval decisions. */

import { api } from "../api.js";
import {
  amount,
  count,
  escapeHtml,
  formatDate,
  formatDateTime,
  money,
} from "../format.js";
import { writesEnabled } from "../store.js";
import {
  confirmDialog,
  demoBadge,
  errorPanel,
  icon,
  sectionBadge,
  statusBadge,
  toast,
} from "../ui.js";

const ACTIONS = {
  approve: {
    status: "approved",
    title: "Approve this purchase?",
    message: "The purchase will be marked as approved and included in expenditure totals.",
    confirmLabel: "Approve purchase",
    tone: "primary",
    toastTitle: "Purchase approved",
  },
  reject: {
    status: "rejected",
    title: "Reject this purchase?",
    message: "The purchase will be marked as rejected and excluded from expenditure totals. It stays in the register for audit.",
    confirmLabel: "Reject purchase",
    tone: "danger",
    toastTitle: "Purchase rejected",
  },
  pending: {
    status: "pending",
    title: "Reopen for approval?",
    message: "The decision will be cleared and the purchase returned to the pending queue.",
    confirmLabel: "Set to pending",
    tone: "primary",
    toastTitle: "Purchase reopened",
  },
};

export async function renderPurchaseDetail(view, params, context) {
  const id = Number(params[0]);
  let purchase;
  try {
    purchase = await api.getPurchase(id);
  } catch (error) {
    if (error.status === 404) {
      view.innerHTML = `
        <div class="view-inner">
          <div class="error-panel" role="alert">
            <span class="empty-icon">${icon("search")}</span>
            <h2>Purchase not found</h2>
            <p>That purchase reference does not exist. It may have been removed from this database.</p>
            <a class="btn btn-primary" href="#/purchases">Back to the register</a>
          </div>
        </div>`;
      return;
    }
    view.innerHTML = `<div class="view-inner">${errorPanel(error)}</div>`;
    return;
  }
  if (context && context.isCurrent && !context.isCurrent()) return;

  const items = purchase.items;
  const totalQuantity = items.reduce((total, item) => total + item.quantity, 0);
  const isPending = purchase.status === "pending";
  const canWrite = writesEnabled();

  view.innerHTML = `
    <div class="view-inner">
      <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="#/purchases">Purchase register</a>
        <span class="sep">/</span>
        <span>${escapeHtml(purchase.reference)}</span>
      </nav>

      <div class="detail-head">
        <div>
          <div class="detail-title">
            <h2>${escapeHtml(purchase.reference)}</h2>
            ${statusBadge(purchase.status, purchase.status_label)}
            ${demoBadge(purchase.is_demo)}
          </div>
          <div class="detail-sub">
            <span>${formatDate(purchase.purchase_date)}</span>
            <span aria-hidden="true">·</span>
            ${sectionBadge(purchase.category, purchase.category_label)}
            <span aria-hidden="true">·</span>
            <span>${escapeHtml(purchase.payment_method_label)}</span>
            <span aria-hidden="true">·</span>
            <a href="#/suppliers/${purchase.supplier_id}">${escapeHtml(purchase.supplier_name)}</a>
          </div>
        </div>
        <div class="detail-actions">
          <a class="btn btn-ghost" href="#/purchases">${icon("arrowLeft")}<span>Back</span></a>
          <button class="btn btn-ghost" type="button" id="print-purchase">${icon("print")}<span>Print</span></button>
        </div>
      </div>

      <div class="detail-grid">
        <section class="card" aria-labelledby="items-title">
          <div class="card-head">
            <div>
              <h3 id="items-title">Line items</h3>
              <p>${count(items.length)} ${items.length === 1 ? "line" : "lines"} · ${count(totalQuantity)} ${totalQuantity === 1 ? "unit" : "units"} in total</p>
            </div>
          </div>
          <div class="table-scroll">
            <table class="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Description</th>
                  <th class="num">Qty</th>
                  <th class="num">Unit cost</th>
                  <th class="num">Line total</th>
                </tr>
              </thead>
              <tbody>
                ${items
                  .map(
                    (item, index) => `
                      <tr>
                        <td class="muted small">${index + 1}</td>
                        <td>${escapeHtml(item.description)}</td>
                        <td class="num">${count(item.quantity)}</td>
                        <td class="num">${amount(item.unit_cost_cents)}</td>
                        <td class="num amount"><strong>${amount(item.line_total_cents)}</strong></td>
                      </tr>`,
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
          <div class="detail-total-bar">
            <div>
              <p class="label">Total recorded</p>
              <p class="value">${money(purchase.total_cents)}</p>
            </div>
            <div class="text-right">
              <p class="label">Calculated from</p>
              <p class="amount"><strong>${count(items.length)} ${items.length === 1 ? "line item" : "line items"}</strong></p>
              <p class="small muted mt-8">${count(totalQuantity)} ${totalQuantity === 1 ? "unit" : "units"} · no taxes or adjustments</p>
            </div>
          </div>
          <div class="detail-note">
            <p class="meta-label">Notes</p>
            ${purchase.notes ? escapeHtml(purchase.notes) : '<span class="muted">No notes recorded for this purchase.</span>'}
          </div>
        </section>

        <aside>
          <section class="card approval-panel" aria-labelledby="approval-title">
            <div class="section-head">
              <div>
                <h3 id="approval-title">Approval</h3>
                <p>${approvalCopy(purchase.status)}</p>
              </div>
              ${statusBadge(purchase.status, purchase.status_label)}
            </div>

            <div class="approval-actions">
              ${
                !canWrite
                  ? `<p class="readonly-note">${icon("info")} Approval actions are disabled in this read-only demonstration.</p>`
                  : isPending
                    ? `<button class="btn btn-primary" type="button" data-action="approve">${icon("check")}<span>Approve purchase</span></button>
                       <button class="btn btn-danger-ghost" type="button" data-action="reject">${icon("close")}<span>Reject purchase</span></button>`
                    : `<button class="btn ${purchase.status === "rejected" ? "btn-primary" : "btn-danger-ghost"}" type="button" data-action="${purchase.status === "rejected" ? "approve" : "reject"}">
                         ${icon(purchase.status === "rejected" ? "check" : "close")}
                         <span>${purchase.status === "rejected" ? "Approve instead" : "Reject purchase"}</span>
                       </button>
                       <button class="btn btn-ghost" type="button" data-action="pending">${icon("refresh")}<span>Reopen as pending</span></button>`
              }
            </div>

            <div class="timeline">
              <div class="timeline-item">
                <p class="what">Recorded</p>
                <p class="when">${formatDateTime(purchase.created_at)}</p>
              </div>
              <div class="timeline-item">
                <p class="what">${purchase.decision_at ? escapeHtml(purchase.status_label) : "Awaiting a decision"}</p>
                <p class="when">${purchase.decision_at ? formatDateTime(purchase.decision_at) : "No decision recorded yet"}</p>
              </div>
            </div>
            <p class="small muted mt-16">Approval is a status change recorded against this purchase. This prototype has no user accounts or role permissions.</p>
          </section>

          <section class="card mt-16" aria-labelledby="details-title">
            <div class="card-head">
              <div>
                <h3 id="details-title">Record details</h3>
                <p>Source information for the voucher</p>
              </div>
            </div>
            <div class="meta-grid">
              <div class="meta-item">
                <p class="meta-label">Supplier</p>
                <p class="meta-value"><a href="#/suppliers/${purchase.supplier_id}">${escapeHtml(purchase.supplier_name)}</a></p>
              </div>
              <div class="meta-item">
                <p class="meta-label">Invoice / receipt</p>
                <p class="meta-value mono">${purchase.invoice_number ? escapeHtml(purchase.invoice_number) : '<span class="muted">Not recorded</span>'}</p>
              </div>
              <div class="meta-item">
                <p class="meta-label">Payment method</p>
                <p class="meta-value">${escapeHtml(purchase.payment_method_label)}</p>
              </div>
              <div class="meta-item">
                <p class="meta-label">School section</p>
                <p class="meta-value">${escapeHtml(purchase.category_label)}</p>
              </div>
              <div class="meta-item">
                <p class="meta-label">Recorded</p>
                <p class="meta-value">${formatDateTime(purchase.created_at)}</p>
              </div>
              <div class="meta-item">
                <p class="meta-label">Last updated</p>
                <p class="meta-value">${formatDateTime(purchase.updated_at)}</p>
              </div>
            </div>
            ${
              purchase.is_demo
                ? `<div class="detail-note"><p class="small">This is fictional demonstration data. Its invoice number begins with <strong>DEMO-</strong>.</p></div>`
                : ""
            }
          </section>
        </aside>
      </div>
    </div>`;

  view.querySelector("#print-purchase").addEventListener("click", () => window.print());

  view.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = ACTIONS[button.dataset.action];
      if (!action) return;
      const confirmed = await confirmDialog({
        title: action.title,
        message: action.message,
        details: [
          { label: "Reference", value: purchase.reference },
          { label: "Supplier", value: purchase.supplier_name },
          { label: "Amount", value: money(purchase.total_cents) },
        ],
        confirmLabel: action.confirmLabel,
        tone: action.tone,
      });
      if (!confirmed) return;

      const buttons = view.querySelectorAll("[data-action]");
      buttons.forEach((item) => {
        item.disabled = true;
      });
      button.textContent = "Saving…";
      try {
        await api.updatePurchaseStatus(purchase.id, action.status);
        toast(`${purchase.reference} is now ${action.status}.`, { title: action.toastTitle });
        await renderPurchaseDetail(view, params, context);
      } catch (error) {
        buttons.forEach((item) => {
          item.disabled = false;
        });
        toast(error.message, { title: "Could not update the purchase", type: "error" });
        await renderPurchaseDetail(view, params, context);
      }
    });
  });
}

function approvalCopy(status) {
  if (status === "approved") {
    return "This purchase is approved and included in expenditure totals.";
  }
  if (status === "rejected") {
    return "This purchase is rejected and excluded from expenditure totals.";
  }
  return "This purchase is waiting for a decision. Approving adds it to approved expenditure.";
}
