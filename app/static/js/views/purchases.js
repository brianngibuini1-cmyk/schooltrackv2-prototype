/** Purchase register: search, date/section filters, totals and CSV export. */

import { api } from "../api.js";
import {
  amount,
  count,
  debounce,
  escapeHtml,
  formatDate,
  money,
} from "../format.js";
import { categoryLabel, categoryParam, state, writesEnabled } from "../store.js";
import {
  demoBadge,
  emptyState,
  icon,
  pagination,
  sectionBadge,
  statusBadge,
} from "../ui.js";

const STATUS_LABELS = {
  pending: "Pending approval",
  approved: "Approved",
  rejected: "Rejected",
};

export async function renderPurchases(view, params, context) {
  const [suppliers] = await Promise.all([api.listSuppliers("")]);
  if (context && context.isCurrent && !context.isCurrent()) return;
  const supplierMap = new Map(suppliers.items.map((supplier) => [String(supplier.id), supplier.name]));
  const canWrite = writesEnabled();

  const filters = state.purchaseFilters;
  view.innerHTML = `
    <div class="view-inner">
      <div class="page-intro">
        <div>
          <h2>All purchase records</h2>
          <p class="lede">
            Every recorded purchase for <strong>${escapeHtml(categoryLabel().toLowerCase())}</strong>.
            Search by reference, supplier, invoice number or item, then narrow by date and approval status.
          </p>
        </div>
        <div class="page-intro-actions">
          <a class="btn btn-ghost" id="export-csv" href="#" download>${icon("download")}<span>Export CSV</span></a>
          ${canWrite ? `<a class="btn btn-primary" href="#/purchases/new">${icon("plus")}<span>New purchase</span></a>` : ""}
        </div>
      </div>

      <section class="card" id="purchase-card">
        <div class="toolbar" role="search" aria-label="Filter purchases">
          <div class="field toolbar-search">
            <label for="filter-search">Search</label>
            <div class="search-input">
              ${icon("search")}
              <input class="input" id="filter-search" type="search" maxlength="120"
                placeholder="Reference, supplier, invoice or item…" value="${escapeHtml(filters.search)}">
            </div>
          </div>
          <div class="field">
            <label for="filter-from">From</label>
            <input class="input" id="filter-from" type="date" value="${escapeHtml(filters.from)}">
          </div>
          <div class="field">
            <label for="filter-to">To</label>
            <input class="input" id="filter-to" type="date" value="${escapeHtml(filters.to)}">
          </div>
          <div class="field">
            <label for="filter-status">Status</label>
            <select class="select" id="filter-status">
              <option value="">All statuses</option>
              ${Object.entries(STATUS_LABELS)
                .map(
                  ([value, label]) =>
                    `<option value="${value}" ${filters.status === value ? "selected" : ""}>${label}</option>`,
                )
                .join("")}
            </select>
          </div>
          <div class="field">
            <label for="filter-supplier">Supplier</label>
            <select class="select" id="filter-supplier">
              <option value="">All suppliers</option>
              ${suppliers.items
                .map(
                  (supplier) =>
                    `<option value="${supplier.id}" ${String(filters.supplier_id) === String(supplier.id) ? "selected" : ""}>${escapeHtml(supplier.name)}</option>`,
                )
                .join("")}
            </select>
          </div>
          <div class="field">
            <label for="filter-per-page">Show</label>
            <select class="select" id="filter-per-page">
              ${[10, 25, 50]
                .map(
                  (size) =>
                    `<option value="${size}" ${Number(filters.per_page) === size ? "selected" : ""}>${size} rows</option>`,
                )
                .join("")}
            </select>
          </div>
          <div class="field">
            <span class="field-label" aria-hidden="true">&nbsp;</span>
            <button class="btn btn-ghost" type="button" id="clear-filters">Clear</button>
          </div>
        </div>

        <div id="purchase-results" aria-live="polite"></div>
      </section>
    </div>`;

  const results = view.querySelector("#purchase-results");
  const exportLink = view.querySelector("#export-csv");
  const searchInput = view.querySelector("#filter-search");
  const fromInput = view.querySelector("#filter-from");
  const toInput = view.querySelector("#filter-to");
  const statusInput = view.querySelector("#filter-status");
  const supplierInput = view.querySelector("#filter-supplier");
  const perPageInput = view.querySelector("#filter-per-page");

  let requestId = 0;
  let lastPage = Number(filters.page) || 1;

  function currentQuery(includePage = true) {
    return {
      search: state.purchaseFilters.search,
      category: categoryParam(),
      status: state.purchaseFilters.status,
      from: state.purchaseFilters.from,
      to: state.purchaseFilters.to,
      supplier_id: state.purchaseFilters.supplier_id,
      page: includePage ? state.purchaseFilters.page : undefined,
      per_page: includePage ? state.purchaseFilters.per_page : undefined,
    };
  }

  function updateExportLink() {
    if (exportLink) exportLink.href = api.purchaseExportUrl(currentQuery(false));
  }

  function readInputs() {
    state.purchaseFilters.search = searchInput.value.trim();
    state.purchaseFilters.status = statusInput.value;
    state.purchaseFilters.from = fromInput.value;
    state.purchaseFilters.to = toInput.value;
    state.purchaseFilters.supplier_id = supplierInput.value;
    state.purchaseFilters.per_page = Number(perPageInput.value) || 10;
    state.purchaseFilters.page = 1;
  }

  function activeTags() {
    const tags = [];
    if (state.category !== "all") {
      tags.push({ key: "category", label: `Section: ${categoryLabel()}`, value: state.category });
    }
    if (state.purchaseFilters.search) {
      tags.push({ key: "search", label: `“${state.purchaseFilters.search}”` });
    }
    if (state.purchaseFilters.from) {
      tags.push({ key: "from", label: `From ${formatDate(state.purchaseFilters.from)}` });
    }
    if (state.purchaseFilters.to) {
      tags.push({ key: "to", label: `To ${formatDate(state.purchaseFilters.to)}` });
    }
    if (state.purchaseFilters.status) {
      tags.push({ key: "status", label: STATUS_LABELS[state.purchaseFilters.status] });
    }
    if (state.purchaseFilters.supplier_id) {
      tags.push({
        key: "supplier_id",
        label: supplierMap.get(String(state.purchaseFilters.supplier_id)) || "Supplier",
      });
    }
    return tags;
  }

  function renderResults(data) {
    const start = data.total === 0 ? 0 : (data.page - 1) * data.per_page + 1;
    const end = Math.min(data.page * data.per_page, data.total);
    const tags = activeTags();
    const filtered = tags.length > 0;

    results.innerHTML = `
      <div class="list-summary">
        <span>Showing <strong>${count(start)}–${count(end)}</strong> of <strong>${count(data.total)}</strong> ${data.total === 1 ? "record" : "records"}</span>
        <span class="sum-total" title="The sum of every record matching the filters, including rejected records">Filtered total (all statuses): <strong>${money(data.filtered_total_cents)}</strong></span>
      </div>
      ${
        filtered
          ? `<div class="active-filters">
              <span>Filters:</span>
              ${tags
                .map(
                  (tag) => `<span class="filter-tag">${escapeHtml(tag.label)}<button type="button" data-clear="${tag.key}" aria-label="Remove filter ${escapeHtml(tag.label)}">×</button></span>`,
                )
                .join("")}
              <button class="link-btn" type="button" data-clear-all>Clear all</button>
            </div>`
          : ""
      }
      ${data.items.length ? purchaseTable(data.items) : emptyResult(filtered, canWrite)}
      ${data.items.length ? pagination({ page: data.page, pages: data.pages }) : ""}
    `;
    updateExportLink();
    lastPage = data.page;
  }

  function showFilterError(message) {
    results.classList.remove("is-loading");
    results.removeAttribute("aria-busy");
    results.innerHTML = `
      <div class="filter-error">
        <span class="empty-icon">${icon("alert")}</span>
        <div>
          <h3>Those dates do not work</h3>
          <p>${escapeHtml(message)}</p>
        </div>
        <button class="btn btn-ghost btn-sm" type="button" data-focus-dates>Adjust dates</button>
      </div>`;
  }

  async function load({ focusResults = false } = {}) {
    // Invalidate any in-flight request, even when this attempt fails validation,
    // so an older response cannot replace the visible error.
    const id = ++requestId;
    if (state.purchaseFilters.from && state.purchaseFilters.to && state.purchaseFilters.from > state.purchaseFilters.to) {
      showFilterError("The “From” date must be on or before the “To” date.");
      return;
    }
    results.classList.add("is-loading");
    results.setAttribute("aria-busy", "true");
    try {
      const data = await api.listPurchases(currentQuery());
      if (id !== requestId) return;
      renderResults(data);
      if (focusResults) results.scrollIntoView({ block: "nearest", behavior: "smooth" });
    } catch (error) {
      if (id !== requestId) return;
      results.innerHTML = `
        <div class="error-panel" role="alert">
          <span class="empty-icon">${icon("alert")}</span>
          <h2>Could not load purchases</h2>
          <p>${escapeHtml(error.message)}</p>
          <button class="btn btn-primary" type="button" data-retry-list>Try again</button>
        </div>`;
    } finally {
      if (id === requestId) {
        results.classList.remove("is-loading");
        results.removeAttribute("aria-busy");
      }
    }
  }

  const debouncedSearch = debounce(() => {
    state.purchaseFilters.search = searchInput.value.trim();
    state.purchaseFilters.page = 1;
    load();
  }, 320);

  searchInput.addEventListener("input", debouncedSearch);
  searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      state.purchaseFilters.search = searchInput.value.trim();
      state.purchaseFilters.page = 1;
      load();
    }
  });

  for (const input of [fromInput, toInput, statusInput, supplierInput, perPageInput]) {
    input.addEventListener("change", () => {
      readInputs();
      load();
    });
  }

  view.querySelector("#clear-filters").addEventListener("click", () => {
    resetFilters();
  });

  function resetFilters() {
    Object.assign(state.purchaseFilters, {
      search: "",
      status: "",
      from: "",
      to: "",
      supplier_id: "",
      page: 1,
      per_page: Number(perPageInput.value) || 10,
    });
    searchInput.value = "";
    statusInput.value = "";
    fromInput.value = "";
    toInput.value = "";
    supplierInput.value = "";
    if (state.category !== "all") {
      document.querySelector('[data-category="all"]')?.click();
      return;
    }
    load();
  }

  results.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const pageButton = target.closest("[data-page]");
    if (pageButton && !pageButton.disabled) {
      state.purchaseFilters.page = Number(pageButton.dataset.page);
      load({ focusResults: true });
      return;
    }
    const clear = target.closest("[data-clear]");
    if (clear) {
      const key = clear.dataset.clear;
      if (key === "category") {
        document.querySelector('[data-category="all"]')?.click();
        return;
      }
      state.purchaseFilters[key] = "";
      state.purchaseFilters.page = 1;
      if (key === "search") searchInput.value = "";
      if (key === "status") statusInput.value = "";
      if (key === "from") fromInput.value = "";
      if (key === "to") toInput.value = "";
      if (key === "supplier_id") supplierInput.value = "";
      load();
      return;
    }
    if (target.closest("[data-clear-all]")) {
      resetFilters();
      return;
    }
    if (target.closest("[data-retry-list]")) {
      load();
      return;
    }
    if (target.closest("[data-focus-dates]")) {
      fromInput.focus();
    }
  });

  updateExportLink();
  results.innerHTML = `
    <div class="loading-panel">
      <span class="spinner" aria-hidden="true"></span>
      <p>Loading purchase records…</p>
    </div>`;
  await load();
}

