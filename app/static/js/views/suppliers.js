/** Supplier directory and individual purchase history. */

import { api } from "../api.js";
import {
  amount,
  count,
  debounce,
  escapeHtml,
  formatDate,
  initials,
  money,
} from "../format.js";
import { state, writesEnabled } from "../store.js";
import {
  demoBadge,
  emptyState,
  errorPanel,
  icon,
  sectionBadge,
  statusBadge,
} from "../ui.js";
import { openSupplierDialog } from "./supplier-form.js";

export async function renderSuppliers(view, params, context) {
  const canWrite = writesEnabled();
  view.innerHTML = `
    <div class="view-inner">
      <div class="page-intro">
        <div>
          <h2>Who the school buys from</h2>
          <p class="lede">
            The businesses the school buys from, with their contact details and a running purchase history.
            Register a supplier once and reuse it on every voucher.
          </p>
        </div>
        <div class="page-intro-actions">
          ${canWrite ? `<button class="btn btn-primary" type="button" id="register-supplier">${icon("plus")}<span>Register supplier</span></button>` : ""}
        </div>
      </div>

      <section class="card">
        <div class="toolbar">
          <div class="field toolbar-search">
            <label for="supplier-search">Search suppliers</label>
            <div class="search-input">
              ${icon("search")}
              <input class="input" id="supplier-search" type="search" maxlength="120"
                placeholder="Name, contact person, phone or email…" value="${escapeHtml(state.supplierSearch)}">
            </div>
          </div>
          <div class="toolbar-actions">
            <button class="btn btn-ghost" type="button" id="clear-supplier-search">Clear</button>
          </div>
        </div>
        <div id="supplier-results" aria-live="polite">
          <div class="loading-panel">
            <span class="spinner" aria-hidden="true"></span>
            <p>Loading suppliers…</p>
          </div>
        </div>
      </section>
    </div>`;

  const results = view.querySelector("#supplier-results");
  const searchInput = view.querySelector("#supplier-search");
  let requestId = 0;

  async function load() {
    const id = ++requestId;
    results.classList.add("is-loading");
    try {
      const data = await api.listSuppliers(state.supplierSearch);
      if (id !== requestId) return;
      renderList(data.items, results, canWrite);
    } catch (error) {
      if (id !== requestId) return;
      results.innerHTML = errorPanel(error);
      results.querySelector("[data-retry]")?.addEventListener("click", load);
    } finally {
      if (id === requestId) results.classList.remove("is-loading");
    }
  }

  const applySearch = debounce(() => {
    state.supplierSearch = searchInput.value.trim();
    load();
  }, 280);
  searchInput.addEventListener("input", applySearch);
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      state.supplierSearch = searchInput.value.trim();
      load();
    }
  });

  view.querySelector("#clear-supplier-search").addEventListener("click", () => {
    state.supplierSearch = "";
    searchInput.value = "";
    searchInput.focus();
    load();
  });

  view.querySelector("#register-supplier")?.addEventListener("click", () => {
    openSupplierDialog({
      onCreated: () => {
        state.supplierSearch = "";
        searchInput.value = "";
        load();
      },
    });
  });

  await load();
}

function renderList(items, results, canWrite) {
  if (!items.length) {
    results.innerHTML = state.supplierSearch
      ? emptyState({
          title: "No suppliers match",
          message: `No supplier name, contact, phone or email matches “${state.supplierSearch}”. Clear the search to see the directory.`,
          iconName: "search",
        })
      : emptyState({
          title: "No suppliers registered",
          message: canWrite
            ? "Register the first supplier before recording a purchase."
            : "No supplier records are available in this demonstration yet.",
          iconName: "users",
        });
    return;
  }

  const approvedTotal = items.reduce((total, supplier) => total + supplier.approved_total_cents, 0);
  const purchases = items.reduce((total, supplier) => total + supplier.purchase_count, 0);

  results.innerHTML = `
    <div class="supplier-summary">
      <span><strong>${count(items.length)}</strong> ${items.length === 1 ? "supplier" : "suppliers"}</span>
      <span><strong>${count(purchases)}</strong> active ${purchases === 1 ? "purchase" : "purchases"}</span>
      <span class="supplier-summary-total">Approved spend: <strong>${money(approvedTotal)}</strong></span>
    </div>
    <div class="supplier-grid">
      ${items.map(supplierCard).join("")}
    </div>`;
}

