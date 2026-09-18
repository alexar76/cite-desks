const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let status = {};
let ui = {};

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (opts.body && !headers["content-type"]) headers["content-type"] = "application/json";
  const res = await fetch(path, { credentials: "include", ...opts, headers });
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/zip")) return res;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || res.statusText);
  return body;
}

function page() {
  const path = location.pathname.replace(/\/$/, "") || "/";
  if (path === "/guide") return "guide";
  if (path === "/sample") return "sample";
  if (path === "/press") return "press";
  if (path === "/legal") return "legal";
  if (path === "/status") return "status";
  // Every Slack message and HMAC webhook the desk sends links to /b/<share_token>
  // (alerts.py). Without this branch nginx's try_files served index.html and the
  // recipient landed on the marketing page instead of the evidence they were alerted
  // about. /login is the same link when a watch has no share token.
  if (path.startsWith("/b/")) return "brief";
  // invoice_view().public_path. A buyer who reloads, or comes back from their wallet,
  // must land on the same invoice — otherwise the amount they were quoted is gone and
  // finishing the purchase needs somebody to look it up for them.
  if (path.startsWith("/pay/")) return "pay";
  if (path === "/login") return "login";
  return "home";
}

function shareToken() {
  return decodeURIComponent(location.pathname.replace(/\/$/, "").slice(3));
}

async function paintSharedBrief() {
  const host = $("view-brief");
  try {
    const brief = await api(`/api/public/briefs/${encodeURIComponent(shareToken())}`);
    $("brief-title").textContent = (brief.watch && brief.watch.name) || ui.shared_brief || "Brief";
    $("brief-status").textContent = [brief.evidence_status, brief.generated_at].filter(Boolean).join(" · ");
    paintSample(brief, "brief-body");
  } catch (err) {
    $("brief-title").textContent = ui.brief_gone || "Brief unavailable";
    $("brief-status").textContent = err.message;
  }
  host.hidden = false;
}

function applyUi(map) {
  ui = map || {};
  document.querySelectorAll("[data-i]").forEach((el) => {
    const key = el.getAttribute("data-i");
    if (ui[key]) el.textContent = ui[key];
  });
}

function listItem(row) {
  return `<li>${esc(row.headline || row.id)} <span class="meta">${esc(row.source || "")}</span></li>`;
}

function listBlock(title, rows) {
  return `<div><h4>${esc(title)}</h4><ul>${(rows || []).map(listItem).join("") || "<li>—</li>"}</ul></div>`;
}

function paintSample(sample, target = "sample") {
  const stamps = (sample.badges || []).map((b) => `<span class="stamp">${esc(b)}</span>`).join("");
  let lists = "";
  if (sample.weather || sample.air || sample.grid) {
    lists = `<div class="split campus">
      ${listBlock("Weather", sample.weather)}
      ${listBlock("Air", sample.air)}
      ${listBlock("Warnings", sample.warnings)}
      ${listBlock("Gauges", sample.gauges)}
      ${listBlock("Grid", sample.grid)}
    </div>`;
  } else if (sample.warnings || sample.gauges) {
    lists = `<div class="split">
      ${listBlock("Warnings", sample.warnings)}
      ${listBlock("Gauges", sample.gauges)}
    </div>`;
  } else if (sample.finnish_ais || sample.norwegian_ais) {
    lists = `<div class="split">
      ${listBlock("Fintraffic", sample.finnish_ais)}
      ${listBlock("Kystverket", sample.norwegian_ais)}
    </div>`;
  } else if (sample.irradiance) {
    lists = `<p class="meta">${esc(JSON.stringify(sample.irradiance))}</p>`;
  }
  $(target).innerHTML = `
    <div class="meta">${esc(sample.artifact_type || "")} · ${esc(sample.evidence_status || "")}</div>
    <h3>${esc(sample.watch?.name || ui.sample || "Brief")}</h3>
    <div>${stamps}</div>
    <p>${esc(sample.summary || "")}</p>
    ${lists}
    <p class="meta">${esc(sample.claim_split || "")}</p>`;
}

