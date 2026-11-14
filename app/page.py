"""The patient-facing booking page, served at /."""

import json

_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Book an appointment · Wellspring Clinic</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#f4f1ea; --bg-2:#ebe6db; --card:#fffdf9; --ink:#1d2321; --muted:#68716d; --line:#e2ddd2;
    --brand:#1f6f5c; --brand-ink:#ffffff; --brand-soft:#e3f0eb;
    --ok:#1f6f5c; --ok-bg:#e3f0eb; --bad:#a8382c; --bad-bg:#f8e6e2;
    --shadow:0 1px 2px rgba(29,35,33,.05), 0 8px 24px rgba(29,35,33,.06);
    --serif:"Fraunces", Georgia, serif; --sans:"Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg:#121615; --bg-2:#181d1b; --card:#1a1f1d; --ink:#ecebe5; --muted:#9aa39e; --line:#2b3330;
      --brand:#5cc4a6; --brand-ink:#0f1513; --brand-soft:#1d2e29;
      --ok:#7dd3b8; --ok-bg:#1d2e29; --bad:#f0a497; --bad-bg:#3a201c;
      --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.25);
    }
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--ink); font:15px/1.55 var(--sans); -webkit-font-smoothing:antialiased; }
  button, input { font:inherit; color:inherit; }
  .wrap { max-width:1120px; margin:0 auto; padding:0 20px; }

  header { border-bottom:1px solid var(--line); background:var(--card); }
  header .wrap { display:flex; align-items:center; justify-content:space-between; height:64px; }
  .brand { display:flex; align-items:center; gap:10px; font-weight:600; letter-spacing:-.01em; }
  .logo { width:32px; height:32px; border-radius:9px; background:var(--brand); display:grid; place-items:center; }
  .logo svg { width:18px; height:18px; }
  .header-note { color:var(--muted); font-size:.9rem; display:flex; align-items:center; gap:8px; }
  .dot { width:8px; height:8px; border-radius:50%; background:#3cb371; box-shadow:0 0 0 4px rgba(60,179,113,.15); }

  .hero { padding:48px 0 28px; }
  .hero h1 { font-family:var(--serif); font-weight:500; font-size:clamp(2rem, 4.5vw, 3rem); line-height:1.1; letter-spacing:-.02em; }
  .hero p { color:var(--muted); margin-top:10px; max-width:560px; font-size:1.05rem; }
  .steps { display:flex; gap:8px; flex-wrap:wrap; margin-top:20px; }
  .step { display:flex; align-items:center; gap:8px; padding:6px 12px 6px 6px; border:1px solid var(--line); border-radius:99px; background:var(--card); font-size:.88rem; color:var(--muted); }
  .step b { width:22px; height:22px; border-radius:50%; display:grid; place-items:center; background:var(--bg-2); color:var(--ink); font-size:.78rem; }
  .step.on { color:var(--ink); border-color:var(--brand); }
  .step.on b { background:var(--brand); color:var(--brand-ink); }

  .grid { display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:24px; align-items:start; padding-bottom:24px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:16px; box-shadow:var(--shadow); }
  .card-pad { padding:24px; }
  .card h2 { font-family:var(--serif); font-weight:500; font-size:1.35rem; letter-spacing:-.01em; }
  .label { font-size:.75rem; text-transform:uppercase; letter-spacing:.09em; color:var(--muted); font-weight:600; }

  .providers { display:flex; gap:8px; flex-wrap:wrap; margin:16px 0 20px; }
  .chip { display:flex; align-items:center; gap:8px; padding:6px 14px 6px 6px; border-radius:99px; border:1px solid var(--line); background:transparent; cursor:pointer; font-weight:500; transition:border-color .15s, background .15s; }
  .chip:hover { border-color:var(--muted); }
  .chip.on { background:var(--brand-soft); border-color:var(--brand); }
  .chip.all { padding-left:14px; }
  .avatar { width:26px; height:26px; border-radius:50%; display:grid; place-items:center; font-size:.72rem; font-weight:600; color:#fff; flex:none; }

  .days { display:flex; gap:8px; overflow-x:auto; padding-bottom:6px; scrollbar-width:thin; }
  .daytab { flex:none; min-width:76px; padding:10px 12px; border-radius:12px; border:1px solid var(--line); background:transparent; cursor:pointer; text-align:center; transition:border-color .15s, background .15s; }
  .daytab:hover { border-color:var(--muted); }
  .daytab .dow { font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
  .daytab .dnum { font-family:var(--serif); font-size:1.5rem; line-height:1.2; }
  .daytab .free { font-size:.75rem; color:var(--brand); font-weight:500; }
  .daytab.on { background:var(--brand); border-color:var(--brand); color:var(--brand-ink); }
  .daytab.on .dow, .daytab.on .free { color:var(--brand-ink); opacity:.85; }
  .daytab.full .free { color:var(--muted); }

  .period { margin-top:22px; }
  .period .label { margin-bottom:10px; display:block; }
  .slots { display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:10px; }
  .slot { display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:12px; border:1px solid var(--line); background:var(--bg); cursor:pointer; text-align:left; transition:border-color .15s, transform .1s, background .15s; }
  .slot:hover:not(:disabled) { border-color:var(--brand); transform:translateY(-1px); }
  .slot .time { font-weight:600; font-variant-numeric:tabular-nums; }
  .slot .who { font-size:.8rem; color:var(--muted); display:block; }
  .slot.on { border-color:var(--brand); background:var(--brand-soft); box-shadow:0 0 0 1px var(--brand) inset; }
  .slot:disabled { cursor:not-allowed; opacity:.45; }
  .slot:disabled .time { text-decoration:line-through; }
  .empty { color:var(--muted); padding:28px 0; text-align:center; }

  .panel { position:sticky; top:20px; }
  .summary { margin:16px 0; padding:14px; border-radius:12px; background:var(--bg); border:1px dashed var(--line); color:var(--muted); font-size:.92rem; }
  .summary.on { border-style:solid; border-color:var(--brand); background:var(--brand-soft); color:var(--ink); display:flex; gap:12px; align-items:center; }
  .summary .avatar { width:40px; height:40px; font-size:.9rem; }
  .summary strong { display:block; }
  .field { display:block; margin-bottom:12px; }
  .field span { display:block; font-size:.85rem; font-weight:500; margin-bottom:6px; }
  .field input { width:100%; padding:11px 13px; border-radius:10px; border:1px solid var(--line); background:var(--bg); outline:none; transition:border-color .15s, box-shadow .15s; }
  .field input:focus { border-color:var(--brand); box-shadow:0 0 0 3px var(--brand-soft); }
  .btn { width:100%; padding:12px 16px; border:0; border-radius:10px; background:var(--brand); color:var(--brand-ink); font-weight:600; cursor:pointer; transition:filter .15s, transform .1s; }
  .btn:hover:not(:disabled) { filter:brightness(1.08); }
  .btn:active:not(:disabled) { transform:translateY(1px); }
  .btn:disabled { opacity:.5; cursor:not-allowed; }
  .btn.ghost { background:transparent; color:var(--ink); border:1px solid var(--line); width:auto; }
  .btn.small { padding:7px 12px; font-size:.85rem; font-weight:500; }
  .fine { font-size:.8rem; color:var(--muted); margin-top:10px; text-align:center; }
  .msg { margin-top:12px; padding:10px 12px; border-radius:10px; font-size:.9rem; display:none; }
  .msg.show { display:block; }
  .msg.ok { background:var(--ok-bg); color:var(--ok); }
  .msg.bad { background:var(--bad-bg); color:var(--bad); }

  .confirmed { text-align:center; padding:8px 0 4px; }
  .tick { width:56px; height:56px; border-radius:50%; background:var(--brand); color:var(--brand-ink); display:grid; place-items:center; margin:0 auto 14px; animation:pop .35s ease-out; }
  @keyframes pop { from { transform:scale(.6); opacity:0; } to { transform:scale(1); opacity:1; } }
  .confirmed h2 { margin-bottom:4px; }
  .ticket { margin:18px 0; text-align:left; border:1px solid var(--line); border-radius:12px; overflow:hidden; }
  .ticket div { display:flex; justify-content:space-between; gap:12px; padding:9px 14px; font-size:.9rem; }
  .ticket div + div { border-top:1px dashed var(--line); }
  .ticket dt { color:var(--muted); }
  .ticket dd { font-weight:500; text-align:right; word-break:break-all; }
  code { font-family:ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size:.82rem; }

  .mine-head { display:flex; justify-content:space-between; align-items:end; gap:16px; flex-wrap:wrap; }
  .lookup { display:flex; gap:8px; flex:1 1 320px; max-width:460px; }
  .lookup input { flex:1; min-width:0; padding:10px 13px; border-radius:10px; border:1px solid var(--line); background:var(--bg); outline:none; }
  .lookup input:focus { border-color:var(--brand); box-shadow:0 0 0 3px var(--brand-soft); }
  .blist { margin-top:18px; display:grid; gap:10px; }
  .bitem { display:flex; align-items:center; gap:14px; padding:12px 14px; border:1px solid var(--line); border-radius:12px; background:var(--bg); }
  .bitem .when { font-weight:600; }
  .bitem .meta { font-size:.82rem; color:var(--muted); }
  .bitem .grow { flex:1; min-width:0; }
  .pill { font-size:.75rem; font-weight:600; padding:3px 10px; border-radius:99px; background:var(--ok-bg); color:var(--ok); text-transform:capitalize; }
  .pill.cancelled { background:var(--bad-bg); color:var(--bad); }
  .bitem.cancelled .when { color:var(--muted); text-decoration:line-through; }
  .more { margin-top:14px; display:flex; justify-content:center; color:var(--muted); font-size:.9rem; }
  .sub { color:var(--muted); margin-top:4px; font-size:.92rem; }

  footer { color:var(--muted); font-size:.85rem; text-align:center; padding:32px 0 48px; }

  @media (max-width: 900px) {
    .grid { grid-template-columns:1fr; }
    .panel { position:static; }
  }
  @media (max-width: 520px) {
    .wrap { padding:0 16px; }
    .card-pad { padding:18px; }
    .header-note span { display:none; }
    .slots { grid-template-columns:repeat(2, minmax(0,1fr)); }
    .slot { padding:10px; }
    .slot .avatar { display:none; }
    .lookup { flex-direction:column; }
    .bitem { flex-wrap:wrap; }
  }
</style>
</head>
<body>
<header>
  <div class="wrap">
    <div class="brand">
      <div class="logo"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg></div>
      Wellspring Clinic
    </div>
    <div class="header-note"><i class="dot"></i><span>Online booking open</span></div>
  </div>
</header>

<main class="wrap">
  <section class="hero">
    <h1>Book your appointment</h1>
    <p>See every open time with our doctors, pick one that suits you, and get your confirmation instantly.</p>
    <div class="steps">
      <div class="step on" id="step1"><b>1</b>Choose a time</div>
      <div class="step" id="step2"><b>2</b>Your details</div>
      <div class="step" id="step3"><b>3</b>Confirmed</div>
    </div>
  </section>

  <div class="grid">
    <section class="card card-pad">
      <h2>Choose a time</h2>
      <div class="providers" id="providers"></div>
      <div class="days" id="days"></div>
      <div id="slots"><p class="empty">Loading available times…</p></div>
    </section>

    <aside class="card card-pad panel" id="panel">
      <div id="book-view">
        <h2>Your appointment</h2>
        <div class="summary" id="summary">Pick a time to get started.</div>
        <form id="book-form" autocomplete="on" novalidate>
          <label class="field"><span>Full name</span><input id="name" name="name" placeholder="e.g. Ada Obi" required></label>
          <label class="field"><span>Email</span><input id="email" name="email" type="email" placeholder="you@example.com" required></label>
          <button class="btn" id="book-btn" type="submit" disabled>Confirm booking</button>
          <p class="fine">You can cancel any time from “My bookings”.</p>
        </form>
        <div id="book-msg" class="msg"></div>
      </div>
      <div id="done-view" style="display:none"></div>
    </aside>
  </div>

  <section class="card card-pad">
    <div class="mine-head">
      <div>
        <h2>My bookings</h2>
        <p class="sub">Enter the email you booked with to see or cancel appointments.</p>
      </div>
      <form class="lookup" id="lookup-form">
        <input id="lookup-email" type="email" placeholder="you@example.com" required>
        <button class="btn ghost" type="submit">Find bookings</button>
      </form>
    </div>
    <div id="mine"></div>
  </section>
</main>

<footer>Wellspring Clinic · Appointments are 30 minutes · Times shown in your local time zone</footer>

<script>
const API = "/api";
const KEY = __API_KEY__;
const COLORS = ["#1f6f5c", "#d9774b", "#5b6bbf", "#a05195", "#2f8fb3", "#b5892e"];
let slots = [], provider = "", day = null, chosen = null, pending = null, cursor = null, lookupEmail = "";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dayKey = (d) => d.toLocaleDateString("en-CA");
const fmtDay = (d) => d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
const fmtTime = (d) => d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
const initials = (n) => n.replace(/^Dr\.?\s+/i, "").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
let providerOrder = [];
const colorFor = (n) => COLORS[Math.max(0, providerOrder.indexOf(n)) % COLORS.length];
const avatar = (n) => `<span class="avatar" style="background:${colorFor(n)}">${esc(initials(n))}</span>`;

async function api(path, options = {}) {
  const res = await fetch(API + path, { ...options, headers: { "X-API-Key": KEY, "Content-Type": "application/json", ...(options.headers || {}) } });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}
const sentence = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) + "." : "Something went wrong.");
function show(el, text, ok) { el.textContent = text; el.className = "msg show " + (ok ? "ok" : "bad"); }
function setStep(n) { [1, 2, 3].forEach((i) => $("step" + i).classList.toggle("on", i <= n)); }

async function loadSlots() {
  const { res, data } = await api("/slots");
  if (!res.ok) { $("slots").innerHTML = `<p class="empty">Couldn't load times: ${esc(data.error || res.status)}</p>`; return; }
  slots = data.slots.filter((s) => new Date(s.start) > new Date());
  providerOrder = [...new Set(data.slots.map((s) => s.provider))].sort();
  renderProviders(); renderDays(); renderSlots();
}

function visible() { return slots.filter((s) => !provider || s.provider === provider); }

function renderProviders() {
  const names = [...new Set(slots.map((s) => s.provider))].sort();
  $("providers").innerHTML = `<button class="chip all ${provider ? "" : "on"}" data-p="">All doctors</button>` +
    names.map((n) => `<button class="chip ${provider === n ? "on" : ""}" data-p="${esc(n)}">${avatar(n)}${esc(n)}</button>`).join("");
}

function renderDays() {
  const byDay = {};
  for (const s of visible()) (byDay[dayKey(new Date(s.start))] ||= []).push(s);
  const keys = Object.keys(byDay).sort();
  if (!keys.includes(day)) day = keys.find((k) => byDay[k].some((s) => s.available)) || keys[0] || null;
  $("days").innerHTML = keys.map((k) => {
    const d = new Date(byDay[k][0].start), free = byDay[k].filter((s) => s.available).length;
    return `<button class="daytab ${k === day ? "on" : ""} ${free ? "" : "full"}" data-day="${k}">
      <div class="dow">${d.toLocaleDateString(undefined, { weekday: "short" })}</div>
      <div class="dnum">${d.getDate()}</div>
      <div class="free">${free ? free + " free" : "Full"}</div></button>`;
  }).join("");
}

function renderSlots() {
  const list = visible().filter((s) => dayKey(new Date(s.start)) === day);
  if (!list.length) { $("slots").innerHTML = '<p class="empty">No upcoming times. Please check back soon.</p>'; return; }
  const groups = [["Morning", (h) => h < 12], ["Afternoon", (h) => h >= 12 && h < 17], ["Evening", (h) => h >= 17]];
  $("slots").innerHTML = groups.map(([label, test]) => {
    const g = list.filter((s) => test(new Date(s.start).getHours()));
    if (!g.length) return "";
    return `<div class="period"><span class="label">${label}</span><div class="slots">${g.map((s) => `
      <button class="slot ${chosen && chosen.id === s.id ? "on" : ""}" data-id="${esc(s.id)}" ${s.available ? "" : "disabled"} title="${esc(s.provider)}">
        ${avatar(s.provider)}<span><span class="time">${fmtTime(new Date(s.start))}</span><span class="who">${esc(s.provider)}${s.available ? "" : " · booked"}</span></span>
      </button>`).join("")}</div></div>`;
  }).join("");
}

function renderSummary() {
  const box = $("summary");
  if (!chosen) { box.className = "summary"; box.textContent = "Pick a time to get started."; $("book-btn").disabled = true; return; }
  const st = new Date(chosen.start), en = new Date(chosen.end);
  box.className = "summary on";
  box.innerHTML = `${avatar(chosen.provider)}<div><strong>${esc(chosen.provider)}</strong>${esc(fmtDay(st))}<br>${esc(fmtTime(st))} – ${esc(fmtTime(en))}</div>`;
  $("book-btn").disabled = false;
}

$("providers").addEventListener("click", (e) => {
  const b = e.target.closest(".chip"); if (!b) return;
  provider = b.dataset.p;
  if (chosen && provider && chosen.provider !== provider) { chosen = null; renderSummary(); setStep(1); }
  renderProviders(); renderDays(); renderSlots();
});
$("days").addEventListener("click", (e) => {
  const b = e.target.closest(".daytab"); if (!b) return;
  day = b.dataset.day; renderDays(); renderSlots();
});
$("slots").addEventListener("click", (e) => {
  const b = e.target.closest(".slot"); if (!b || b.disabled) return;
  chosen = slots.find((s) => s.id === b.dataset.id); pending = null;
  $("book-msg").className = "msg";
  renderSlots(); renderSummary(); setStep(2);
  if (window.matchMedia("(max-width: 900px)").matches) $("panel").scrollIntoView({ behavior: "smooth", block: "start" });
  $("name").focus({ preventScroll: true });
});

$("book-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!chosen) return;
  const slot = chosen;
  const body = { slot_id: slot.id, name: $("name").value, email: $("email").value };
  // One idempotency key per booking attempt, reused if the same details are retried.
  const bodyText = JSON.stringify(body);
  if (!pending || pending.body !== bodyText) pending = { body: bodyText, key: crypto.randomUUID() };
  $("book-btn").disabled = true; $("book-btn").textContent = "Booking…";
  try {
    const { res, data } = await api("/bookings", { method: "POST", body: bodyText, headers: { "Idempotency-Key": pending.key } });
    if (res.status === 201) { pending = null; showConfirmation(data, slot); }
    else if (res.status === 429) show($("book-msg"), `Too many attempts. Please wait ${res.headers.get("Retry-After") || 60} seconds and try again.`, false);
    else {
      show($("book-msg"), res.status === 409 ? "Sorry, someone just booked that time. Please pick another." : sentence(data.error), false);
      if (res.status === 409) { pending = null; chosen = null; renderSummary(); setStep(1); }
    }
  } catch {
    show($("book-msg"), "Network problem. Press the button again: you won't be booked twice.", false);
  } finally {
    $("book-btn").textContent = "Confirm booking";
    $("book-btn").disabled = !chosen;
    await loadSlots();
  }
});

