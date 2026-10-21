/** Application shell: routing, section selector and startup. */

import { api } from "./api.js";
import { categoryLabel, saveCategory, state } from "./store.js";
import { destroyCharts, errorPanel, icon } from "./ui.js";
import { renderDashboard } from "./views/dashboard.js";
import { renderPurchaseDetail } from "./views/purchase-detail.js";
import { renderPurchaseForm } from "./views/purchase-form.js";
import { renderPurchases } from "./views/purchases.js";
import { renderReports } from "./views/reports.js";
import { renderSupplierDetail, renderSuppliers } from "./views/suppliers.js";

const ROUTES = [
  {
    pattern: /^\/dashboard\/?$/,
    key: "dashboard",
    nav: "dashboard",
    title: "Dashboard",
    kicker: "Financial overview",
    render: renderDashboard,
  },
  {
    pattern: /^\/purchases\/?$/,
    key: "purchases",
    nav: "purchases",
    title: "Purchase register",
    kicker: "Procurement records",
    render: renderPurchases,
  },
  {
    pattern: /^\/purchases\/new\/?$/,
    key: "new-purchase",
    nav: "new-purchase",
    title: "Record a purchase",
    kicker: "New record",
    render: renderPurchaseForm,
  },
  {
    pattern: /^\/purchases\/(\d+)\/?$/,
    key: "purchase-detail",
    nav: "purchases",
    title: "Purchase details",
    kicker: "Purchase voucher",
    render: renderPurchaseDetail,
  },
  {
    pattern: /^\/suppliers\/?$/,
    key: "suppliers",
    nav: "suppliers",
    title: "Suppliers",
    kicker: "Supplier directory",
    render: renderSuppliers,
  },
  {
    pattern: /^\/suppliers\/(\d+)\/?$/,
    key: "supplier-detail",
    nav: "suppliers",
    title: "Supplier history",
    kicker: "Supplier record",
    render: renderSupplierDetail,
  },
  {
    pattern: /^\/reports\/?$/,
    key: "reports",
    nav: "reports",
    title: "Expenditure reports",
    kicker: "Analysis",
    render: renderReports,
  },
];

const view = document.getElementById("view");
const titleElement = document.getElementById("page-title");
const eyebrowElement = document.getElementById("page-eyebrow");
const shell = document.getElementById("app-shell");
const sidebarBackdrop = document.getElementById("sidebar-backdrop");
const menuButton = document.getElementById("menu-btn");
const categoryButtons = Array.from(document.querySelectorAll("[data-category]"));

let currentRoute = null;
let renderToken = 0;
let metaLoaded = false;

/* -------------------------------------------------------------------------- */
/* Section selector                                                           */
/* -------------------------------------------------------------------------- */

function paintCategoryButtons() {
  for (const button of categoryButtons) {
    button.setAttribute("aria-pressed", String(button.dataset.category === state.category));
  }
}

function setCategory(value) {
  if (state.category === value) return;
  saveCategory(value);
  state.purchaseFilters.page = 1;
  paintCategoryButtons();
  document.dispatchEvent(new CustomEvent("schooltrack:categorychange", {
    detail: { category: state.category, label: categoryLabel() },
  }));
  // The purchase form keeps its unsaved input; its view reacts to the event.
  if (currentRoute && currentRoute.key !== "new-purchase") renderRoute();
}

for (const button of categoryButtons) {
  button.addEventListener("click", () => setCategory(button.dataset.category));
}

/* -------------------------------------------------------------------------- */
/* Mobile navigation                                                          */
/* -------------------------------------------------------------------------- */

function setMenu(open) {
  shell.classList.toggle("sidebar-open", open);
  sidebarBackdrop.hidden = !open;
  menuButton.setAttribute("aria-expanded", String(open));
  menuButton.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
}

menuButton.addEventListener("click", () => setMenu(!shell.classList.contains("sidebar-open")));
sidebarBackdrop.addEventListener("click", () => setMenu(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMenu(false);
});
window.addEventListener("resize", () => {
  if (window.innerWidth > 1020) setMenu(false);
});
document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", () => setMenu(false));
});

/* -------------------------------------------------------------------------- */
/* Routing                                                                    */
/* -------------------------------------------------------------------------- */