function paintWatchForm() {
  const kind = status.watch_kind === "point" ? "point" : "bbox";
  const box = status.default_bbox || [];
  const point = status.default_point || [];
  $("new-watch").innerHTML = kind === "point"
    ? `<label>Name <input name="name" required></label>
       <label>Lat <input name="lat" required value="${esc(point[0] ?? "")}"></label>
       <label>Lon <input name="lon" required value="${esc(point[1] ?? "")}"></label>
       <button class="btn btn-accent" type="submit">${esc(ui.new_watch || "Save")}</button>`
    : `<label>Name <input name="name" required></label>
       <label>West <input name="west" required value="${esc(box[0] ?? "")}"></label>
       <label>South <input name="south" required value="${esc(box[1] ?? "")}"></label>
       <label>East <input name="east" required value="${esc(box[2] ?? "")}"></label>
       <label>North <input name="north" required value="${esc(box[3] ?? "")}"></label>
       <button class="btn btn-accent" type="submit">${esc(ui.new_watch || "Save")}</button>`;
}

function where(w) {
  if (w.lat != null && w.lon != null) return `${w.lat}, ${w.lon}`;
  if (w.west != null) return `${w.west}/${w.south} → ${w.east}/${w.north}`;
  return "";
}

async function loadDesk() {
  $("workspace").hidden = false;
  $("logout").hidden = false;
  const watches = await api("/api/watches");
  $("watches").innerHTML = watches.map((w) =>
    `<tr>
      <td>${esc(w.name)}<div class="muted">${esc(w.schedule)} · ${esc(w.status)}</div></td>
      <td class="muted">${esc(where(w))}</td>
      <td>${esc(w.policy)}</td>
      <td><button class="btn" data-run="${esc(w.id)}">${esc(ui.run_now || "Run")}</button></td>
    </tr>`
  ).join("");
  const archive = await api("/api/archive");
  $("archive").innerHTML = archive.map((b) =>
    `<tr>
      <td class="muted">${esc(b.id)}</td>
      <td>${esc(b.evidence_status || "")}</td>
      <td class="muted">${esc(b.created_at || "")}</td>
      <td><a href="/api/briefs/${esc(b.id)}/cite-pack" data-pack="${esc(b.id)}">${esc(ui.cite_pack || "Cite pack")}</a></td>
    </tr>`
  ).join("");
}

// ------------------------------------------------------------------ checkout
// The buyer never waits for a person: the invoice page polls until the settlement
// watcher has turned their USDC into a desk key, then redeems that key itself.
let invoiceId = null;
let pollTimer = null;

function paintPlans() {
  const rail = status.pay || {};
  const host = $("plans");
  if (!rail.enabled) {
    host.innerHTML = "";
    const closed = $("pay-closed");
    closed.textContent = [ui.pay_closed, rail.closed_reason].filter(Boolean).join(" ");
    closed.hidden = false;
    return;
  }
  $("pay-closed").hidden = true;
  host.innerHTML = Object.entries(rail.plans || {}).map(([code, plan]) =>
    `<div class="plan">
      <h3>${esc(plan.name)}</h3>
      <div class="price">$${esc(plan.price_usd)}</div>
      <ul>
        <li>${esc(plan.watches)} ${esc(ui.pay_plan_watches || "watches")}</li>
        <li>${esc(plan.runs)} ${esc(ui.pay_plan_runs || "runs / month")}</li>
        <li>${esc(plan.days)} days</li>
      </ul>
      <button class="btn btn-accent" data-plan="${esc(code)}">${esc(ui.pay_buy || "Buy")}</button>
    </div>`
  ).join("");
}

function stamp(iso) {
  if (!iso) return "";
  const when = new Date(iso);
  return isNaN(when) ? iso : when.toLocaleString();
}

