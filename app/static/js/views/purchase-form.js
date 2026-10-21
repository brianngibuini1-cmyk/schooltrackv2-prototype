/** Purchase entry: line items, live preview totals and server validation. */

import { api } from "../api.js";
import { escapeHtml, money } from "../format.js";
import { state, writesEnabled } from "../store.js";
import {
  applyFieldErrors,
  clearFieldErrors,
  icon,
  readOnlyPanel,
  setButtonBusy,
  toast,
} from "../ui.js";
import { openSupplierDialog } from "./supplier-form.js";

const MAX_ITEMS = 50;
const MAX_UNIT_COST = 10_000_000;

export async function renderPurchaseForm(view, params, context) {
  const meta = state.meta;
  if (!writesEnabled()) {
    view.innerHTML = `
      <div class="view-inner">
        <div class="page-intro">
          <div>
            <h2>New purchase voucher</h2>
            <p class="lede">Purchase entry is not available in this public demonstration.</p>
          </div>
          <div class="page-intro-actions">
            <a class="btn btn-ghost" href="#/purchases">${icon("arrowLeft")}<span>Back to register</span></a>
          </div>
        </div>
        ${readOnlyPanel("Creating and approving purchase records is disabled in this read-only demo.")}
      </div>`;
    return;
  }
  const suppliers = await api.listSuppliers("");
  if (context && context.isCurrent && !context.isCurrent()) return;

  const initialCategory = state.category === "all" ? "primary" : state.category;
  const purchaseStatuses = meta.statuses.filter((status) => status.value !== "rejected");

  view.innerHTML = `
    <div class="view-inner">
      <div class="page-intro">
        <div>
          <h2>New purchase voucher</h2>
          <p class="lede">
            Capture the paper voucher once, with every line item. SchoolTrack calculates the totals,
            assigns the reference and stores the record in the configured database.
          </p>
        </div>
        <div class="page-intro-actions">
          <a class="btn btn-ghost" href="#/purchases">${icon("arrowLeft")}<span>Back to register</span></a>
        </div>
      </div>

      <form id="purchase-form" class="card form-card" novalidate>
        <div id="purchase-form-alert"></div>

        <section class="form-section">
          <div class="form-section-head">
            <div>
              <h3>Record details</h3>
              <p>Who supplied the goods, when, and for which school section.</p>
            </div>
            <div class="reference-preview" aria-live="polite">
              <div>
                <span class="ref-label">Next reference</span>
                <div class="ref-value" id="reference-preview">…</div>
              </div>
              <span class="ref-hint">Preview only — the final<br>reference is issued on save.</span>
            </div>
          </div>

          <div class="form-grid">
            <div class="field">
              <label for="purchase-date">Purchase date</label>
              <input class="input" id="purchase-date" data-field="purchase_date" type="date"
                value="${escapeHtml(meta.today)}" max="${escapeHtml(meta.today)}" required>
            </div>
            <div class="field">
              <label for="purchase-section">School section</label>
              <select class="select" id="purchase-section" data-field="category">
                ${meta.categories
                  .map(
                    (category) =>
                      `<option value="${category.value}" ${category.value === initialCategory ? "selected" : ""}>${escapeHtml(category.label)}</option>`,
                  )
                  .join("")}
              </select>
            </div>
            <div class="field">
              <label for="payment-method">Payment method</label>
              <select class="select" id="payment-method" data-field="payment_method">
                ${meta.payment_methods
                  .map(
                    (method) =>
                      `<option value="${method.value}" ${method.value === "mpesa" ? "selected" : ""}>${escapeHtml(method.label)}</option>`,
                  )
                  .join("")}
              </select>
            </div>
            <div class="field">
              <label for="purchase-status">Approval status</label>
              <select class="select" id="purchase-status" data-field="status">
                ${purchaseStatuses
                  .map(
                    (status) =>
                      `<option value="${status.value}" ${status.value === "pending" ? "selected" : ""}>${escapeHtml(status.label)}</option>`,
                  )
                  .join("")}
              </select>
            </div>

            <div class="field span-2">
              <label for="supplier-select">Supplier</label>
              <div class="supplier-select-row">
                <select class="select" id="supplier-select" data-field="supplier_id" required>
                  <option value="">Select the supplier…</option>
                  ${suppliers.items
                    .map(
                      (supplier) =>
                        `<option value="${supplier.id}" ${suppliers.items.length === 1 ? "selected" : ""}>${escapeHtml(supplier.name)}</option>`,
                    )
                    .join("")}
                </select>
                <button class="btn btn-ghost" type="button" id="add-supplier">${icon("plus")}<span>New supplier</span></button>
              </div>
              <span class="hint">The supplier must be registered before the purchase can be saved.</span>
            </div>

            <div class="field span-2">
              <label for="invoice-number">Invoice / receipt number <span class="optional">optional</span></label>
              <input class="input" id="invoice-number" data-field="invoice_number" maxlength="60"
                placeholder="e.g. INV-1042" autocomplete="off">
            </div>
          </div>
        </section>

        <section class="form-section">
          <div class="form-section-head">
            <div>
              <h3>Line items</h3>
              <p>Add each item separately. Quantities, unit costs and totals are checked again by the server.</p>
            </div>
            <button class="btn btn-ghost btn-sm" type="button" id="add-item">${icon("plus")}<span>Add line</span></button>
          </div>

          <table class="items-table" aria-label="Purchase line items">
            <thead>
              <tr>
                <th scope="col">Description</th>
                <th scope="col" class="num col-qty">Quantity</th>
                <th scope="col" class="num col-cost">Unit cost (KSh)</th>
                <th scope="col" class="num col-total">Line total</th>
                <th scope="col" class="col-remove"><span class="sr-only">Remove</span></th>
              </tr>
            </thead>
            <tbody id="item-body">
              ${itemRow(0)}
            </tbody>
          </table>

          <div class="items-foot">
            <p class="demo-note">
              ${icon("info")}
              <span>No taxes or adjustments are applied in this prototype. Totals are recalculated on the server before saving.</span>
            </p>
            <div class="totals-box" aria-live="polite">
              <div class="totals-row"><span>Line items</span><strong id="total-lines">1</strong></div>
              <div class="totals-row"><span>Total quantity</span><strong id="total-quantity">1</strong></div>
              <div class="totals-row grand"><span>Total</span><strong id="total-amount">KSh 0.00</strong></div>
            </div>
          </div>
        </section>

        <section class="form-section">
          <div class="field mb-0">
            <label for="purchase-notes">Notes <span class="optional">optional</span></label>
            <textarea class="textarea" id="purchase-notes" data-field="notes" maxlength="500"
              placeholder="Purpose, budget line, or approval comments."></textarea>
          </div>
        </section>

        <div class="form-actions">
          <p class="form-actions-note">The record is saved to the configured SchoolTrack database.</p>
          <a class="btn btn-ghost" href="#/purchases">Cancel</a>
          <button class="btn btn-primary" type="submit" id="save-purchase">${icon("check")}<span>Save purchase</span></button>
        </div>
      </form>
    </div>`;

  const form = view.querySelector("#purchase-form");
  const alertBox = view.querySelector("#purchase-form-alert");
  const dateInput = view.querySelector("#purchase-date");
  const sectionInput = view.querySelector("#purchase-section");
  const supplierInput = view.querySelector("#supplier-select");
  const paymentInput = view.querySelector("#payment-method");
  const statusInput = view.querySelector("#purchase-status");
  const invoiceInput = view.querySelector("#invoice-number");
  const notesInput = view.querySelector("#purchase-notes");
  const itemBody = view.querySelector("#item-body");
  const addItemButton = view.querySelector("#add-item");
  const saveButton = view.querySelector("#save-purchase");
  const referencePreview = view.querySelector("#reference-preview");
  const totalLines = view.querySelector("#total-lines");
  const totalQuantity = view.querySelector("#total-quantity");
  const totalAmount = view.querySelector("#total-amount");

  let referenceRequest = 0;

  function rowElements() {
    return Array.from(itemBody.querySelectorAll("tr.item-row"));
  }

  function renumberRows() {
    const rows = rowElements();
    rows.forEach((row, index) => {
      row.dataset.index = String(index);
      row.querySelectorAll("[data-item]").forEach((input) => {
        input.dataset.field = `items.${index}.${input.dataset.item}`;
      });
    });
    const removeButtons = rowElements().map((row) => row.querySelector("[data-remove]"));
    removeButtons.forEach((button) => {
      if (button) button.disabled = rows.length === 1;
    });
    addItemButton.disabled = rows.length >= MAX_ITEMS;
  }

  function recalc() {
    let lines = 0;
    let quantityTotal = 0;
    let grandTotal = 0;
    for (const row of rowElements()) {
      const quantity = Number.parseInt(row.querySelector('[data-item="quantity"]').value, 10) || 0;
      const unitCost = moneyToCents(row.querySelector('[data-item="unit_cost"]').value);
      const total = Math.max(0, quantity) * unitCost;
      lines += 1;
      quantityTotal += Math.max(0, quantity);
      grandTotal += total;
      const cell = row.querySelector(".line-total");
      if (cell) cell.textContent = money(total);
    }
    totalLines.textContent = String(lines);
    totalQuantity.textContent = quantityTotal.toLocaleString("en-KE");
    totalAmount.textContent = money(grandTotal);
  }

  async function refreshReference() {
    const request = ++referenceRequest;
    const date = dateInput.value;
    if (!date) {
      referencePreview.textContent = "Assigned on save";
      return;
    }
    referencePreview.textContent = "…";
    try {
      const data = await api.nextReference(date);
      if (request === referenceRequest) referencePreview.textContent = data.preview;
    } catch {
      if (request === referenceRequest) referencePreview.textContent = "Assigned on save";
    }
  }

  function collectPayload() {
    const items = rowElements().map((row) => ({
      description: row.querySelector('[data-item="description"]').value.trim(),
      quantity: Number(row.querySelector('[data-item="quantity"]').value),
      unit_cost: row.querySelector('[data-item="unit_cost"]').value.trim(),
    }));
    return {
      purchase_date: dateInput.value,
      supplier_id: supplierInput.value ? Number(supplierInput.value) : null,
      category: sectionInput.value,
      payment_method: paymentInput.value,
      invoice_number: invoiceInput.value.trim(),
      status: statusInput.value,
      notes: notesInput.value.trim(),
      items,
    };
  }

  function validate(payload) {
    const errors = {};
    if (!payload.purchase_date) {
      errors.purchase_date = "Choose the purchase date.";
    } else if (payload.purchase_date > meta.today) {
      errors.purchase_date = "A purchase cannot be dated in the future.";
    } else if (payload.purchase_date < "2000-01-01") {
      errors.purchase_date = "Enter a date on or after 1 January 2000.";
    }
    if (!payload.supplier_id) {
      errors.supplier_id = "Choose a supplier, or register a new one.";
    }
    if (!payload.items.length) {
      errors.items = "Add at least one line item.";
    }
    payload.items.forEach((item, index) => {
      if (item.description.length < 2) {
        errors[`items.${index}.description`] = "Describe the item in at least two characters.";
      } else if (item.description.length > 160) {
        errors[`items.${index}.description`] = "Keep the description to 160 characters or fewer.";
      }
      if (!Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > 100_000) {
        errors[`items.${index}.quantity`] = "Quantity must be a whole number from 1 to 100,000.";
      }
      const cost = Number(item.unit_cost);
      if (!item.unit_cost || !Number.isFinite(cost) || cost <= 0) {
        errors[`items.${index}.unit_cost`] = "Enter a unit cost greater than zero.";
      } else if (cost > MAX_UNIT_COST) {
        errors[`items.${index}.unit_cost`] = `Unit cost cannot exceed ${money(MAX_UNIT_COST * 100)}.`;
      } else if (!/^\d+(\.\d{1,2})?$/.test(item.unit_cost)) {
        errors[`items.${index}.unit_cost`] = "Use at most two decimal places.";
      }
    });
    return errors;
  }

  function showFormError(message, fields = {}) {
    clearFieldErrors(form);
    const unmapped = Object.entries(fields).filter(
      ([key]) => !form.querySelector(`[data-field="${key}"]`),
    );
    alertBox.innerHTML = `
      <div class="form-error" role="alert">
        ${icon("alert")}
        <div>
          <strong>We could not save this purchase</strong>
          <p>${escapeHtml(message)}</p>
          ${
            unmapped.length
              ? `<ul>${unmapped.map(([, value]) => `<li>${escapeHtml(value)}</li>`).join("")}</ul>`
              : ""
          }
        </div>
      </div>`;
    applyFieldErrors(form, fields);
    alertBox.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  itemBody.addEventListener("input", recalc);
  itemBody.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const removeButton = target && target.closest("[data-remove]");
    if (!removeButton || removeButton.disabled) return;
    const row = removeButton.closest("tr");
    if (rowElements().length <= 1) return;
    row.remove();
    renumberRows();
    recalc();
  });

  addItemButton.addEventListener("click", () => {
    if (rowElements().length >= MAX_ITEMS) return;
    itemBody.insertAdjacentHTML("beforeend", itemRow(rowElements().length));
    renumberRows();
    recalc();
    const rows = rowElements();
    rows[rows.length - 1].querySelector('[data-item="description"]').focus();
  });

  dateInput.addEventListener("change", refreshReference);
  sectionInput.addEventListener("change", () => {
    sectionInput.classList.remove("is-invalid");
  });

  view.querySelector("#add-supplier").addEventListener("click", () => {
    openSupplierDialog({
      onCreated: (supplier) => {
        const option = document.createElement("option");
        option.value = String(supplier.id);
        option.textContent = supplier.name;
        supplierInput.appendChild(option);
        supplierInput.value = String(supplier.id);
        supplierInput.classList.remove("is-invalid");
      },
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saveButton.disabled) return;
    alertBox.innerHTML = "";
    clearFieldErrors(form);
    const payload = collectPayload();
    const errors = validate(payload);
    if (Object.keys(errors).length) {
      showFormError("Some details need attention. Review the highlighted fields.", errors);
      return;
    }

    setButtonBusy(saveButton, true, "Saving purchase…");
    try {
      const created = await api.createPurchase(payload);
      toast(`${created.reference} recorded for ${money(created.total_cents)}.`, {
        title: "Purchase saved",
        type: "success",
      });
      window.location.hash = `#/purchases/${created.id}`;
    } catch (error) {
      setButtonBusy(saveButton, false);
      showFormError(error.message || "The purchase could not be saved.", error.fields || {});
    }
  });

  form.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  const onCategoryChange = (event) => {
    if (event.detail.category !== "all") sectionInput.value = event.detail.category;
  };
  document.addEventListener("schooltrack:categorychange", onCategoryChange);
  window.addEventListener(
    "hashchange",
    () => document.removeEventListener("schooltrack:categorychange", onCategoryChange),
    { once: true },
  );

  renumberRows();
  recalc();
  refreshReference();
}