function parseHash() {
  const raw = window.location.hash.replace(/^#/, "");
  const path = raw.split("?")[0] || "/dashboard";
  return path.startsWith("/") ? path : `/${path}`;
}

function matchRoute(path) {
  for (const route of ROUTES) {
    const match = route.pattern.exec(path);
    if (match) return { route, params: match.slice(1) };
  }
  return null;
}

function paintNavigation(route) {
  document.querySelectorAll("[data-nav]").forEach((link) => {
    const active = link.dataset.nav === route.nav;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  titleElement.textContent = route.title;
  eyebrowElement.textContent = route.kicker;
  document.title = `${route.title} · SchoolTrack`;
}

async function renderRoute() {
  if (!metaLoaded) return;
  const token = ++renderToken;
  const path = parseHash();
  const matched = matchRoute(path);

  if (!matched) {
    paintNavigation({ nav: "", title: "Page not found", kicker: "SchoolTrack" });
    view.innerHTML = `
      <div class="view-inner">
        <div class="error-panel" role="alert">
          <span class="empty-icon">${icon("search")}</span>
          <h2>Page not found</h2>
          <p>The page <strong>${escapeText(path)}</strong> does not exist in this prototype.</p>
          <a class="btn btn-primary" href="#/dashboard">Return to the dashboard</a>
        </div>
      </div>`;
    window.scrollTo({ top: 0, behavior: "auto" });
    return;
  }

  const { route, params } = matched;
  currentRoute = route;
  paintNavigation(route);
  setMenu(false);
  destroyCharts();
  view.innerHTML = `
    <div class="view-inner">
      <div class="loading-panel">
        <span class="spinner" aria-hidden="true"></span>
        <p>Loading ${escapeText(route.title.toLowerCase())}…</p>
      </div>
    </div>`;

  try {
    await route.render(view, params, { token, isCurrent: () => token === renderToken });
  } catch (error) {
    if (token !== renderToken) return;
    console.error("SchoolTrack view failed", error);
    view.innerHTML = `<div class="view-inner">${errorPanel(error)}</div>`;
  }
  if (token === renderToken) window.scrollTo({ top: 0, behavior: "auto" });
}

function escapeText(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character]));
}

window.addEventListener("hashchange", renderRoute);

/* -------------------------------------------------------------------------- */
/* Startup                                                                    */
/* -------------------------------------------------------------------------- */

function hydrateShell(meta) {
  const schoolName = meta.school_name || "Mwangaza Academy";
  const subtitle = meta.school_subtitle || "Primary & Junior Secondary";
  const canWrite = meta.writes_enabled !== false;
  const isDemo = Boolean(meta.demo_mode);

  const brand = document.getElementById("brand-school");
  if (brand) brand.textContent = schoolName;
  const footer = document.getElementById("footer-meta");
  if (footer) footer.textContent = `${schoolName} · ${subtitle}`;
  const version = document.getElementById("app-version");
  if (version) version.textContent = `${meta.app_name || "SchoolTrack"} v${meta.version || "1.0"}`;
  const storage = document.getElementById("footer-storage");
  if (storage) {
    storage.textContent = meta.storage_backend === "postgresql"
      ? "PostgreSQL storage"
      : "SQLite storage";
  }
  document.title = `SchoolTrack · ${schoolName}`;

  document.querySelectorAll("[data-write-action]").forEach((element) => {
    element.hidden = !canWrite;
  });
  document.body.classList.toggle("read-only-demo", isDemo && !canWrite);

  const strip = document.getElementById("demo-strip");
  if (strip) {
    strip.hidden = !isDemo;
    strip.classList.toggle("read-only", isDemo && !canWrite);
    if (isDemo) {
      const title = document.getElementById("demo-strip-title");
      const text = document.getElementById("demo-strip-text");
      if (title) {
        title.textContent = canWrite ? "Interactive demonstration." : "Read-only demonstration.";
      }
      if (text) {
        const warning = meta.demo_warning || "Fictional data only.";
        text.textContent = canWrite
          ? `${warning} Public visitors may share the same demo dataset.`
          : `${warning} Creating and approving records is disabled in this demo.`;
      }
    }
  }

  const chipText = document.getElementById("demo-chip-text");
  if (chipText) {
    chipText.textContent = isDemo
      ? (canWrite ? "Shared demo data" : "Read-only demo")
      : "Prototype data";
  }
  const sidebarNote = document.getElementById("sidebar-note");
  if (sidebarNote) {
    sidebarNote.textContent = isDemo
      ? (canWrite
          ? "Fictional records. Public visitors share this dataset; writes are rate-limited."
          : "Fictional records. This public demonstration is read-only.")
      : "Fictional records only. This prototype uses the configured database.";
  }
}

async function loadMeta() {
  try {
    state.meta = await api.meta();
    metaLoaded = true;
    hydrateShell(state.meta);
    return true;
  } catch (error) {
    view.innerHTML = `
      <div class="view-inner">
        <div class="error-panel" role="alert">
          <span class="empty-icon">${icon("alert")}</span>
          <h2>SchoolTrack could not start</h2>
          <p>${escapeText(error.message)}</p>
          <button class="btn btn-primary" type="button" data-bootstrap-retry>Start again</button>
        </div>
      </div>`;
    return false;
  }
}

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (target.closest("[data-retry]")) {
    renderRoute();
    return;
  }
  if (target.closest("[data-bootstrap-retry]")) bootstrap();
});

async function bootstrap() {
  paintCategoryButtons();
  view.innerHTML = `
    <div class="view-inner">
      <div class="loading-panel">
        <span class="spinner" aria-hidden="true"></span>
        <p>Starting SchoolTrack…</p>
      </div>
    </div>`;
  const ready = await loadMeta();
  if (!ready) return;
  if (!window.location.hash || window.location.hash === "#/" || window.location.hash === "#") {
    window.history.replaceState(null, "", "#/dashboard");
  }
  await renderRoute();
}

bootstrap();
