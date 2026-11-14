"""The patient-facing booking page, served at /."""

import json

_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Book an appointment</title>
<style>
  :root { --bg:#f6f5f1; --card:#fff; --ink:#1b1d1f; --muted:#6b6f73; --line:#e3e1db;
          --accent:#c9643f; --accent-ink:#fff; --ok:#2f7d4f; --ok-bg:#e7f3ec; --bad:#b3261e; --bad-bg:#fbeaea; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#141516; --card:#1c1d1f; --ink:#eeece6; --muted:#a2a59f; --line:#2e3033;
            --accent:#e07e57; --accent-ink:#141516; --ok:#7fd0a0; --ok-bg:#1d2b23; --bad:#f2a49e; --bad-bg:#3a1f1d; }
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--ink); font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
  .wrap { max-width:880px; margin:0 auto; padding:40px 16px 80px; }
  h1 { font-size:1.9rem; letter-spacing:-.01em; }
  h2 { font-size:1.15rem; margin-bottom:12px; }
  .sub { color:var(--muted); margin:4px 0 28px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px; margin-bottom:20px; }
  .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
  select, input { font:inherit; color:inherit; background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:9px 12px; min-width:0; }
  input { flex:1 1 200px; }
  button { font:inherit; border:0; border-radius:8px; padding:9px 16px; cursor:pointer; background:var(--accent); color:var(--accent-ink); font-weight:600; }
  button.ghost { background:transparent; color:var(--ink); border:1px solid var(--line); font-weight:500; }
  button:disabled { opacity:.5; cursor:not-allowed; }
  .day { margin-top:16px; }
  .day h3 { font-size:.8rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); margin-bottom:8px; }
  .slots { display:grid; grid-template-columns:repeat(auto-fill,minmax(130px,1fr)); gap:8px; }
  .slot { text-align:left; background:var(--bg); color:var(--ink); border:1px solid var(--line); font-weight:500; }
  .slot small { display:block; color:var(--muted); font-weight:400; }
  .slot.selected { border-color:var(--accent); box-shadow:0 0 0 2px var(--accent) inset; }
  .slot:disabled { text-decoration:line-through; }
  form { display:none; margin-top:16px; padding-top:16px; border-top:1px solid var(--line); }
  form.open { display:block; }
  .msg { margin-top:12px; padding:10px 12px; border-radius:8px; display:none; }
  .msg.show { display:block; }
  .msg.ok { background:var(--ok-bg); color:var(--ok); }
  .msg.bad { background:var(--bad-bg); color:var(--bad); }
  .confirm dl { display:grid; grid-template-columns:max-content 1fr; gap:6px 16px; margin-top:12px; }
  .confirm dt { color:var(--muted); }
  .confirm code, td code { font-size:.85em; }
  table { width:100%; border-collapse:collapse; margin-top:12px; font-size:.95rem; }
  th, td { text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); }
  th { color:var(--muted); font-weight:500; font-size:.8rem; text-transform:uppercase; letter-spacing:.06em; }
  .pill { font-size:.8rem; padding:2px 8px; border-radius:99px; background:var(--ok-bg); color:var(--ok); }
  .pill.cancelled { background:var(--bad-bg); color:var(--bad); }
  .muted { color:var(--muted); }
  .table-scroll { overflow-x:auto; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Book an appointment</h1>
  <p class="sub">Pick a free slot, enter your details, and you're booked.</p>

  <section class="card">
    <div class="row" style="justify-content:space-between">
      <h2 style="margin:0">Available slots</h2>
      <label class="row muted">Provider
        <select id="provider"><option value="">All providers</option></select>
      </label>
    </div>
    <div id="slots"><p class="muted" style="margin-top:12px">Loading slotsâ€¦</p></div>

    <form id="book-form" autocomplete="on">
      <p id="chosen" style="margin-bottom:10px"></p>
      <div class="row">
        <input id="name" name="name" placeholder="Full name" required>
        <input id="email" name="email" type="email" placeholder="Email address" required>
        <button id="book-btn" type="submit">Book this slot</button>
      </div>
    </form>
    <div id="book-msg" class="msg"></div>
  </section>

  <section id="confirmation" class="card confirm" style="display:none"></section>

  <section class="card">
    <h2>My bookings</h2>
    <form id="lookup-form" class="open" style="margin:0;padding:0;border:0">
      <div class="row">
        <input id="lookup-email" type="email" placeholder="Email you booked with" required>
        <button type="submit" class="ghost">Show my bookings</button>
      </div>
    </form>
    <div id="mine"></div>
  </section>
</div>

<script>
const API = "/api";
const KEY = __API_KEY__;
let slots = [], chosen = null, pending = null, cursor = null, lookupEmail = "";
const $ = (id) => document.getElementById(id);
const fmtDay = (d) => d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
const fmtTime = (d) => d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options = {}) {
  const res = await fetch(API + path, { ...options, headers: { "X-API-Key": KEY, "Content-Type": "application/json", ...(options.headers || {}) } });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

function show(el, text, ok) { el.textContent = text; el.className = "msg show " + (ok ? "ok" : "bad"); }

async function loadSlots() {
  const provider = $("provider").value;
  const { res, data } = await api("/slots" + (provider ? "?provider=" + encodeURIComponent(provider) : ""));
  if (!res.ok) { $("slots").innerHTML = '<p class="muted">Could not load slots: ' + esc(data.error || res.status) + "</p>"; return; }
  slots = data.slots;
  if (!provider) {
    const names = [...new Set(slots.map((s) => s.provider))].sort();
    $("provider").innerHTML = '<option value="">All providers</option>' + names.map((n) => `<option>${esc(n)}</option>`).join("");
  }
  renderSlots();
}

function renderSlots() {
  const now = new Date();
  const upcoming = slots.filter((s) => new Date(s.start) > now);
  if (!upcoming.length) { $("slots").innerHTML = '<p class="muted" style="margin-top:12px">No upcoming slots.</p>'; return; }
  const days = {};
  for (const s of upcoming) (days[fmtDay(new Date(s.start))] ||= []).push(s);
  $("slots").innerHTML = Object.entries(days).map(([day, list]) => `
    <div class="day"><h3>${esc(day)}</h3><div class="slots">
      ${list.map((s) => `<button type="button" class="slot ${chosen && chosen.id === s.id ? "selected" : ""}" data-id="${esc(s.id)}" ${s.available ? "" : "disabled"}>
        ${fmtTime(new Date(s.start))} â€“ ${fmtTime(new Date(s.end))}<small>${esc(s.provider)}${s.available ? "" : " Â· booked"}</small></button>`).join("")}
    </div></div>`).join("");
}

$("slots").addEventListener("click", (e) => {
  const btn = e.target.closest(".slot");
  if (!btn || btn.disabled) return;
  chosen = slots.find((s) => s.id === btn.dataset.id);
  pending = null;
  $("chosen").innerHTML = `Booking <strong>${esc(chosen.provider)}</strong>, ${esc(fmtDay(new Date(chosen.start)))} at ${esc(fmtTime(new Date(chosen.start)))}`;
  $("book-form").classList.add("open");
  $("book-msg").className = "msg";
  renderSlots();
  $("name").focus();
});

$("book-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!chosen) return;
  const body = { slot_id: chosen.id, name: $("name").value, email: $("email").value };
  // One idempotency key per booking attempt, reused if the same details are retried.
  const bodyText = JSON.stringify(body);
  if (!pending || pending.body !== bodyText) pending = { body: bodyText, key: crypto.randomUUID() };
  $("book-btn").disabled = true;
  try {
    const { res, data } = await api("/bookings", { method: "POST", body: bodyText, headers: { "Idempotency-Key": pending.key } });
    if (res.status === 201) {
      pending = null;
      showConfirmation(data, chosen);
      $("book-form").classList.remove("open");
      $("book-msg").className = "msg";
      chosen = null;
      $("lookup-email").value = data.email;
    } else if (res.status === 429) {
      show($("book-msg"), `Too many attempts. Please wait ${res.headers.get("Retry-After") || 60} seconds and try again.`, false);
    } else {
      show($("book-msg"), data.error ? data.error.charAt(0).toUpperCase() + data.error.slice(1) + "." : "Something went wrong.", false);
      if (res.status === 409) pending = null;
    }
  } catch {
    show($("book-msg"), "Network problem. Press Book again: you won't be booked twice.", false);
  } finally {
    $("book-btn").disabled = false;
    loadSlots();
  }
});