function showConfirmation(b, slot) {
  const st = new Date(slot.start), en = new Date(slot.end);
  setStep(3);
  chosen = null;
  $("book-view").style.display = "none";
  $("done-view").style.display = "block";
  $("done-view").innerHTML = `
    <div class="confirmed">
      <div class="tick"><svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></div>
      <h2>You're booked</h2>
      <p class="sub">See you on ${esc(fmtDay(st))}.</p>
    </div>
    <dl class="ticket">
      <div><dt>Doctor</dt><dd>${esc(slot.provider)}</dd></div>
      <div><dt>Time</dt><dd>${esc(fmtTime(st))} – ${esc(fmtTime(en))}</dd></div>
      <div><dt>Name</dt><dd>${esc(b.name)}</dd></div>
      <div><dt>Email</dt><dd>${esc(b.email)}</dd></div>
      <div><dt>Status</dt><dd><span class="pill">${esc(b.status)}</span></dd></div>
      <div><dt>Booking ID</dt><dd><code>${esc(b.id)}</code></dd></div>
    </dl>
    <button class="btn ghost" id="again" style="width:100%">Book another appointment</button>`;
  $("lookup-email").value = b.email;
}

$("done-view").addEventListener("click", (e) => {
  if (e.target.id !== "again") return;
  $("done-view").style.display = "none"; $("book-view").style.display = "block";
  $("book-msg").className = "msg"; renderSummary(); renderSlots(); setStep(1);
});