function paintInvoice(invoice) {
  const paid = invoice.status === "paid";
  const box = $("checkout");
  box.hidden = false;
  $("ck-number").textContent = `${invoice.number} · ${invoice.plan_name} · ${invoice.days} days`;
  $("ck-amount").textContent = invoice.amount_usdc;
  $("ck-to").textContent = invoice.pay_to;
  $("ck-wallet").href = invoice.eip681;
  $("ck-explorer").href = invoice.explorer_tx || invoice.explorer_address;
  // A settled invoice must stop asking to be paid. Leaving "send exactly …" and a wallet
  // link on a paid card is how a buyer pays twice.
  $("ck-instructions").hidden = paid;
  $("ck-wallet").hidden = paid;
  $("ck-simulate").hidden = !invoice.fixture || paid;
  $("ck-confirm").hidden = paid;
  $("ck-expiry").textContent = paid
    ? [stamp(invoice.paid_at), invoice.late ? ui.pay_late : ""].filter(Boolean).join(" · ")
    : `${ui.pay_expires || "Quote lapses"} ${stamp(invoice.expires_at)}`;
  $("ck-state").textContent = paid ? (ui.pay_paid || "Paid.") : (ui.pay_waiting || "Waiting for your transfer.");
  if (invoice.desk_key) {
    $("ck-key").textContent = invoice.desk_key;
    $("ck-key-wrap").hidden = false;
  }
  box.scrollIntoView({ block: "nearest" });
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

async function settleIfPaid(invoice) {
  if (invoice.status !== "paid") return false;
  stopPolling();
  paintInvoice(invoice);
  if (invoice.desk_key) {
    // Redeem on the buyer's behalf. The key stays on screen in case they want to keep it,
    // but nobody has to paste it anywhere to start using what they bought.
    try {
      await api("/api/auth/redeem", { method: "POST", body: JSON.stringify({ desk_key: invoice.desk_key }) });
      await loadDesk();
    } catch (err) {
      $("ck-err").textContent = err.message;
    }
  }
  return true;
}

async function trackInvoice(id, { push = true } = {}) {
  invoiceId = id;
  if (push && location.pathname !== `/pay/${id}`) history.pushState({}, "", `/pay/${id}`);
  stopPolling();
  const read = async () => {
    try {
      const invoice = await api(`/api/public/pay/invoices/${encodeURIComponent(id)}`);
      if (!(await settleIfPaid(invoice))) paintInvoice(invoice);
    } catch (err) {
      $("ck-err").textContent = err.message;
      stopPolling();
    }
  };
  await read();
  pollTimer = setInterval(read, 5000);
}

function paintGuide(guide) {
  $("guide-title").textContent = guide.title || "";
  $("guide-lede").textContent = guide.lede || "";
  $("guide-body").innerHTML = (guide.sections || []).map((sec) =>
    `<section id="${esc(sec.id)}"><h2>${esc(sec.title)}</h2>${(sec.body || []).map((p) => `<p>${esc(p)}</p>`).join("")}</section>`
  ).join("");
}

function bullets(items) {
  return (items || []).map((item) => `<li>${esc(item)}</li>`).join("");
}

function paintLanding(landing) {
  landing = landing || {};
  const ticks = (landing.ticker || []).concat(landing.ticker || []);
  $("ticker").innerHTML = ticks.map((item) =>
    `<span class="${String(item).includes("SIGNED") ? "signed" : ""}">${esc(item)}</span>`
  ).join("");
  $("sell-list").innerHTML = bullets(landing.sell);
  $("refuse-list").innerHTML = bullets(landing.refuse);
  $("beyond-h2").textContent = landing.beyond_h2 || "";
  $("beyond-sub").textContent = landing.beyond_sub || "";
  $("beyond-cards").innerHTML = ["b1", "b2", "b3"].map((key) =>
    `<div class="card"><h3>${esc(landing[`${key}_t`] || "")}</h3><p>${esc(landing[`${key}_p`] || "")}</p></div>`
  ).join("");
  $("product-h2-a").textContent = landing.product_h2_a || "";
  $("product-h2-b").textContent = landing.product_h2_b || "";
  $("product-sub").textContent = landing.product_sub || "";
  $("product-cards").innerHTML = ["p1", "p2", "p3"].map((key, i) =>
    `<div class="card"><div class="idx">0${i + 1}</div><h3>${esc(landing[`${key}_t`] || "")}</h3><p>${esc(landing[`${key}_p`] || "")}</p></div>`
  ).join("");
}

function paintLegal(legal) {
  legal = legal || {};
  $("legal-p1").textContent = legal.p1 || "";
  $("legal-p2").textContent = legal.p2 || "";
  $("legal-strip-page").textContent = status.legal_strip || "";
}

function setupVisualMotion() {
  const nav = document.querySelector(".site-nav");
  const paintNav = () => nav?.classList.toggle("is-scrolled", window.scrollY > 12);
  paintNav();
  window.addEventListener("scroll", paintNav, { passive: true });

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  document.documentElement.classList.add("has-motion");
  const targets = document.querySelectorAll(
    ".split-claim, .section:not(#desk), .grid-3 .card, .grid-2 .card, .plans .plan, .paper",
  );
  targets.forEach((node, index) => {
    node.classList.add("reveal-item");
    node.style.setProperty("--reveal-delay", `${(index % 3) * 70}ms`);
  });
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.08, rootMargin: "0px 0px -7% 0px" });
  targets.forEach((node) => observer.observe(node));
}