function supplierCard(supplier) {
  return `
    <article class="card supplier-card">
      <div class="supplier-card-top">
        <span class="supplier-avatar" aria-hidden="true">${escapeHtml(initials(supplier.name))}</span>
        ${demoBadge(supplier.is_demo)}
      </div>
      <h3><a href="#/suppliers/${supplier.id}">${escapeHtml(supplier.name)}</a></h3>
      <div class="supplier-contact">
        ${supplier.contact_person ? `<span>${escapeHtml(supplier.contact_person)}</span>` : '<span class="muted">No contact person recorded</span>'}
        ${supplier.phone ? `<span>${escapeHtml(supplier.phone)}</span>` : ""}
        ${supplier.email ? `<span>${escapeHtml(supplier.email)}</span>` : ""}
      </div>
      <div class="supplier-stats">
        <div class="supplier-stat">
          <p class="label">Purchases</p>
          <p class="value">${count(supplier.purchase_count)}</p>
        </div>
        <div class="supplier-stat">
          <p class="label">Approved spend</p>
          <p class="value">${supplier.approved_total_cents ? money(supplier.approved_total_cents) : "—"}</p>
        </div>
      </div>
      <div class="supplier-card-foot">
        <span class="last">${supplier.last_purchase_date ? `Last purchase ${formatDate(supplier.last_purchase_date)}` : "No purchases yet"}</span>
        <a class="btn btn-subtle btn-sm" href="#/suppliers/${supplier.id}">History</a>
      </div>
    </article>`;
}

export async function renderSupplierDetail(view, params, context) {
  const id = Number(params[0]);
  let supplier;
  try {
    supplier = await api.getSupplier(id);
  } catch (error) {
    if (error.status === 404) {
      view.innerHTML = `
        <div class="view-inner">
          <div class="error-panel" role="alert">
            <span class="empty-icon">${icon("search")}</span>
            <h2>Supplier not found</h2>
            <p>That supplier does not exist in this database.</p>
            <a class="btn btn-primary" href="#/suppliers">Back to suppliers</a>
          </div>
        </div>`;
      return;
    }
    view.innerHTML = `<div class="view-inner">${errorPanel(error)}</div>`;
    return;
  }
  if (context && context.isCurrent && !context.isCurrent()) return;

  view.innerHTML = `
    <div class="view-inner">
      <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="#/suppliers">Suppliers</a>
        <span class="sep">/</span>
        <span>${escapeHtml(supplier.name)}</span>
      </nav>

      <section class="card supplier-hero">
        <div class="supplier-hero-main">
          <span class="supplier-avatar" aria-hidden="true">${escapeHtml(initials(supplier.name))}</span>
          <div>
            <div class="detail-title">
              <h2>${escapeHtml(supplier.name)}</h2>
              ${demoBadge(supplier.is_demo)}
            </div>
            <div class="contact-line">
              ${supplier.contact_person ? `<span>${escapeHtml(supplier.contact_person)}</span>` : ""}
              ${supplier.phone ? `<span>${icon("phone")} ${escapeHtml(supplier.phone)}</span>` : ""}
              ${supplier.email ? `<span>${icon("mail")} ${escapeHtml(supplier.email)}</span>` : ""}
              ${supplier.address ? `<span>${escapeHtml(supplier.address)}</span>` : ""}
            </div>
            ${supplier.notes ? `<p class="small muted mt-8">${escapeHtml(supplier.notes)}</p>` : ""}
          </div>
        </div>
        <div class="supplier-hero-stats">
          <div class="supplier-stat">
            <p class="label">Purchases</p>
            <p class="value">${count(supplier.purchase_count)}</p>
          </div>
          <div class="supplier-stat">
            <p class="label">Approved spend</p>
            <p class="value">${money(supplier.approved_total_cents)}</p>
          </div>
          <div class="supplier-stat">
            <p class="label">Awaiting approval</p>
            <p class="value">${money(supplier.pending_total_cents)}</p>
          </div>
          <div class="supplier-stat">
            <p class="label">Last purchase</p>
            <p class="value">${supplier.last_purchase_date ? formatDate(supplier.last_purchase_date) : "—"}</p>
          </div>
        </div>
      </section>

      <section class="card mt-16" aria-labelledby="history-title">
        <div class="card-head">
          <div>
            <h3 id="history-title">Purchase history</h3>
            <p>${count(supplier.history_total)} ${supplier.history_total === 1 ? "record" : "records"} · newest first</p>
          </div>
          <a class="btn btn-ghost btn-sm" href="#/purchases">Open register</a>
        </div>
        ${
          supplier.history.length
            ? `<div class="table-scroll">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>Reference</th>
                      <th>Date</th>
                      <th>Section</th>
                      <th class="hide-sm">Items</th>
                      <th>Status</th>
                      <th class="num">Amount (KSh)</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${supplier.history
                      .map(
                        (purchase) => `
                          <tr>
                            <td><a class="row-link mono" href="#/purchases/${purchase.id}">${escapeHtml(purchase.reference)}</a></td>
                            <td>${formatDate(purchase.purchase_date)}</td>
                            <td>${sectionBadge(purchase.category, purchase.category === "jss" ? "JSS" : "Primary")}</td>
                            <td class="hide-sm small muted">${escapeHtml(purchase.items_summary)}</td>
                            <td>${statusBadge(purchase.status, purchase.status_label)}</td>
                            <td class="num amount"><strong>${amount(purchase.total_cents)}</strong></td>
                          </tr>`,
                      )
                      .join("")}
                  </tbody>
                </table>
              </div>`
            : emptyState({
                title: "No purchases yet",
                message: "This supplier has not been used on a purchase. Record one to start the history.",
                iconName: "receipt",
                href: "#/purchases/new",
                action: "Record a purchase",
              })
        }
      </section>
    </div>`;
}