async function loadMine(more) {
  if (!more) { cursor = null; $("mine").innerHTML = ""; }
  const qs = new URLSearchParams({ email: lookupEmail, limit: "5" });
  if (cursor) qs.set("cursor", cursor);
  const { res, data } = await api("/bookings?" + qs);
  if (!res.ok) { $("mine").innerHTML = `<div class="msg show bad">${esc(sentence(data.error))}</div>`; return; }
  cursor = data.next_cursor;
  if (!more && !data.bookings.length) { $("mine").innerHTML = '<p class="empty">No bookings found for that email.</p>'; return; }
  if (!more) $("mine").innerHTML = '<div class="blist" id="blist"></div><div class="more" id="more-row"></div>';
  const byId = Object.fromEntries(slots.map((s) => [s.id, s]));
  $("blist").insertAdjacentHTML("beforeend", data.bookings.map((b) => {
    const s = byId[b.slot_id];
    const when = s ? `${fmtDay(new Date(s.start))}, ${fmtTime(new Date(s.start))}` : `Slot ${b.slot_id}`;
    return `<div class="bitem ${b.status === "cancelled" ? "cancelled" : ""}">${s ? avatar(s.provider) : ""}
      <div class="grow"><div class="when">${esc(when)}</div><div class="meta">${esc(s ? s.provider + " · " : "")}<code>${esc(b.id)}</code></div></div>
      <span class="pill ${b.status === "cancelled" ? "cancelled" : ""}">${esc(b.status)}</span>
      ${b.status === "confirmed" ? `<button class="btn ghost small" data-cancel="${esc(b.id)}">Cancel</button>` : ""}</div>`;
  }).join(""));
  $("more-row").innerHTML = cursor ? '<button class="btn ghost small" id="more">Show more</button>' : "That's everything.";
}

$("lookup-form").addEventListener("submit", (e) => { e.preventDefault(); lookupEmail = $("lookup-email").value.trim(); loadMine(false); });
$("mine").addEventListener("click", async (e) => {
  if (e.target.id === "more") return loadMine(true);
  const id = e.target.dataset.cancel;
  if (!id || !confirm("Cancel this appointment?")) return;
  e.target.disabled = true; e.target.textContent = "Cancelling…";
  const { res, data } = await api("/bookings/" + encodeURIComponent(id), { method: "DELETE" });
  if (!res.ok) alert(sentence(data.error));
  await loadSlots();
  loadMine(false);
});

loadSlots();
</script>
</body>
</html>
"""


def render_page(api_key: str) -> str:
    # The page is a client of the API, so it needs the key. json.dumps + "<\/" escaping
    # keeps the value safe inside the <script> tag.
    return _PAGE.replace("__API_KEY__", json.dumps(api_key).replace("</", "<\\/"))
