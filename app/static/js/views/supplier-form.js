/** Register-supplier dialog shared by the supplier directory and purchase form. */

import { api } from "../api.js";
import {
  applyFieldErrors,
  clearFieldErrors,
  icon,
  openModal,
  setButtonBusy,
  toast,
} from "../ui.js";

export function openSupplierDialog({ onCreated } = {}) {
  const modal = openModal({
    title: "Register a supplier",
    subtitle: "Suppliers are fictional records in this demonstration.",
    body: `
      <form id="supplier-form" novalidate>
        <div id="supplier-form-alert"></div>
        <div class="field">
          <label for="supplier-name">Supplier name <span class="optional">required</span></label>
          <input class="input" id="supplier-name" name="name" data-field="name" maxlength="120"
            placeholder="e.g. Baraka Stationers &amp; Printers" autofocus autocomplete="organization">
        </div>
        <div class="form-grid">
          <div class="field span-2">
            <label for="supplier-contact">Contact person <span class="optional">optional</span></label>
            <input class="input" id="supplier-contact" name="contact_person" data-field="contact_person"
              maxlength="120" autocomplete="name">
          </div>
          <div class="field span-2">
            <label for="supplier-phone">Phone <span class="optional">optional</span></label>
            <input class="input" id="supplier-phone" name="phone" data-field="phone" maxlength="40"
              placeholder="0712 345 678" autocomplete="tel">
          </div>
          <div class="field span-2">
            <label for="supplier-email">Email <span class="optional">optional</span></label>
            <input class="input" id="supplier-email" name="email" data-field="email" type="email"
              maxlength="160" autocomplete="email">
          </div>
          <div class="field span-2">
            <label for="supplier-address">Address <span class="optional">optional</span></label>
            <input class="input" id="supplier-address" name="address" data-field="address" maxlength="200"
              autocomplete="street-address">
          </div>
          <div class="field span-4">
            <label for="supplier-notes">Notes <span class="optional">optional</span></label>
            <textarea class="textarea" id="supplier-notes" name="notes" data-field="notes" maxlength="500"
              placeholder="Payment terms, regular contact, or anything useful for the school office."></textarea>
          </div>
        </div>
      </form>`,
    footer: `
      <span class="modal-foot-note">All fields are validated by the server.</span>
      <button class="btn btn-ghost" type="button" data-supplier-cancel>Cancel</button>
      <button class="btn btn-primary" type="submit" form="supplier-form" data-supplier-save>Register supplier</button>`,
  });

  const { overlay, close } = modal;
  const form = overlay.querySelector("#supplier-form");
  const saveButton = overlay.querySelector("[data-supplier-save]");
  const alertBox = overlay.querySelector("#supplier-form-alert");

  overlay.querySelector("[data-supplier-cancel]").addEventListener("click", close);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (saveButton.disabled) return;
    clearFieldErrors(form);
    alertBox.innerHTML = "";

    const data = Object.fromEntries(new FormData(form).entries());
    const errors = {};
    if (!String(data.name || "").trim()) errors.name = "Enter the supplier name.";
    else if (String(data.name).trim().length < 2) errors.name = "Use at least two characters.";

    if (Object.keys(errors).length) {
      applyFieldErrors(form, errors);
      alertBox.innerHTML = errorAlert("Check the supplier name and try again.");
      return;
    }

    setButtonBusy(saveButton, true, "Registering…");
    try {
      const supplier = await api.createSupplier({
        name: String(data.name).trim(),
        contact_person: String(data.contact_person || "").trim(),
        phone: String(data.phone || "").trim(),
        email: String(data.email || "").trim(),
        address: String(data.address || "").trim(),
        notes: String(data.notes || "").trim(),
      });
      toast(`${supplier.name} has been added to the supplier directory.`, {
        title: "Supplier registered",
      });
      close();
      if (typeof onCreated === "function") onCreated(supplier);
    } catch (error) {
      setButtonBusy(saveButton, false);
      applyFieldErrors(form, error.fields || {});
      alertBox.innerHTML = errorAlert(error.message);
    }
  });
}

function errorAlert(message) {
  return `
    <div class="form-error" role="alert">
      ${icon("alert")}
      <div><strong>Could not register the supplier</strong>${escapeMessage(message)}</div>
    </div>`;
}

function escapeMessage(message) {
  return String(message || "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character]));
}