function itemRow(index) {
  return `
    <tr class="item-row" data-index="${index}">
      <td class="col-description" data-label="Description">
        <input class="input" data-item="description" data-field="items.${index}.description"
          maxlength="160" placeholder="e.g. Exercise books, 48 pages" aria-label="Item description">
      </td>
      <td class="col-qty" data-label="Quantity">
        <input class="input" data-item="quantity" data-field="items.${index}.quantity"
          type="number" inputmode="numeric" min="1" max="100000" step="1" value="1" aria-label="Quantity">
      </td>
      <td class="col-cost" data-label="Unit cost (KSh)">
        <input class="input" data-item="unit_cost" data-field="items.${index}.unit_cost"
          type="number" inputmode="decimal" min="0.01" max="${MAX_UNIT_COST}" step="0.01"
          placeholder="0.00" aria-label="Unit cost in shillings">
      </td>
      <td class="col-total" data-label="Line total">
        <span class="line-total">KSh 0.00</span>
      </td>
      <td class="col-remove">
        <button class="remove-row" type="button" data-remove aria-label="Remove this line item">
          ${icon("close")}
        </button>
      </td>
    </tr>`;
}

function moneyToCents(raw) {
  const value = Number.parseFloat(String(raw).trim());
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.round(value * 100);
}
