/** Thin client for the SchoolTrack JSON API. */

import { buildQuery } from "./format.js";

export class ApiError extends Error {
  constructor(message, { status = 0, fields = {} } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fields = fields || {};
  }
}

async function request(path, { method = "GET", body } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: body === undefined ? { Accept: "application/json" } : {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "SchoolTrack could not reach the local server. Check that it is still running and try again.",
      { status: 0 },
    );
  }

  if (response.ok) {
    if (response.status === 204) return null;
    return response.json();
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // The server returned a non-JSON error body; fall through to a generic message.
  }
  const error = payload && payload.error ? payload.error : {};
  const fallback = response.status === 404
    ? "The requested record could not be found."
    : "The request could not be completed. Please review the details and try again.";
  throw new ApiError(error.message || fallback, {
    status: response.status,
    fields: error.fields || {},
  });
}

function purchaseQuery(filters = {}) {
  return buildQuery({
    search: filters.search,
    category: filters.category,
    status: filters.status,
    from: filters.from,
    to: filters.to,
    supplier_id: filters.supplier_id,
    page: filters.page,
    per_page: filters.per_page,
  });
}

export const api = {
  meta() {
    return request("/api/meta");
  },

  dashboard(category) {
    return request(`/api/dashboard${buildQuery({ category })}`);
  },

  listPurchases(filters = {}) {
    return request(`/api/purchases${purchaseQuery(filters)}`);
  },

  getPurchase(id) {
    return request(`/api/purchases/${encodeURIComponent(id)}`);
  },

  createPurchase(payload) {
    return request("/api/purchases", { method: "POST", body: payload });
  },

  updatePurchaseStatus(id, status) {
    return request(`/api/purchases/${encodeURIComponent(id)}/status`, {
      method: "PATCH",
      body: { status },
    });
  },

  nextReference(purchaseDate) {
    return request(`/api/purchases/next-reference${buildQuery({ purchase_date: purchaseDate })}`);
  },

  purchaseExportUrl(filters = {}) {
    return `/api/purchases/export.csv${purchaseQuery(filters)}`;
  },

  listSuppliers(search = "") {
    return request(`/api/suppliers${buildQuery({ search })}`);
  },

  getSupplier(id) {
    return request(`/api/suppliers/${encodeURIComponent(id)}`);
  },

  createSupplier(payload) {
    return request("/api/suppliers", { method: "POST", body: payload });
  },

  reports(filters = {}) {
    return request(`/api/reports${buildQuery({
      from: filters.from,
      to: filters.to,
      category: filters.category,
      status: filters.status,
    })}`);
  },
};
