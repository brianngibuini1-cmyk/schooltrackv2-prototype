/** Small amount of cross-view UI state (filters, section selection). */

import { todayISO } from "./format.js";

const CATEGORY_KEY = "schooltrack.category";
const VALID_CATEGORIES = ["all", "primary", "jss"];

function loadCategory() {
  try {
    const saved = window.localStorage.getItem(CATEGORY_KEY);
    return VALID_CATEGORIES.includes(saved) ? saved : "all";
  } catch {
    return "all";
  }
}

export const state = {
  meta: null,
  category: loadCategory(),
  purchaseFilters: {
    search: "",
    status: "",
    from: "",
    to: "",
    supplier_id: "",
    page: 1,
    per_page: 10,
  },
  supplierSearch: "",
  report: {
    preset: "ytd",
    from: "",
    to: "",
    status: "approved",
  },
};

export function saveCategory(value) {
  state.category = VALID_CATEGORIES.includes(value) ? value : "all";
  try {
    window.localStorage.setItem(CATEGORY_KEY, state.category);
  } catch {
    // Storage can be unavailable in privacy modes; the in-memory value still works.
  }
}

export function categoryParam() {
  return state.category === "all" ? undefined : state.category;
}

export function writesEnabled() {
  return !state.meta || state.meta.writes_enabled !== false;
}

export function demoMode() {
  return Boolean(state.meta && state.meta.demo_mode);
}

export function categoryLabel(value = state.category) {
  if (value === "primary") return "Primary section";
  if (value === "jss") return "Junior Secondary (JSS)";
  return "All sections";
}

export function today() {
  return (state.meta && state.meta.today) || todayISO();
}

export function addDays(iso, days) {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + days);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function monthStart(iso, offsetMonths = 0) {
  const [year, month] = iso.split("-").map(Number);
  const date = new Date(year, month - 1 + offsetMonths, 1, 12);
  const resultMonth = String(date.getMonth() + 1).padStart(2, "0");
  return `${date.getFullYear()}-${resultMonth}-01`;
}

/** Date range for a report preset, based on the server's date. */
export function reportRange(preset, from = "", to = "") {
  const end = today();
  switch (preset) {
    case "this-month":
      return { from: monthStart(end), to: end };
    case "last-30":
      return { from: addDays(end, -29), to: end };
    case "last-12":
      return { from: monthStart(end, -11), to: end };
    case "custom":
      return { from: from || monthStart(end), to: to || end };
    case "ytd":
    default:
      return { from: `${end.slice(0, 4)}-01-01`, to: end };
  }
}