function purchaseTable(items) {
  return `
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th>Reference</th>
            <th>Supplier &amp; items</th>
            <th>Section</th>
            <th class="hide-sm">Payment</th>
            <th>Status</th>
            <th class="num">Amount (KSh)</th>
            <th></th>
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
                  <td>
                    <div class="cell-stack">
                      <span class="primary">${escapeHtml(item.supplier_name)}</span>
                      <span class="secondary">${escapeHtml(item.items_summary)}</span>
                    </div>
                  </td>
                  <td>${sectionBadge(item.category, item.category === "jss" ? "JSS" : "Primary")}</td>
                  <td class="hide-sm">${escapeHtml(item.payment_method_label)}</td>
                  <td>${statusBadge(item.status, item.status_label)}</td>
                  <td class="num amount"><strong>${amount(item.total_cents)}</strong></td>
                  <td class="num"><a class="btn btn-subtle btn-sm" href="#/purchases/${item.id}">View</a></td>
                </tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </div>`;
}

function emptyResult(filtered, canWrite) {
  if (!filtered) {
    return emptyState({
      title: "No purchases yet",
      message: canWrite
        ? "The register is empty for this section. Record a purchase or change the section selector."
        : "The register is empty for this section in the current demonstration dataset.",
      iconName: "receipt",
      href: canWrite ? "#/purchases/new" : "",
      action: canWrite ? "Record a purchase" : "",
    });
  }
  return emptyState({
    title: "No purchases match",
    message: "Try a different search term or date range, or clear the filters to see the full register.",
    iconName: "search",
  });
}