function showConfirmation(b, slot) {
  const start = new Date(slot.start);
  $("confirmation").style.display = "block";
  $("confirmation").innerHTML = `
    <h2>You're booked âœ“</h2>
    <p class="muted">A record of your appointment:</p>
    <dl>
      <dt>Booking ID</dt><dd><code>${esc(b.id)}</code></dd>
      <dt>Provider</dt><dd>${esc(slot.provider)}</dd>
      <dt>When</dt><dd>${esc(fmtDay(start))}, ${esc(fmtTime(start))} â€“ ${esc(fmtTime(new Date(slot.end)))}</dd>
      <dt>Name</dt><dd>${esc(b.name)}</dd>
      <dt>Email</dt><dd>${esc(b.email)}</dd>
      <dt>Status</dt><dd><span class="pill">${esc(b.status)}</span></dd>
    </dl>`;
  $("confirmation").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function loadMine(more) {
  if (!more) { cursor = null; $("mine").innerHTML = ""; }
  const qs = new URLSearchParams({ email: lookupEmail, limit: "5" });
  if (cursor) qs.set("cursor", cursor);
  const { res, data } = await api("/bookings?" + qs);
  if (!res.ok) { $("mine").innerHTML = `<div class="msg show bad">${esc(data.error || "Could not load bookings")}</div>`; return; }
  cursor = data.next_cursor;
  const slotById = Object.fromEntries(slots.map((s) => [s.id, s]));
  const rows = data.bookings.map((b) => {
    const s = slotById[b.slot_id];
    const when = s ? `${fmtDay(new Date(s.start))}, ${fmtTime(new Date(s.start))}` : esc(b.slot_id);
    return `<tr><td>${esc(when)}<br><span class="muted">${esc(s ? s.provider : "")}</span></td>
      <td><code>${esc(b.id)}</code></td>
      <td><span class="pill ${b.status === "cancelled" ? "cancelled" : ""}">${esc(b.status)}</span></td>
      <td>${b.status === "confirmed" ? `<button class="ghost" data-cancel="${esc(b.id)}">Cancel</button>` : ""}</td></tr>`;
  }).join("");
  let table = $("mine").querySelector("tbody");
  if (!table) {
    if (!data.bookings.length) { $("mine").innerHTML = '<p class="muted" style="margin-top:12px">No bookings for that email.</p>'; return; }
    $("mine").innerHTML = '<div class="table-scroll"><table><thead><tr><th>When</th><th>Booking ID</th><th>Status</th><th></th></tr></thead><tbody></tbody></table></div><div class="row" style="margin-top:12px" id="more-row"></div>';
    table = $("mine").querySelector("tbody");
  }
  table.insertAdjacentHTML("beforeend", rows);
  $("more-row").innerHTML = cursor ? '<button class="ghost" id="more">Load more</button>' : '<span class="muted">That\'s all your bookings.</span>';
}

$("lookup-form").addEventListener("submit", (e) => { e.preventDefault(); lookupEmail = $("lookup-email").value.trim(); loadMine(false); });
$("mine").addEventListener("click", async (e) => {
  if (e.target.id === "more") return loadMine(true);
  const id = e.target.dataset.cancel;
  if (!id || !confirm("Cancel this booking?")) return;
  e.target.disabled = true;
  const { res, data } = await api("/bookings/" + encodeURIComponent(id), { method: "DELETE" });
  if (!res.ok) alert(data.error || "Could not cancel");
  await loadSlots();
  loadMine(false);
});
$("provider").addEventListener("change", () => { chosen = null; $("book-form").classList.remove("open"); loadSlots(); });
loadSlots();
</script>
</body>
</html>
"""


def render_page(api_key: str) -> str:
    # The page is a client of the API, so it needs the key. json.dumps + "<\/" escaping
    # keeps the value safe inside the <script> tag.
    return _PAGE.replace("__API_KEY__", json.dumps(api_key).replace("</", "<\\/"))