async function paintPress() {
  const press = await api("/api/public/press");
  $("press-boilerplate").textContent = press.boilerplate || "";
  $("press-links").innerHTML =
    `Public origin <a href="${esc(press.origin)}">${esc(press.host)}</a>. Desk mail ` +
    `<a href="mailto:${esc(press.mail)}">${esc(press.mail)}</a>. Sample artifact ` +
    `<a href="/sample" data-nav>/sample</a>. Cite pack <a href="/api/public/sample-cite-pack">sample_cite.zip</a>.`;
  $("press-facts").innerHTML = (press.facts || []).map((row) =>
    `<tr><th>${esc(row[0])}</th><td>${esc(row[1])}</td></tr>`
  ).join("");
  $("press-do").innerHTML = bullets(press.do);
  $("press-dont").innerHTML = bullets(press.do_not);
}

async function paintStatusView() {
  const health = await api("/api/public/health").catch(() => ({}));
  const checkout = health.checkout || {};
  $("status-body").innerHTML = `
    <p class="meta">${esc(status.product)} · ${esc(status.canonical_host)}</p>
    <p>${esc(status.tagline || "")}</p>
    <p class="meta">hub ${esc(status.hub_mode)} · pay ${esc(status.pay_mode)} · last run ${esc(status.last_completed_run_at || "—")}</p>
    <p>Checkout ${checkout.open ? "open" : "closed"} · settlement ${esc(checkout.settlement || "—")}</p>
    <p>${esc(status.placement_note || "")}</p>
    <p class="meta">Not: ${esc((status.not || []).join(", "))}</p>
  `;
}

function showView(view) {
  const homeish = view === "home" || view === "login" || view === "pay";
  $("view-home").hidden = !homeish;
  $("view-guide").hidden = view !== "guide";
  $("view-brief").hidden = view !== "brief";
  $("view-sample").hidden = view !== "sample";
  $("view-press").hidden = view !== "press";
  $("view-legal").hidden = view !== "legal";
  $("view-status").hidden = view !== "status";
}

async function route() {
  const view = page();
  showView(view);
  if (view === "brief") { await paintSharedBrief(); return; }
  if (view === "press") await paintPress();
  if (view === "status") await paintStatusView();
  if (view === "login") location.hash = "#desk";
  if (view === "pay") {
    await trackInvoice(decodeURIComponent(location.pathname.replace(/\/$/, "").slice(5)), { push: false });
  }
}

let landingPack = {};

async function boot() {
  const lang = new URLSearchParams(location.search).get("lang") || "";
  const i18n = await api("/api/public/i18n" + (lang ? `?lang=${encodeURIComponent(lang)}` : ""));
  status = await api("/api/public/status" + (lang ? `?lang=${encodeURIComponent(lang)}` : ""));
  landingPack = i18n.landing || {};
  document.documentElement.lang = i18n.locale;
  document.documentElement.dataset.desk = status.desk_id;
  document.title = status.product;
  $("brand-name").textContent = status.product.split(" ")[0];
  applyUi(i18n.ui);
  if (status.demo) {
    const banner = $("demo-banner");
    if (banner) banner.hidden = false;
    document.body.classList.add("demo-mode");
  }
  $("kicker").textContent = i18n.ui.kicker || "";
  $("hero-title").textContent = i18n.ui.hero_title || status.product;
  $("hero-em").textContent = i18n.ui.hero_em || "";
  $("lede").textContent = i18n.ui.lede || status.tagline || "";
  $("region").textContent = `${i18n.ui.region_label || ""} · ${status.host_region || ""}`.trim();
  $("legal-strip").textContent = status.legal_strip || "";
  $("footer-powered").textContent = i18n.ui.footer_powered || "";
  $("mail").textContent = status.desk_mail || "";
  $("mail").href = status.desk_mail ? `mailto:${status.desk_mail}` : "#";
  $("host").textContent = status.canonical_host || "";
  $("badges").innerHTML = (status.not || []).map((n) => `<span class="badge">NOT ${esc(n)}</span>`).join("");
  const sel = $("lang");
  sel.innerHTML = (i18n.locales || []).map((loc) =>
    `<option value="${esc(loc.code)}" ${loc.code === i18n.locale ? "selected" : ""}>${esc(loc.name)}</option>`
  ).join("");
  const sample = await api("/api/public/sample-brief");
  paintSample(sample);
  paintSample(sample, "sample-page");
  paintWatchForm();
  paintPlans();
  paintGuide(i18n.guide || {});
  paintLanding(landingPack);
  paintLegal(i18n.legal || {});
  setupVisualMotion();
  if (typeof window.mountDeskScene === "function") window.mountDeskScene(status.desk_id);
  else {
    const wait = () => {
      if (typeof window.mountDeskScene === "function") window.mountDeskScene(status.desk_id);
      else requestAnimationFrame(wait);
    };
    wait();
  }
  if (status.demo_email) document.querySelector("#login input[name=email]").value = status.demo_email;
  try { await loadDesk(); } catch { $("workspace").hidden = true; $("logout").hidden = true; }
  await route();
}

$("lang").addEventListener("change", () => {
  const next = $("lang").value;
  const url = new URL(location.href);
  url.searchParams.set("lang", next);
  location.assign(url.toString());
});

$("login").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("desk-err").textContent = "";
  try {
    const data = Object.fromEntries(new FormData(event.target));
    await api("/api/auth/login", { method: "POST", body: JSON.stringify(data) });
    await loadDesk();
  } catch (err) {
    $("desk-err").textContent = err.message;
  }
});
$("logout").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" }).catch(() => {});
  $("workspace").hidden = true;
  $("logout").hidden = true;
});
$("watches").addEventListener("click", async (event) => {
  const id = event.target.dataset.run;
  if (!id) return;
  try {
    $("run").textContent = JSON.stringify(await api("/api/watches/" + id + "/run", { method: "POST" }), null, 2);
    await loadDesk();
  } catch (err) {
    $("run").textContent = err.message;
  }
});
$("archive").addEventListener("click", async (event) => {
  const id = event.target.dataset.pack;
  if (!id) return;
  event.preventDefault();
  const res = await api("/api/briefs/" + id + "/cite-pack");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = id + "-cite-pack.zip";
  a.click();
  URL.revokeObjectURL(url);
});
$("plans").addEventListener("click", async (event) => {
  const plan = event.target.dataset.plan;
  if (!plan) return;
  $("ck-err").textContent = "";
  try {
    const invoice = await api("/api/public/pay/invoices", { method: "POST", body: JSON.stringify({ plan }) });
    paintInvoice(invoice);
    await trackInvoice(invoice.id);
  } catch (err) {
    $("ck-err").textContent = err.message;
  }
});
$("ck-simulate").addEventListener("click", async () => {
  if (!invoiceId) return;
  $("ck-err").textContent = "";
  try {
    await api(`/api/public/pay/invoices/${encodeURIComponent(invoiceId)}/simulate`, { method: "POST" });
    await trackInvoice(invoiceId, { push: false });
  } catch (err) {
    $("ck-err").textContent = err.message;
  }
});
$("ck-confirm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const tx = new FormData(event.target).get("tx_hash");
  if (!invoiceId || !tx) return;
  $("ck-err").textContent = "";
  try {
    const invoice = await api(`/api/public/pay/invoices/${encodeURIComponent(invoiceId)}/confirm`, {
      method: "POST",
      body: JSON.stringify({ tx_hash: String(tx).trim() }),
    });
    if (!(await settleIfPaid(invoice))) paintInvoice(invoice);
  } catch (err) {
    $("ck-err").textContent = err.message;
  }
});
$("redeem").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("desk-err").textContent = "";
  try {
    const data = Object.fromEntries(new FormData(event.target));
    await api("/api/auth/redeem", { method: "POST", body: JSON.stringify(data) });
    await loadDesk();
  } catch (err) {
    $("desk-err").textContent = err.message;
  }
});
$("new-watch").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  const body = { name: data.name };
  for (const key of ["west", "south", "east", "north", "lat", "lon"]) {
    if (data[key] !== undefined && data[key] !== "") body[key] = Number(data[key]);
  }
  try {
    await api("/api/watches", { method: "POST", body: JSON.stringify(body) });
    await loadDesk();
  } catch (err) {
    $("desk-err").textContent = err.message;
  }
});

boot();
window.addEventListener("popstate", () => { route(); });
document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-nav]");
  if (!link) return;
  const href = link.getAttribute("href");
  if (!href || href.startsWith("http") || href.startsWith("mailto:")) return;
  event.preventDefault();
  const url = new URL(href, location.origin);
  url.search = location.search;
  history.pushState({}, "", url.pathname + url.search + url.hash);
  route();
  if (url.hash) {
    const target = document.querySelector(url.hash);
    if (target) target.scrollIntoView({ block: "start" });
  } else {
    window.scrollTo(0, 0);
  }
});
