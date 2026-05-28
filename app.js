/* ═══════════════════════════════════════════════════════════
   app.js  —  Dhanak Banquet Hall Manager  v3.0
   ═══════════════════════════════════════════════════════════ */

// ── App state ─────────────────────────────────────────────────
const state = {
  page:     "bookings",
  bookings: [],
  search:   "",
  filter:   "all",
  editId:   null,
};

// ── Dark mode init ───────────────────────────────────────────
(function initDarkMode() {
  const saved = localStorage.getItem("dhanak_theme") || "dark";
  document.documentElement.setAttribute("data-theme", saved);
})();

function toggleDarkMode(enable) {
  const theme = enable ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("dhanak_theme", theme);
  dmSync();
}

function dmSync() {
  const on    = localStorage.getItem("dhanak_theme") === "dark";
  const cb    = document.getElementById("dm-cb");
  const track = document.getElementById("dm-track");
  const thumb = document.getElementById("dm-thumb");
  if (cb)    cb.checked             = on;
  if (track) track.style.background = on ? "#C6A058" : "rgba(0,0,0,0.15)";
  if (thumb) thumb.style.left       = on ? "22px"    : "2px";
}

// ── Custom Select helpers ─────────────────────────────────────
function csGet(id) {
  const el = document.getElementById(id);
  if (!el) return "";
  return el.dataset.value || "";
}
function csSet(id, val) {
  const el = document.getElementById(id);
  if (!el || !el.classList.contains("csel")) return;
  const opt = el.querySelector(`.csel-opt[data-value="${CSS.escape(val)}"]`);
  const label = opt ? opt.textContent : val;
  el.dataset.value = val;
  const valEl = el.querySelector(".csel-val");
  if (valEl) valEl.textContent = label;
  el.querySelectorAll(".csel-opt").forEach(o =>
    o.classList.toggle("active", o.dataset.value === val));
}
function initCustomSelects() {
  // IMPORTANT: skip .cal-csel (Calendar tab) and .dp-csel (date-picker) —
  // they manage their own open/close lifecycle in _buildCalendarSelects()
  // and renderDatePicker(). Without this exclusion, duplicate handlers
  // cause a double-toggle (open → instantly close).
  document.querySelectorAll(".csel:not(.cal-csel):not(.dp-csel)").forEach(sel => {
    if (sel._cselInit) return;
    sel._cselInit = true;
    const trigger = sel.querySelector(".csel-trigger");
    const list    = sel.querySelector(".csel-list");
    if (!trigger || !list) return;

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const wasOpen = sel.classList.contains("open");
      // close all others (but NOT calendar/datepicker csels)
      document.querySelectorAll(".csel.open:not(.cal-csel):not(.dp-csel)").forEach(s => s.classList.remove("open"));
      if (!wasOpen) sel.classList.add("open");
    });

    list.querySelectorAll(".csel-opt").forEach(opt => {
      opt.addEventListener("click", (e) => {
        e.stopPropagation();
        csSet(sel.id, opt.dataset.value);
        sel.classList.remove("open");
        const cb = sel.dataset.onchange;
        if (cb && window[cb]) window[cb]();
      });
    });
  });

  // close on outside click — exclude calendar/datepicker csels
  if (!document._cselHandler) {
    document._cselHandler = true;
    document.addEventListener("click", () =>
      document.querySelectorAll(".csel.open:not(.cal-csel):not(.dp-csel)").forEach(s => s.classList.remove("open")));
  }
}


// ── Avatar color cycling ──────────────────────────────────────
const AV_CLASSES = ["av-orange","av-blue","av-green","av-purple","av-pink","av-teal","av-gray"];
const avColor = (name) => {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffffffff;
  return AV_CLASSES[Math.abs(h) % AV_CLASSES.length];
};
const initials = (name) => name.trim().split(/\s+/).map(w => w[0]).join("").slice(0,2).toUpperCase();

// ── Format helpers ────────────────────────────────────────────
const fmt = {
  rupees: (n) => "Rs.\u202f" + Number(n).toLocaleString("en-PK"),
  date:   (s) => {
    if (!s) return "—";
    const d = new Date(s + "T00:00:00");
    return d.toLocaleDateString("en-GB", { day:"numeric", month:"short", year:"numeric" });
  },
  remaining: (n) => n <= 0
    ? '<span style="color:var(--text-faint)">Rs.\u202f0</span>'
    : `<span style="color:#A32D2D">${fmt.rupees(n)}</span>`,
};

const evBadge = (ev) => `<span class="ev-badge ev-${ev || 'Other'}">${ev || "Other"}</span>`;
const stBadge = (st) => `<span class="st-badge st-${st}"><span class="dot"></span>${st.charAt(0)+st.slice(1).toLowerCase()}</span>`;
// Menu type badge: FPH = Food Per Head, SPH = Sitting Per Head
const menuBadge = (m) => {
  const label = m === "FPH" ? "FPH" : m === "SPH" ? "SPH" : (m || "—");
  return `<span class="st-badge" style="background:var(--primary-light,#ede9fe);color:var(--primary,#4F46E5)">${label}</span>`;
};

const ICON = {
  edit:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`,
  clear:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`,
  cancel:  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  receipt: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16l3-2 2 2 2-2 2 2 2-2 3 2V4a2 2 0 0 0-2-2z"/><line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="13" x2="16" y2="13"/></svg>`,
  plus:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
  fph:     `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 12h6M9 16h4"/></svg>`,
};

// ════════════════════════════════════════════════════════════
//  QWebChannel bootstrap
// ════════════════════════════════════════════════════════════
let backend = null;

document.addEventListener("DOMContentLoaded", () => {
  if (typeof QWebChannel !== "undefined" && typeof qt !== "undefined") {
    new QWebChannel(qt.webChannelTransport, (channel) => {
      backend = channel.objects.backend;
      initApp();
    });
  } else {
    backend = makeMockBackend();
    initApp();
  }
});

// ════════════════════════════════════════════════════════════
//  App init
// ════════════════════════════════════════════════════════════
function initApp() {
  setupNav();
  setupSearch();
  setupFilters();
  const dateBtn = document.getElementById("f-date-btn");
  if (dateBtn) {
    dateBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const popup = document.getElementById("date-picker-popup");
      if (popup && !popup.classList.contains("hidden")) closeDatePicker();
      else openDatePicker();
    });
  }
  navigateTo("bookings");
}

function setupNav() {
  document.querySelectorAll(".nav-item").forEach(el => {
    el.addEventListener("click", () => navigateTo(el.dataset.page));
  });
}

const PAGE_META = {
  bookings:  { title: "Upcoming",          sub: "Bookings from 2026 onwards" },
  calendar:  { title: "Calendar",         sub: "Availability overview by month" },
  upcoming:  { title: "All Bookings",     sub: "Complete booking history with actions" },
  customers: { title: "Customers",        sub: "All registered customers" },
  history:   { title: "History & Search", sub: "Customer history and advanced search" },
  reports:   { title: "Reports",          sub: "Revenue and booking insights" },
  ai:        { title: "Shift Checker",     sub: "Check date availability by voice or text" },
  settings:    { title: "Settings",         sub: "Manage application preferences" },
  "fph-menu":    { title: "FPH Menu Order",    sub: "Select Food-Per-Head items for a booking" },
  "fph-records": { title: "FPH Menu Records",  sub: "All saved Food-Per-Head orders" },
};

function navigateTo(page) {
  state.page = page;
  document.querySelectorAll(".nav-item").forEach(el =>
    el.classList.toggle("active", el.dataset.page === page));
  const meta = PAGE_META[page] || { title: page, sub: "" };
  document.getElementById("page-title").textContent = meta.title;
  document.getElementById("page-sub").textContent   = meta.sub;
  document.querySelectorAll(".page").forEach(el =>
    el.classList.toggle("active", el.id === `page-${page}`));
  renderTopbarActions(page);
  switch (page) {
    case "bookings":  loadBookings();   break;
    case "calendar":  loadCalendar();   break;
    case "upcoming":  loadUpcoming();   break;
    case "customers": loadCustomers();  break;
    case "history":   loadHistory();    break;
    case "reports":   loadReports();    break;
    case "settings":    renderSettings();  break;
    case "fph-menu":    loadFphMenu();     break;
    case "fph-records": loadFphRecords();  break;
  }
}

function renderTopbarActions(page) {
  const el = document.getElementById("topbar-actions");
  if (page === "bookings") {
    el.innerHTML = `<button class="btn btn-primary" onclick="openModal()">${ICON.plus} New Booking</button>`;
  } else if (page === "fph-menu") {
    el.innerHTML = `<button class="btn btn-ghost" onclick="resetFphForm()" style="margin-right:8px;">Reset Form</button>
      <button class="btn btn-primary" onclick="saveFphMenu()">${ICON.fph} Save &amp; Print</button>`;
  } else if (page === "fph-records") {
    el.innerHTML = `<button class="icon-btn" title="Reload" onclick="loadFphRecords()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
    </button>`;
  } else {
    el.innerHTML = "";
  }
}

// ════════════════════════════════════════════════════════════
//  CALENDAR  (Fix #4: month + year dropdowns)
// ════════════════════════════════════════════════════════════
const MONTH_NAMES = ["January","February","March","April","May","June",
                     "July","August","September","October","November","December"];

const calState = {
  year:  new Date().getFullYear(),
  month: new Date().getMonth() + 1,
};

function loadCalendar() {
  const now = new Date();
  if (!calState.year)  calState.year  = now.getFullYear();
  if (!calState.month) calState.month = now.getMonth() + 1;
  _buildCalendarSelects();
  bindCalendarControls();
  renderCalendar(calState.year, calState.month);
}

function _buildCalendarSelects() {
  const mCsel = document.getElementById("cal-month-csel");
  const yCsel = document.getElementById("cal-year-csel");
  if (!mCsel || !yCsel) return;
  const mList = document.getElementById("cal-month-list");
  const yList = document.getElementById("cal-year-list");

  if (!mCsel._built) {
    mCsel._built = true;
    mList.innerHTML = MONTH_NAMES.map((m, i) =>
      `<div class="csel-opt" data-value="${i+1}">${m}</div>`).join("");
    mList.addEventListener("click", (e) => {
      const opt = e.target.closest(".csel-opt");
      if (!opt) return;
      mCsel.querySelector(".csel-val").textContent = MONTH_NAMES[parseInt(opt.dataset.value) - 1];
      mCsel.classList.remove("open");
      _setCalState(calState.year, parseInt(opt.dataset.value));
    });
    mCsel.querySelector(".csel-trigger").addEventListener("click", (e) => {
      e.stopPropagation();
      yCsel.classList.remove("open");
      mCsel.classList.toggle("open");
    });
  }
  mCsel.querySelector(".csel-val").textContent = MONTH_NAMES[calState.month - 1];

  const cy = new Date().getFullYear();
  if (!yCsel._built) {
    yCsel._built = true;
    let opts = "";
    for (let y = cy - 5; y <= cy + 5; y++) opts += `<div class="csel-opt" data-value="${y}">${y}</div>`;
    yList.innerHTML = opts;
    yList.addEventListener("click", (e) => {
      const opt = e.target.closest(".csel-opt");
      if (!opt) return;
      yCsel.querySelector(".csel-val").textContent = opt.dataset.value;
      yCsel.classList.remove("open");
      _setCalState(parseInt(opt.dataset.value), calState.month);
    });
    yCsel.querySelector(".csel-trigger").addEventListener("click", (e) => {
      e.stopPropagation();
      mCsel.classList.remove("open");
      yCsel.classList.toggle("open");
    });
  }
  yCsel.querySelector(".csel-val").textContent = calState.year;

  if (!mCsel._outsideBound) {
    mCsel._outsideBound = true;
    document.addEventListener("click", (e) => {
      if (!mCsel.contains(e.target)) mCsel.classList.remove("open");
      if (!yCsel.contains(e.target)) yCsel.classList.remove("open");
    });
  }
}

function bindCalendarControls() {
  const prev  = document.getElementById("cal-prev-month");
  const next  = document.getElementById("cal-next-month");
  if (prev && !prev._bound) {
    prev._bound = true;
    prev.addEventListener("click", () => {
      let { year, month } = calState;
      if (--month < 1) { month = 12; year--; }
      _setCalState(year, month);
    });
  }
  if (next && !next._bound) {
    next._bound = true;
    next.addEventListener("click", () => {
      let { year, month } = calState;
      if (++month > 12) { month = 1; year++; }
      _setCalState(year, month);
    });
  }
}

function _setCalState(year, month) {
  calState.year  = year;
  calState.month = month;
  const mCsel = document.getElementById("cal-month-csel");
  const yCsel = document.getElementById("cal-year-csel");
  if (mCsel) mCsel.querySelector(".csel-val").textContent = MONTH_NAMES[month - 1];
  if (yCsel) yCsel.querySelector(".csel-val").textContent = year;
  renderCalendar(year, month);
}

function renderCalendar(year, month) {
  if (!backend) return;
  const grid = document.getElementById("calendar-grid");
  if (!grid) return;

  backend.get_month_availability(year, month, (json) => {
    let data;
    try { data = JSON.parse(json); } catch { return; }
    const days = data.days || {};

    const firstDay    = new Date(year, month - 1, 1);
    const startWd     = (firstDay.getDay() + 6) % 7;  // Mon = 0
    const daysInMonth = new Date(year, month, 0).getDate();

    const ALL_SHIFTS = ["day 1","day 2","night 1","night 2"];

    // Normalize a shift string from DB into one of the 4 canonical keys.
    // DB may store "Day 1", "Day 2", "Night 1", "Night 2" (new format) or
    // legacy single-word values like "Day", "Evening", "Night", "Afternoon".
    function normalizeShift(s) {
      const t = (s || "").toLowerCase().trim();
      // already canonical
      if (t === "day 1")   return "day 1";
      if (t === "day 2")   return "day 2";
      if (t === "night 1") return "night 1";
      if (t === "night 2") return "night 2";
      // legacy mappings
      if (t === "day" || t === "morning")           return "day 1";
      if (t === "afternoon" || t === "lunch")        return "day 2";
      if (t === "evening" || t === "dinner")         return "night 1";
      if (t === "night" || t === "late night")       return "night 2";
      return t; // fallback — will just not match, which is safe
    }

    let cells = [];
    const wd = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
    cells.push(`<div class="cal-header-row">${wd.map(w => `<div class="cal-header-cell">${w}</div>`).join("")}</div>`);

    let row = [];
    for (let i = 0; i < startWd; i++) row.push(`<div class="cal-cell empty"></div>`);

    for (let d = 1; d <= daysInMonth; d++) {
      const key    = String(d);
      const meta   = days[key] || { shifts: [], count: 0 };
      const booked = meta.count > 0;
      const shifts  = (meta.shifts || []);

      const takenSet = new Set(shifts.map(normalizeShift));
      // 4 segments: Day 1, Day 2, Night 1, Night 2
      const segs = ALL_SHIFTS.map(s => takenSet.has(s));

      const tooltip = booked
        ? `${d} ${MONTH_NAMES[month-1]}: ${meta.shifts.join(", ")} booked`
        : `${d} ${MONTH_NAMES[month-1]}: All shifts free`;

      row.push(`
        <div class="cal-cell${booked ? " booked" : ""}" data-date="${year}-${String(month).padStart(2,"0")}-${String(d).padStart(2,"0")}" title="${tooltip}">
          <div class="cal-pill">
            <div class="cal-shift-row">
              <div class="shift-box${segs[0] ? " filled" : ""}"></div>
              <div class="shift-box${segs[1] ? " filled" : ""}"></div>
            </div>
            <div class="cal-day-label">${d}</div>
            <div class="cal-shift-row">
              <div class="shift-box${segs[2] ? " filled" : ""}"></div>
              <div class="shift-box${segs[3] ? " filled" : ""}"></div>
            </div>
          </div>
        </div>`);

      if (row.length === 7 || d === daysInMonth) {
        cells.push(`<div class="cal-row">${row.join("")}</div>`);
        row = [];
      }
    }
    grid.innerHTML = cells.join("");

    // Individual day click — replace handler each render to avoid accumulation
    if (grid._calClick) grid.removeEventListener("click", grid._calClick);
    grid._calClick = function(e) {
      const cell = e.target.closest(".cal-cell:not(.empty)");
      if (!cell) return;
      grid.querySelectorAll(".cal-cell.selected").forEach(c => c.classList.remove("selected"));
      cell.classList.add("selected");
    };
    grid.addEventListener("click", grid._calClick);
  });
}

// ════════════════════════════════════════════════════════════
//  MINI DATE PICKER
// ════════════════════════════════════════════════════════════
const dpState = { year: 0, month: 0 };

function openDatePicker() {
  const popup = document.getElementById("date-picker-popup");
  const input = document.getElementById("f-date");
  if (!popup || !input) return;
  const now = new Date();
  let y = now.getFullYear(), m = now.getMonth() + 1;
  if (/^\d{4}-\d{2}-\d{2}$/.test(input.value)) {
    const d = new Date(input.value + "T00:00:00");
    if (!isNaN(d)) { y = d.getFullYear(); m = d.getMonth() + 1; }
  }
  dpState.year = y; dpState.month = m;
  popup.classList.remove("hidden");
  renderDatePicker();
  setTimeout(() => document.addEventListener("click", _dpOutsideHandler), 0);
}

function closeDatePicker() {
  const popup = document.getElementById("date-picker-popup");
  if (popup) popup.classList.add("hidden");
  document.removeEventListener("click", _dpOutsideHandler);
}

function _dpOutsideHandler(e) {
  const popup = document.getElementById("date-picker-popup");
  const btn   = document.getElementById("f-date-btn");
  if (popup && !popup.contains(e.target) && e.target !== btn && !btn.contains(e.target))
    closeDatePicker();
}

function renderDatePicker() {
  const popup = document.getElementById("date-picker-popup");
  if (!popup) return;
  const { year, month } = dpState;
  const firstDay    = new Date(year, month - 1, 1);
  const startWd     = (firstDay.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month, 0).getDate();
  const today       = new Date().toISOString().split("T")[0];
  const selected    = (document.getElementById("f-date") || {}).value || "";

  let cells = "";
  for (let i = 0; i < startWd; i++) cells += `<span class="dp-day empty"></span>`;
  for (let d = 1; d <= daysInMonth; d++) {
    const iso = `${year}-${String(month).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
    const cls = iso === selected ? " selected" : iso === today ? " today" : "";
    cells += `<span class="dp-day${cls}" data-date="${iso}">${d}</span>`;
  }

  // Build month/year custom selects for DatePicker (uses .csel pattern — no native <select>)
  const dpMonthItems = MONTH_NAMES.map((m, i) =>
    `<div class="csel-opt${i+1 === month ? " active" : ""}" data-value="${i+1}">${m}</div>`).join("");
  const dpCY = new Date().getFullYear();
  let dpYearItems = "";
  for (let y = dpCY - 5; y <= dpCY + 5; y++)
    dpYearItems += `<div class="csel-opt${y === year ? " active" : ""}" data-value="${y}">${y}</div>`;

  popup.innerHTML = `
    <div class="dp-header">
      <button type="button" class="dp-nav" id="dp-prev">&#8249;</button>
      <div class="csel dp-csel" id="dp-month-csel" data-value="${month}" style="width:110px;">
        <div class="csel-trigger"><span class="csel-val">${MONTH_NAMES[month-1]}</span><span class="csel-arrow">&#9660;</span></div>
        <div class="csel-list">${dpMonthItems}</div>
      </div>
      <div class="csel dp-csel" id="dp-year-csel" data-value="${year}" style="width:74px;">
        <div class="csel-trigger"><span class="csel-val">${year}</span><span class="csel-arrow">&#9660;</span></div>
        <div class="csel-list">${dpYearItems}</div>
      </div>
      <button type="button" class="dp-nav" id="dp-next">&#8250;</button>
    </div>
    <div class="dp-weekdays"><span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span><span>Su</span></div>
    <div class="dp-grid">${cells}</div>`;

  // ── Prev / Next arrows ──
  popup.querySelector("#dp-prev").addEventListener("click", (e) => {
    e.stopPropagation();
    if (--dpState.month < 1) { dpState.month = 12; dpState.year--; }
    renderDatePicker();
  });
  popup.querySelector("#dp-next").addEventListener("click", (e) => {
    e.stopPropagation();
    if (++dpState.month > 12) { dpState.month = 1; dpState.year++; }
    renderDatePicker();
  });

  // ── Wire up custom-select month/year triggers & options ──
  popup.querySelectorAll(".dp-csel").forEach(sel => {
    const trigger = sel.querySelector(".csel-trigger");
    const list    = sel.querySelector(".csel-list");
    if (!trigger || !list) return;

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const wasOpen = sel.classList.contains("open");
      // close the other dp-csel if open
      popup.querySelectorAll(".dp-csel.open").forEach(s => s.classList.remove("open"));
      if (!wasOpen) sel.classList.add("open");
    });

    list.querySelectorAll(".csel-opt").forEach(opt => {
      opt.addEventListener("click", (e) => {
        e.stopPropagation();
        sel.classList.remove("open");
        const val = parseInt(opt.dataset.value);
        if (sel.id === "dp-month-csel") {
          dpState.month = val;
        } else {
          dpState.year = val;
        }
        renderDatePicker();
      });
    });
  });

  // ── Day cell clicks ──
  popup.querySelectorAll(".dp-day[data-date]").forEach(el => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      const inp = document.getElementById("f-date");
      if (inp) inp.value = el.dataset.date;
      closeDatePicker();
    });
  });
}

// ════════════════════════════════════════════════════════════
//  SEARCH & FILTER
// ════════════════════════════════════════════════════════════
function setupSearch() {
  const inp = document.getElementById("search-input");
  if (!inp) return;
  let timer;
  inp.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => { state.search = inp.value; loadBookings(); }, 250);
  });
}

function setupFilters() {
  document.getElementById("filter-chips").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    document.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    state.filter = chip.dataset.filter;
    loadBookings();
  });
}

// ════════════════════════════════════════════════════════════
//  BOOKINGS PAGE
// ════════════════════════════════════════════════════════════
function loadBookings() {
  if (!backend) return;
  backend.get_bookings_filtered(state.search, state.filter, (json) => {
    state.bookings = JSON.parse(json);
    renderStats();
    // Upcoming tab: only show 2026 and later bookings
    const upcoming = state.bookings.filter(b => (b.date || "") >= "2026-01-01");
    renderBookingsTable(upcoming);
  });
}

function renderStats() {
  if (!backend) return;
  backend.get_stats((json) => {
    const s = JSON.parse(json);
    const nextLabel = s.next_date ? fmt.date(s.next_date) : "None";
    document.getElementById("stats-row").innerHTML = `
      <div class="stat-card">
        <div class="stat-label">Total bookings</div>
        <div class="stat-value">${s.total}</div>
        <span class="stat-badge badge-blue">Active</span>
      </div>
      <div class="stat-card">
        <div class="stat-label">Pending clearance</div>
        <div class="stat-value">${s.pending}</div>
        <span class="stat-badge badge-amber">${s.pending > 0 ? "Needs attention" : "All clear"}</span>
      </div>
      <div class="stat-card">
        <div class="stat-label">Revenue (cleared)</div>
        <div class="stat-value" style="font-size:19px">${fmt.rupees(s.revenue)}</div>
        <span class="stat-badge badge-green">Collected</span>
      </div>
      <div class="stat-card">
        <div class="stat-label">Upcoming (30 days)</div>
        <div class="stat-value">${s.upcoming}</div>
        <span class="stat-badge badge-gray">Next: ${nextLabel}</span>
      </div>`;
  });
}

// Fix #8: Rate + Type columns in bookings table
function renderBookingsTable(bookings) {
  const tbody = document.getElementById("bookings-tbody");
  document.getElementById("booking-count").textContent =
    `${bookings.length} result${bookings.length !== 1 ? "s" : ""}`;

  if (bookings.length === 0) {
    tbody.innerHTML = `<tr><td colspan="13"><div class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
      <p>No bookings found</p></div></td></tr>`;
    document.getElementById("table-footer").innerHTML = "";
    return;
  }

  tbody.innerHTML = bookings.map(b => `
    <tr>
      <td class="td-id">#${b.id}</td>
      <td><div class="td-name">
        <div class="av ${avColor(b.name)}">${initials(b.name)}</div>
        ${escHtml(b.name)}
      </div></td>
      <td>${fmt.date(b.date)}</td>
      <td>${escHtml(b.shift)}</td>
      <td>${evBadge(b.event)}</td>
      <td>${menuBadge(b.menu_type)}</td>
      <td class="mono">${Number(b.persons).toLocaleString()}</td>
      <td class="mono">${fmt.rupees(b.rate || 0)}</td>
      <td class="mono">${fmt.rupees(b.total)}</td>
      <td class="mono">${fmt.rupees(b.advance)}</td>
      <td>${fmt.remaining(b.remaining)}</td>
      <td>${stBadge(b.status)}</td>
      <td>
        <div class="row-actions">
          <button class="icon-btn" title="Edit" onclick="openEditModal(${b.id})">${ICON.edit}</button>
          <button class="icon-btn" title="Booking receipt" onclick="printReceipt(${b.id})">${ICON.receipt}</button>
          ${b.status === "CLEARED"
            ? `<button class="icon-btn" title="Clearance receipt (A4)" onclick="printClearance(${b.id})">${ICON.clear}</button>`
            : `<button class="icon-btn" title="Mark cleared" onclick="markCleared(${b.id})">${ICON.clear}</button>`}
          ${b.menu_type === "FPH" ? `<button class="icon-btn" title="FPH Menu Order" style="color:var(--primary)" onclick="openFphForBooking(${b.id},'${b.name.replace(/'/g,"\\'")}')">${ICON.fph}</button>` : ""}
          ${b.status !== "CANCELLED" ? `<button class="icon-btn danger" title="Cancel" onclick="cancelBooking(${b.id})">${ICON.cancel}</button>` : ""}
        </div>
      </td>
    </tr>`).join("");

  document.getElementById("table-footer").innerHTML =
    `<span>Showing ${bookings.length} booking${bookings.length !== 1 ? "s" : ""}</span>`;
}

// ════════════════════════════════════════════════════════════
//  RECEIPTS
// ════════════════════════════════════════════════════════════
function printReceipt(id) {
  if (!backend) { toast("Backend not ready", "error"); return; }
  backend.print_booking_receipt(id, (json) => {
    let r; try { r = JSON.parse(json); } catch { toast("Receipt error: bad response", "error"); return; }
    if (r.success) toast("Customer & office copies sent to printer", "success");
    else toast("Receipt error: " + r.error, "error");
  });
}

// ── Charges modal — shown before any clearance action ──────────────────
function showChargesModal(id, onConfirm) {
  // Remove any existing charges modal
  const existing = document.getElementById("charges-modal-overlay");
  if (existing) existing.remove();

  const b = state.bookings.find(x => x.id === id) || {};
  const gross = ((b.persons || 0) * (b.rate || 0));
  const adv   = b.advance || 0;
  const remaining = Math.max(0, gross - adv);

  const overlay = document.createElement("div");
  overlay.id = "charges-modal-overlay";
  overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;display:flex;align-items:center;justify-content:center;";

  overlay.innerHTML = `
    <div style="background:#fff;border-radius:14px;padding:32px 36px;width:440px;max-width:95vw;box-shadow:0 8px 40px rgba(0,0,0,.3);font-family:Georgia,serif;">
      <h2 style="margin:0 0 6px;font-size:20px;color:#C9A84C;">💳 Clearance — Booking #${id}</h2>
      <p style="margin:0 0 18px;font-size:13px;color:#6B7280;">Enter any discount or extra seating charge before printing the receipt.</p>

      <div style="background:#f9f5ee;border-radius:8px;padding:12px 16px;margin-bottom:20px;font-size:14px;color:#374151;">
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;"><span>Gross Total</span><b>Rs. ${fmt.rupees(gross)}</b></div>
        <div style="display:flex;justify-content:space-between;"><span>Advance Paid</span><b style="color:#16A34A;">Rs. ${fmt.rupees(adv)}</b></div>
      </div>

      <div style="margin-bottom:14px;">
        <label style="display:block;font-size:13px;color:#D97706;font-weight:bold;margin-bottom:4px;">Discount (Rs.) <span style="font-weight:normal;color:#9CA3AF;">— leave 0 if none</span></label>
        <input id="cm-discount" type="number" min="0" value="0"
          style="width:100%;padding:9px 12px;border:1.5px solid #E5E7EB;border-radius:8px;font-size:15px;font-family:Georgia,serif;outline:none;"
          oninput="cmRecalc(${id})" />
        <div id="cm-disc-pct" style="font-size:12px;color:#D97706;margin-top:3px;"></div>
      </div>

      <div style="margin-bottom:22px;">
        <label style="display:block;font-size:13px;color:#4F46E5;font-weight:bold;margin-bottom:4px;">Extra Seats (count) <span style="font-weight:normal;color:#9CA3AF;">— Rs. 200/seat, leave 0 if none</span></label>
        <input id="cm-seats" type="number" min="0" value="0"
          style="width:100%;padding:9px 12px;border:1.5px solid #E5E7EB;border-radius:8px;font-size:15px;font-family:Georgia,serif;outline:none;"
          oninput="cmRecalc(${id})" />
        <div id="cm-seat-total" style="font-size:12px;color:#4F46E5;margin-top:3px;"></div>
      </div>

      <div id="cm-net-row" style="background:#f0fdf4;border-radius:8px;padding:10px 16px;margin-bottom:22px;font-size:15px;font-weight:bold;display:flex;justify-content:space-between;color:#065F46;">
        <span>Net Payable</span><span id="cm-net-val">Rs. ${fmt.rupees(remaining)}</span>
      </div>

      <div style="display:flex;gap:12px;">
        <button onclick="document.getElementById('charges-modal-overlay').remove()"
          style="flex:1;padding:10px;background:#F3F4F6;border:none;border-radius:8px;font-size:15px;font-family:Georgia,serif;cursor:pointer;color:#6B7280;">Cancel</button>
        <button id="cm-confirm-btn"
          style="flex:2;padding:10px;background:#C9A84C;border:none;border-radius:8px;font-size:15px;font-family:Georgia,serif;cursor:pointer;color:#fff;font-weight:bold;"
          onclick="cmConfirm(${id})">✅ Confirm &amp; Print Receipt</button>
      </div>
    </div>`;

  // Store the callback
  window._cmCallback = onConfirm;
  window._cmGross    = gross;
  window._cmAdv      = adv;
  document.body.appendChild(overlay);

  // Focus discount field
  setTimeout(() => document.getElementById("cm-discount")?.focus(), 50);
}

function cmRecalc(id) {
  const gross    = window._cmGross || 0;
  const adv      = window._cmAdv  || 0;
  const discount = parseFloat(document.getElementById("cm-discount")?.value) || 0;
  const seats    = parseInt(document.getElementById("cm-seats")?.value)  || 0;
  const seating  = seats * 200;
  const net      = Math.max(0, gross - discount + seating);

  const pctEl = document.getElementById("cm-disc-pct");
  if (pctEl) pctEl.textContent = (discount > 0 && gross > 0)
    ? `${((discount / gross) * 100).toFixed(1)}% discount applied`
    : "";

  const seatEl = document.getElementById("cm-seat-total");
  if (seatEl) seatEl.textContent = seats > 0 ? `${seats} × Rs. 200 = Rs. ${fmt.rupees(seating)}` : "";

  const netEl = document.getElementById("cm-net-val");
  if (netEl) netEl.textContent = "Rs. " + fmt.rupees(net);
}

function cmConfirm(id) {
  const discount = Math.max(0, parseFloat(document.getElementById("cm-discount")?.value) || 0);
  const seats    = Math.max(0, parseInt(document.getElementById("cm-seats")?.value) || 0);
  const seating  = seats * 200;
  document.getElementById("charges-modal-overlay").remove();
  if (window._cmCallback) window._cmCallback(id, discount, seating);
}

function printClearance(id) {
  if (!backend) { toast("Backend not ready", "error"); return; }
  showChargesModal(id, (id, discount, seating) => {
    backend.print_clearance_receipt_with_charges(id, discount, seating, (json) => {
      let r; try { r = JSON.parse(json); } catch { toast("Clearance error: bad response", "error"); return; }
      if (r.success) toast("Clearance receipt sent to printer", "success");
      else toast("Clearance error: " + r.error, "error");
    });
  });
}

function markCleared(id) {
  if (!confirm("Mark this booking as fully cleared?\n\nYou\'ll enter discount and extra seating charges next.")) return;
  showChargesModal(id, (id, discount, seating) => {
    backend.mark_cleared_with_charges(id, discount, seating, (json) => {
      let r; try { r = JSON.parse(json); } catch { toast("Error", "error"); return; }
      if (r.success) {
        toast("Booking cleared — printing clearance receipt…", "success");
        loadBookings();
        backend.print_clearance_receipt_with_charges(id, discount, seating, (json2) => {
          let r2; try { r2 = JSON.parse(json2); } catch { return; }
          if (r2.success) toast("Clearance receipt sent to printer", "success");
          else toast("Receipt error: " + (r2.error || "unknown"), "error");
        });
      } else {
        toast("Error: " + r.error, "error");
      }
    });
  });
}

function cancelBooking(id) {
  if (!confirm("Cancel this booking? This cannot be undone easily.")) return;
  backend.cancel_booking(id, (json) => {
    const r = JSON.parse(json);
    if (r.success) { toast("Booking cancelled", "success"); loadBookings(); }
    else toast("Error: " + r.error, "error");
  });
}

// ════════════════════════════════════════════════════════════
//  MODAL  (Add / Edit booking)
// ════════════════════════════════════════════════════════════

// Live recalculation of total and remaining
function recalcBooking() {
  const persons   = parseInt(document.getElementById("f-persons")?.value) || 0;
  const rate      = parseFloat(document.getElementById("f-rate")?.value)   || 0;
  const advance   = parseFloat(document.getElementById("f-advance")?.value) || 0;
  const total     = Math.round(persons * rate);
  const remaining = Math.max(0, total - advance);
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
  set("f-total",     total);
  set("f-remaining", remaining);
}

function openModal() {
  state.editId = null;
  document.getElementById("modal-title").textContent = "New Booking";
  document.getElementById("booking-form").reset();
  document.getElementById("f-id").value      = "";
  document.getElementById("f-date").value    = new Date().toISOString().split("T")[0];
  document.getElementById("f-advance").value = "0";
  const pfEl = document.getElementById("f-pfans"); if (pfEl) pfEl.value = "0";
  recalcBooking();
  document.getElementById("modal-overlay").classList.remove("hidden");
  initCustomSelects();
  setTimeout(() => document.getElementById("f-name")?.focus(), 10);
}

function openEditModal(id) {
  const b = state.bookings.find(x => x.id === id);
  if (!b) return;
  state.editId = id;
  document.getElementById("modal-title").textContent = "Edit Booking";
  document.getElementById("f-id").value         = b.id;
  document.getElementById("f-name").value        = b.name;
  document.getElementById("f-phone").value       = b.phone || "";
  const cnicEl = document.getElementById("f-cnic"); if (cnicEl) cnicEl.value = b.cnic || "";
  const haEl = document.getElementById("f-home-address"); if (haEl) haEl.value = b.home_address || "";
  document.getElementById("f-date").value        = b.date;
  csSet("f-shift",     b.shift);
  csSet("f-event",     b.event);
  csSet("f-menu-type", b.menu_type || "FPH");
  document.getElementById("f-persons").value     = b.persons;
  document.getElementById("f-rate").value        = b.rate || 0;
  document.getElementById("f-advance").value     = b.advance;
  const pfEl2 = document.getElementById("f-pfans"); if (pfEl2) pfEl2.value = b.p_fans || 0;
  csSet("f-status", b.status);
  document.getElementById("f-notes").value       = b.notes || "";
  recalcBooking();
  document.getElementById("modal-overlay").classList.remove("hidden");
  initCustomSelects();
  setTimeout(() => document.getElementById("f-name")?.focus(), 10);
}

function closeModal() {
  document.getElementById("modal-overlay").classList.add("hidden");
  closeDatePicker();
  state.editId = null;
}

document.getElementById("modal-overlay").addEventListener("click", (e) => {
  if (e.target === document.getElementById("modal-overlay")) closeModal();
});

document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

// Fix #5: availability check before submit
function submitBooking() {
  const name    = document.getElementById("f-name").value.trim();
  const date    = document.getElementById("f-date").value;
  const shift   = csGet("f-shift");
  const persons = parseInt(document.getElementById("f-persons").value) || 0;
  const rate    = parseFloat(document.getElementById("f-rate").value)  || 0;
  const advance = parseFloat(document.getElementById("f-advance").value) || 0;

  if (!name || !date || !shift || !persons || !rate) {
    toast("Please fill in all required fields", "error");
    return;
  }

  const doSave = () => {
    const data = {
      name,
      phone:        document.getElementById("f-phone").value.trim(),
      cnic:         (document.getElementById("f-cnic")?.value || "").trim(),
      home_address: (document.getElementById("f-home-address")?.value || "").trim(),
      date,
      shift,
      event:        csGet("f-event"),
      menu_type:    csGet("f-menu-type"),
      persons,
      rate,
      advance,
      p_fans:       parseInt(document.getElementById("f-pfans")?.value) || 0,
      status:       csGet("f-status"),
      notes:        document.getElementById("f-notes").value.trim(),
    };
    const payload = JSON.stringify(data);

    if (state.editId !== null) {
      backend.update_booking(state.editId, payload, (json) => {
        const r = JSON.parse(json);
        if (r.success) { closeModal(); toast("Booking updated", "success"); loadBookings(); }
        else toast("Error: " + r.error, "error");
      });
    } else {
      backend.add_booking(payload, (json) => {
        const r = JSON.parse(json);
        if (r.success) {
          closeModal();
          toast("New booking added (#" + r.id + ")", "success");
          loadBookings();
          // Only auto-print receipt for bookings dated today or later
          const todayISO = new Date().toISOString().split("T")[0];
          if (r.id && data.date >= todayISO) printReceipt(r.id);
        } else {
          toast("Error: " + r.error, "error");
        }
      });
    }
  };

  // For new bookings, check availability first (Fix #5 safety check)
  if (state.editId === null && backend.get_day_availability) {
    backend.get_day_availability(date, (json) => {
      let av; try { av = JSON.parse(json); } catch { doSave(); return; }
      const taken = av.taken || [];
      const takenSet = new Set(
        Array.isArray(taken) ? taken.map(s => s.toLowerCase()) : Object.keys(taken)
      );
      if (takenSet.has(shift.toLowerCase())) {
        toast(`⚠ ${shift} shift on ${date} is already booked!`, "error");
        return;
      }
      doSave();
    });
  } else {
    doSave();
  }
}

// ════════════════════════════════════════════════════════════
//  UPCOMING PAGE  (Fix #7: Type column; Fix #8: Rate column)
// ════════════════════════════════════════════════════════════
function loadUpcoming() {
  if (!backend) return;
  // All Bookings tab: show every booking with edit/delete
  backend.get_bookings_filtered("", "all", (json) => {
    const rows = JSON.parse(json);
    // Merge into state.bookings so edit modal can find any booking
    rows.forEach(b => {
      if (!state.bookings.find(x => x.id === b.id)) state.bookings.push(b);
    });
    const tbody = document.getElementById("upcoming-tbody");
    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="12"><div class="empty-state"><p>No bookings found</p></div></td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(b => `
      <tr>
        <td class="td-id">#${b.id}</td>
        <td><div class="td-name"><div class="av ${avColor(b.name)}">${initials(b.name)}</div>${escHtml(b.name)}</div></td>
        <td>${fmt.date(b.date)}</td>
        <td>${escHtml(b.shift)}</td>
        <td>${evBadge(b.event)}</td>
        <td>${menuBadge(b.menu_type)}</td>
        <td class="mono">${Number(b.persons).toLocaleString()}</td>
        <td class="mono">${fmt.rupees(b.rate || 0)}</td>
        <td class="mono">${fmt.rupees(b.total)}</td>
        <td>${fmt.remaining(b.remaining)}</td>
        <td>${stBadge(b.status)}</td>
        <td>
          <div class="row-actions">
            <button class="icon-btn" title="Edit" onclick="openEditModal(${b.id})">${ICON.edit}</button>
            <button class="icon-btn" title="Booking receipt" onclick="printReceipt(${b.id})">${ICON.receipt}</button>
            ${b.status === "CLEARED"
              ? `<button class="icon-btn" title="Clearance receipt (A4)" onclick="printClearance(${b.id})">${ICON.clear}</button>`
              : `<button class="icon-btn" title="Mark cleared" onclick="markCleared(${b.id})">${ICON.clear}</button>`}
            ${b.status !== "CANCELLED" ? `<button class="icon-btn danger" title="Cancel" onclick="cancelBooking(${b.id})">${ICON.cancel}</button>` : ""}
          </div>
        </td>
      </tr>`).join("");
  });
}

// ════════════════════════════════════════════════════════════
//  CUSTOMERS
// ════════════════════════════════════════════════════════════
function loadCustomers() {
  if (!backend) return;
  backend.get_customers((json) => {
    const rows  = JSON.parse(json);
    const tbody = document.getElementById("customers-tbody");
    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><p>No customers yet</p></div></td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(c => `
      <tr>
        <td><div class="td-name"><div class="av ${avColor(c.name)}">${initials(c.name)}</div>${escHtml(c.name)}</div></td>
        <td>${escHtml(c.phone || "—")}</td>
        <td>${escHtml(c.cnic || "—")}</td>
        <td>${escHtml(c.home_address || "—")}</td>
        <td><span class="st-badge" style="background:var(--primary-light);color:var(--primary)">${c.total_bookings}</span></td>
        <td class="mono">${fmt.rupees(c.total_spent)}</td>
        <td>${fmt.date(c.last_booking)}</td>
      </tr>`).join("");
  });
}

// ════════════════════════════════════════════════════════════
//  REPORTS
// ════════════════════════════════════════════════════════════
function loadReports() {
  if (!backend) return;
  backend.get_stats((sJson) => {
    backend.get_report_data((rJson) => {
      const s = JSON.parse(sJson);
      const r = JSON.parse(rJson);
      const el = document.getElementById("reports-content");
      const year = new Date().getFullYear();
      backend.get_yearly_summary(year, (yJson) => {
        let y; try { y = JSON.parse(yJson); } catch { y = { months: [] }; }
        const months = y.months || [];

        el.innerHTML = `
        <div class="reports-stats">
          <div class="stat-card">
            <div class="stat-label">Total revenue collected</div>
            <div class="stat-value" style="font-size:20px">${fmt.rupees(s.revenue)}</div>
            <span class="stat-badge badge-green">From cleared bookings</span>
          </div>
          <div class="stat-card">
            <div class="stat-label">Total bookings</div>
            <div class="stat-value">${s.total}</div>
            <span class="stat-badge badge-blue">Excl. cancelled</span>
          </div>
          <div class="stat-card">
            <div class="stat-label">Pending clearance</div>
            <div class="stat-value">${s.pending}</div>
            <span class="stat-badge badge-amber">Awaiting clearance</span>
          </div>
        </div>
        <div class="events-table-card">
          <div class="table-toolbar"><div><div class="table-title">Revenue by Event Type</div></div></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Event</th><th>Bookings</th><th>Revenue</th></tr></thead>
              <tbody>
                ${r.by_event.length === 0
                  ? `<tr><td colspan="3"><div class="empty-state"><p>No data yet</p></div></td></tr>`
                  : r.by_event.map(ev => `
                    <tr>
                      <td>${evBadge(ev.event)}</td>
                      <td>${ev.count}</td>
                      <td class="mono">${fmt.rupees(ev.revenue)}</td>
                    </tr>`).join("")}
              </tbody>
            </table>
          </div>
        </div>
        <div class="events-table-card" style="margin-top:12px">
          <div class="table-toolbar">
            <div>
              <div class="table-title">Monthly Summary (${year})</div>
              <div class="table-sub">Bookings, revenue, advance, pending per month</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>Month</th><th>Bookings</th><th>Revenue</th><th>Advance</th><th>Remaining</th></tr>
              </thead>
              <tbody>
                ${months.length === 0
                  ? `<tr><td colspan="7"><div class="empty-state"><p>No monthly data yet</p></div></td></tr>`
                  : months.map(m => `
                    <tr>
                      <td>${escHtml(m.month)}</td>
                      <td class="mono">${m.count}</td>
                      <td class="mono">${fmt.rupees(m.revenue)}</td>
                      <td class="mono">${fmt.rupees(m.advance)}</td>
                      <td class="mono">${fmt.rupees(m.remaining)}</td>

                    </tr>`).join("")}
              </tbody>
            </table>
          </div>
        </div>`;
      });
    });
  });
}

// ════════════════════════════════════════════════════════════
//  HISTORY / SEARCH
// ════════════════════════════════════════════════════════════
function loadHistory() {
  // Load cancelled/deleted bookings into their own panel
  if (backend) {
    backend.get_cancelled_bookings((json) => {
      let rows; try { rows = JSON.parse(json); } catch { rows = []; }
      renderCancelledPanel(rows);
    });
  }
  const btnHist = document.getElementById("btn-hist-search");
  const btnAdv  = document.getElementById("btn-adv-search");

  if (btnHist && !btnHist._bound) {
    btnHist._bound = true;
    btnHist.addEventListener("click", () => {
      const phone = (document.getElementById("hist-phone")?.value || "").trim();
      if (!phone) { toast("Enter a phone number to search", "error"); return; }
      backend.customer_history(phone, (json) => {
        let rows; try { rows = JSON.parse(json); } catch { rows = []; }
        renderHistoryResults(rows, `History for ${phone}`);
      });
    });
  }

  if (btnAdv && !btnAdv._bound) {
    btnAdv._bound = true;
    btnAdv.addEventListener("click", () => {
      const q = (document.getElementById("adv-query")?.value || "").trim();
      const incCancelled = !!document.getElementById("adv-include-cancelled")?.checked;
      if (!q) { toast("Type something to search", "error"); return; }
      backend.search_bookings(q, incCancelled, (json) => {
        let rows; try { rows = JSON.parse(json); } catch { rows = []; }
        renderHistoryResults(rows, `Search: ${q}${incCancelled ? " (incl. cancelled)" : ""}`);
      });
    });
  }
}

function renderHistoryResults(rows, label) {
  const tbody   = document.getElementById("history-tbody");
  const countEl = document.getElementById("history-count");
  if (!tbody || !countEl) return;
  countEl.textContent = `${rows.length} record${rows.length !== 1 ? "s" : ""} · ${label || ""}`;

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="10"><div class="empty-state"><p>No matching bookings</p></div></td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(b => `
    <tr>
      <td class="td-id">#${b.id}</td>
      <td><div class="td-name"><div class="av ${avColor(b.name)}">${initials(b.name)}</div>${escHtml(b.name)}</div></td>
      <td>${fmt.date(b.date)}</td>
      <td>${escHtml(b.shift)}</td>
      <td>${evBadge(b.event)}</td>
      <td class="mono">${Number(b.persons).toLocaleString()}</td>
      <td class="mono">${fmt.rupees(b.total)}</td>
      <td class="mono">${fmt.rupees(b.advance)}</td>
      <td>${fmt.remaining(b.remaining)}</td>
      <td>${stBadge(b.status)}</td>
    </tr>`).join("");
}

// ════════════════════════════════════════════════════════════
//  SETTINGS
// ════════════════════════════════════════════════════════════
function renderSettings() {
  const cont = document.getElementById("settings-content");
  if (!cont) return;

  cont.innerHTML = `
    <div class="settings-section">
      <div class="settings-section-title">Appearance</div>
      <div class="settings-row">
        <div>
          <div class="settings-row-label">Dark Mode</div>
          <div class="settings-row-sub">Easy on the eyes — saved automatically in browser.</div>
        </div>
        <label style="display:flex;align-items:center;gap:10px;cursor:pointer;user-select:none;">
          <span style="font-size:13px;color:var(--text-muted)">Light</span>
          <div id="dm-wrap" style="position:relative;width:44px;height:24px;flex-shrink:0;"
               onclick="var c=document.getElementById('dm-cb');c.checked=!c.checked;toggleDarkMode(c.checked);dmSync();">
            <input type="checkbox" id="dm-cb" style="opacity:0;position:absolute;width:0;height:0;" />
            <span id="dm-track" style="position:absolute;inset:0;border-radius:999px;background:var(--border-mid);transition:.2s;"></span>
            <span id="dm-thumb" style="position:absolute;top:2px;left:2px;width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.35);transition:.2s;pointer-events:none;"></span>
          </div>
          <span style="font-size:13px;color:var(--text-muted)">Dark</span>
        </label>
      </div>
    </div>
    <div class="settings-section">
      <div class="settings-section-title">Hall Information</div>
      <div class="settings-row">
        <div><div class="settings-row-label">Hall Name</div><div class="settings-row-sub">Displayed on receipts and reports</div></div>
        <input id="cfg-hall-name" class="settings-input" />
      </div>
      <div class="settings-row">
        <div><div class="settings-row-label">Contact Number</div><div class="settings-row-sub">Printed on receipts</div></div>
        <input id="cfg-hall-phone1" class="settings-input" placeholder="e.g. 051-XXXXXXX" />
      </div>
      <div class="settings-row">
        <div><div class="settings-row-label">Address</div><div class="settings-row-sub">Shown on printed documents</div></div>
        <input id="cfg-hall-address" class="settings-input" placeholder="Hall address" />
      </div>
    </div>
    <div class="settings-section">
      <div class="settings-section-title">Application</div>
      <div class="settings-row">
        <div><div class="settings-row-label">App Version</div><div class="settings-row-sub">Dhanak Banquet Hall Manager</div></div>
        <span style="font-size:13px;color:var(--text-muted)">v3.0</span>
      </div>
      <div class="settings-row">
        <div><div class="settings-row-label">Database Location</div><div class="settings-row-sub">SQLite data file</div></div>
        <span style="font-size:12px;color:var(--text-faint);font-family:monospace">dhanak.db</span>
      </div>
      <div class="settings-row">
        <div><div class="settings-row-label">Claude API key</div><div class="settings-row-sub">Stored locally in Config; used by AI assistant</div></div>
        <input id="cfg-api-key" class="settings-input" placeholder="sk-ant-..." />
      </div>
    </div>
    <div class="settings-section">
      <div class="settings-section-title">Google Sheets</div>
      <div class="settings-row">
        <div><div class="settings-row-label">Sheet ID</div><div class="settings-row-sub">ID from the Google Sheets URL</div></div>
        <input id="cfg-gsheet-id" class="settings-input" placeholder="Sheet ID" />
      </div>
      <div class="settings-row">
        <div><div class="settings-row-label">Service account JSON path</div><div class="settings-row-sub">Full path to the downloaded JSON key</div></div>
        <input id="cfg-gsheet-key" class="settings-input" placeholder="C:\\path\\to\\service-key.json" />
      </div>
      <div class="settings-row">
        <div><div class="settings-row-label">Sync Now</div><div class="settings-row-sub">Export recent bookings to the configured sheet</div></div>
        <button class="btn btn-primary" id="btn-sync-sheets">Sync to Google Sheets</button>
      </div>
    </div>
    <div class="settings-section">
      <div class="settings-section-title">Printers</div>
      <div class="settings-row">
        <div>
          <div class="settings-row-label">Thermal Printer Name</div>
          <div class="settings-row-sub">Exact Windows printer name for 80mm booking receipts. Leave blank to use browser dialog.</div>
        </div>
        <input id="cfg-thermal-printer" class="settings-input" placeholder="e.g. EPSON TM-T20III" />
      </div>
      <div class="settings-row">
        <div>
          <div class="settings-row-label">A4 Printer Name</div>
          <div class="settings-row-sub">Exact Windows printer name for A4 clearance receipts. Leave blank to use browser dialog.</div>
        </div>
        <input id="cfg-a4-printer" class="settings-input" placeholder="e.g. HP LaserJet M404" />
      </div>
      <div class="settings-row">
        <div>
          <div class="settings-row-label">How to find printer names</div>
          <div class="settings-row-sub">Go to Windows Settings → Bluetooth &amp; devices → Printers &amp; scanners. Copy the name exactly.</div>
        </div>
        <span style="font-size:12px;color:var(--text-muted)">⚙ Windows only</span>
      </div>
    </div>
    <div class="settings-section">
      <div class="settings-section-title">Maintenance</div>
      <div class="settings-row">
        <div><div class="settings-row-label">Backup database</div><div class="settings-row-sub">Creates a timestamped copy of the SQLite file</div></div>
        <button class="btn btn-ghost" id="btn-backup">Backup Now</button>
      </div>
      <div class="settings-row">
        <div><div class="settings-row-label">Export CSV</div><div class="settings-row-sub">Exports bookings as CSV (Excel compatible)</div></div>
        <button class="btn btn-ghost" id="btn-export-csv">Export CSV</button>
      </div>
    </div>`;

  const cfgKeys = [
    ["hall_name",        "cfg-hall-name"],
    ["hall_phone1",      "cfg-hall-phone1"],
    ["hall_address",     "cfg-hall-address"],
    ["api_key",          "cfg-api-key"],
    ["gsheet_id",        "cfg-gsheet-id"],
    ["gsheet_key_path",  "cfg-gsheet-key"],
    ["thermal_printer",  "cfg-thermal-printer"],
    ["a4_printer",       "cfg-a4-printer"],
  ];
  cfgKeys.forEach(([key, id]) => {
    backend.get_config_value(key, (json) => {
      let r; try { r = JSON.parse(json); } catch { return; }
      const el = document.getElementById(id);
      if (el) el.value = r.value || "";
    });
  });
  // Sync the toggle knob once settings panel renders
  dmSync();

  cfgKeys.forEach(([key, id]) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("blur", () => {
      backend.set_config_value(key, el.value, (json) => {
        let r; try { r = JSON.parse(json); } catch { return; }
        if (!r.success) toast(r.error || "Failed to save setting", "error");
      });
    });
  });

  document.getElementById("btn-sync-sheets")?.addEventListener("click", () => {
    const sheetId = document.getElementById("cfg-gsheet-id").value.trim();
    const keyPath = document.getElementById("cfg-gsheet-key").value.trim();
    backend.sync_google_sheet(sheetId, keyPath, (json) => {
      let r; try { r = JSON.parse(json); } catch { toast("Sheets error", "error"); return; }
      r.success ? toast(`Synced ${r.rows} rows`, "success") : toast(r.error || "Sync failed", "error");
    });
  });

  document.getElementById("btn-backup")?.addEventListener("click", () => {
    backend.backup_now((json) => {
      let r; try { r = JSON.parse(json); } catch { toast("Backup error", "error"); return; }
      r.success ? toast(`Backup: ${r.path}`, "success") : toast(r.error || "Backup failed", "error");
    });
  });

  document.getElementById("btn-export-csv")?.addEventListener("click", () => {
    backend.export_csv((json) => {
      let r; try { r = JSON.parse(json); } catch { toast("Export error", "error"); return; }
      r.success ? toast(`CSV exported: ${r.path}`, "success") : toast(r.error || "Export failed", "error");
    });
  });
}

// ════════════════════════════════════════════════════════════
//  AI ASSISTANT
// ════════════════════════════════════════════════════════════
function _aiAppend(html) {
  const log = document.getElementById("ai-log");
  if (!log) return;
  // Remove welcome message on first interaction
  const welcome = log.querySelector(".ai-welcome");
  if (welcome) welcome.remove();
  log.insertAdjacentHTML("beforeend", html);
  log.scrollTop = log.scrollHeight;
}

function sendAiQuery() {
  if (!backend) { toast("Backend not ready", "error"); return; }
  const input   = document.getElementById("ai-input");
  const sendBtn = document.getElementById("ai-send-btn");
  const text    = input?.value.trim();
  if (!text) { toast("Type a question first", "error"); return; }

  // Prevent double-sends
  if (sendBtn) { sendBtn.disabled = true; sendBtn.style.opacity = "0.5"; }

  // Show user bubble
  _aiAppend(`<div class="ai-exchange">
    <div class="ai-user">${escHtml(text)}</div>
  </div>`);
  input.value = "";
  input.style.height = "auto";

  // Show typing indicator
  const typingId = "ai-typing-" + Date.now();
  _aiAppend(`<div id="${typingId}" class="ai-exchange">
    <div class="ai-bot" style="opacity:0.6;font-style:italic;">Thinking…</div>
  </div>`);

  backend.ai_query(text, (json) => {
    // Re-enable send button
    if (sendBtn) { sendBtn.disabled = false; sendBtn.style.opacity = "1"; }

    // Remove typing indicator
    const typingEl = document.getElementById(typingId);
    if (typingEl) typingEl.remove();

    let r; try { r = JSON.parse(json); } catch { toast("AI error: bad response", "error"); return; }
    if (!r.success) {
      _aiAppend(`<div class="ai-error">Error: ${escHtml(r.error)}</div>`);
      return;
    }
    _aiAppend(`<div class="ai-exchange">
      <div class="ai-bot">${escHtml(r.reply)}</div>
    </div>`);
  });
}

// Enter to send (Shift+Enter for newline)
document.addEventListener("DOMContentLoaded", () => {
  setTimeout(() => {
    const aiInput = document.getElementById("ai-input");
    if (aiInput) {
      aiInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendAiQuery();
        }
      });
      // Auto-resize textarea
      aiInput.addEventListener("input", () => {
        aiInput.style.height = "auto";
        aiInput.style.height = Math.min(aiInput.scrollHeight, 80) + "px";
      });
    }
  }, 200);
});

function runVoice() {
  if (!backend) { toast("Backend not ready", "error"); return; }
  const micBtn = document.getElementById("ai-mic-btn");

  // Prevent double-click
  if (micBtn && (micBtn.classList.contains("listening") || micBtn.classList.contains("processing"))) return;

  if (micBtn) {
    micBtn.classList.add("listening");
    micBtn.innerHTML = '<span class="mic-count">3</span>';
  }

  // ── 3-2-1 countdown on the button ──
  let count = 3;
  const countInterval = setInterval(() => {
    count--;
    if (count > 0 && micBtn) {
      micBtn.innerHTML = `<span class="mic-count">${count}</span>`;
    } else {
      clearInterval(countInterval);
      if (micBtn) {
        micBtn.classList.remove("listening");
        micBtn.classList.add("processing");
        micBtn.innerHTML = '<span class="mic-count" style="font-size:9px">...</span>';
      }
    }
  }, 1000);

  // Show listening bubble
  const listenId = "ai-listen-" + Date.now();
  _aiAppend(`<div id="${listenId}" class="ai-exchange">
    <div class="ai-user" style="opacity:0.6;font-style:italic;">Recording 3s...</div>
  </div>`);

  backend.voice_interact((json) => {
    clearInterval(countInterval);

    // Reset mic button
    if (micBtn) {
      micBtn.classList.remove("listening", "processing");
      micBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="1" width="6" height="11" rx="3"/><path d="M19 10v1a7 7 0 0 1-14 0v-1"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>';
    }

    // Remove listening placeholder
    const listenEl = document.getElementById(listenId);
    if (listenEl) listenEl.remove();

    let r; try { r = JSON.parse(json); } catch { toast("Voice error", "error"); return; }

    if (!r.success) {
      const err = (r.error || "").toLowerCase();
      if (err.includes("recognize") || err.includes("speech")) {
        _aiAppend(`<div class="ai-error">No speech detected. Tap mic and speak clearly for 3 seconds.</div>`);
      } else {
        _aiAppend(`<div class="ai-error">Error: ${escHtml(r.error)}</div>`);
      }
      return;
    }
    _aiAppend(`<div class="ai-exchange">
      <div class="ai-user">${escHtml(r.heard || "")}</div>
      <div class="ai-bot">${escHtml(r.reply)}</div>
    </div>`);
  });
}

// ════════════════════════════════════════════════════════════
//  TOAST
// ════════════════════════════════════════════════════════════
let toastTimer = null;
function toast(msg, type = "success") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = `toast ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = "toast hidden"; }, 3000);
}

// ════════════════════════════════════════════════════════════
//  UTILITY
// ════════════════════════════════════════════════════════════
function escHtml(str) {
  return String(str ?? "")
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}

// ════════════════════════════════════════════════════════════
//  FPH MENU — category definitions (mirror dhanak.py)
// ════════════════════════════════════════════════════════════
const FPH_CATEGORIES = [
  { key: "1",  title: "1 – Salan (Curry)",       options: [
      "Mutton Qorma Red","Mutton Qorma White",
      "Beef Qorma Red","Beef Qorma White",
      "Chicken Qorma Red","Chicken Qorma White",
  ]},
  { key: "2",  title: "2 – Namkin Chawal (Rice)", options: ["Mutton Biryani","Beef Biryani","Chicken Biryani","Fried Rice","Murgh Pulao","Kabli Palao"] },
  { key: "3",  title: "3 – Sweet Dish",           options: ["Matanajan","Zarda","Kheer","Fruit Trifle","Ice Cream Simple","Ice Cream Walls","Lab-e-Shirin"] },
  { key: "4",  title: "4 – Salad",                options: ["Fresh Sabzi Salad","Kachumber Salad","Russian Salad","Chanay","Lobia","Macaroni"] },
  { key: "5",  title: "5 – Drinks",               options: [
      "Coke 1.5L","Coke 1L","Sprite 1.5L","Sprite 1L",
      "7UP 1.5L","7UP 1L","Nestle Juice Regular","Fresh Juice",
      "Tin","NR",
  ]},
  { key: "6",  title: "6 – Raita",                options: ["Podina Raita","Zeera Raita","Sada Dahi Raita"] },
  { key: "7",  title: "7 – Roti (Bread)",         options: ["Tandoori Roti","Khameeri Roti","Sada Naan","Roghni Naan","Milky Naan","Sheermal"] },
  { key: "8",  title: "8 – Paani (Water)",        options: ["Sada Thanda Paani","Branded Mineral Water","Normal Mineral Water"] },
  { key: "9",  title: "9 – BBQ",                  options: ["Chicken Tikka Boti","Beef Kabab","Chicken Kabab","Seekhi Kabab","Malai Boti","Reshmi Kabab"] },
  { key: "10", title: "10 – Roast",               options: ["Chicken Steam Roast","Beef Steam Roast","Chicken Brost","Chicken Pakoda","Chicken Candy","Chicken Butterfly"] },
  { key: "11", title: "11 – Fish Counter",        options: ["Finger Fish","Normal Fish"] },
  { key: "12", title: "12 – Other Items",         options: [] },
];

// Current FPH selections state (key → array of chosen options)
const fphState = {};

function loadFphMenu() {
  const grid = document.getElementById("fph-categories-grid");
  if (!grid) return;
  renderFphGrid(grid);
}

function renderFphGrid(grid) {
  grid.innerHTML = FPH_CATEGORIES.map(cat => {
    const chosen = fphState[cat.key] || [];
    const chosenSet = new Set(Array.isArray(chosen) ? chosen : [chosen]);
    if (cat.options.length === 0) {
      const val = Array.isArray(chosen) ? chosen.join(", ") : (chosen || "");
      return `<div class="fph-box">
        <div class="fph-box-title">${escHtml(cat.title)}</div>
        <input class="fph-other-input" type="text" placeholder="Describe item…"
          value="${escHtml(val)}"
          oninput="fphState['${cat.key}']=[this.value]" />
      </div>`;
    }
    const opts = cat.options.map(opt => {
      const sel = chosenSet.has(opt);
      return `<label class="fph-radio-label${sel ? " fph-selected" : ""}">
        <input type="checkbox" name="fph_${cat.key}" value="${escHtml(opt)}"
          ${sel ? "checked" : ""}
          onchange="fphToggleOption('${cat.key}', this.value, this.checked, this.closest('.fph-box'))" />
        <span class="fph-radio-dot"></span>
        <span class="fph-radio-text">${escHtml(opt)}</span>
      </label>`;
    }).join("");
    return `<div class="fph-box">
      <div class="fph-box-title">${escHtml(cat.title)}</div>
      ${opts}
    </div>`;
  }).join("");
}

function fphToggleOption(catKey, value, checked, box) {
  if (!fphState[catKey]) fphState[catKey] = [];
  if (!Array.isArray(fphState[catKey])) fphState[catKey] = [fphState[catKey]];
  if (checked) {
    if (!fphState[catKey].includes(value)) fphState[catKey].push(value);
  } else {
    fphState[catKey] = fphState[catKey].filter(v => v !== value);
  }
  if (!box) return;
  box.querySelectorAll(".fph-radio-label").forEach(lbl => {
    lbl.classList.toggle("fph-selected", lbl.querySelector("input").checked);
  });
}

function resetFphForm() {
  Object.keys(fphState).forEach(k => delete fphState[k]);
  const cname = document.getElementById("fph-cname"); if (cname) cname.value = "";
  const bnum  = document.getElementById("fph-bnum");  if (bnum)  bnum.value  = "";
  const notes = document.getElementById("fph-notes"); if (notes) notes.value = "";
  const grid  = document.getElementById("fph-categories-grid");
  if (grid) renderFphGrid(grid);
}

function saveFphMenu() {
  if (!backend) { toast("Backend not ready", "error"); return; }
  const cname = (document.getElementById("fph-cname")?.value || "").trim();
  const bnum  = (document.getElementById("fph-bnum")?.value  || "").trim();
  const notes = (document.getElementById("fph-notes")?.value || "").trim();
  if (!cname) { toast("Please enter a customer name", "error"); return; }
  const menuData = {
    booking_id:    parseInt(bnum) || 0,
    customer_name: cname,
    booking_number: bnum,
    selections:    { ...fphState },
    notes,
  };
  const payload = JSON.stringify(menuData);
  // Save to DB
  backend.save_fph_menu(payload, (json) => {
    let r; try { r = JSON.parse(json); } catch { toast("Save error", "error"); return; }
    if (!r.success) { toast("Save failed: " + r.error, "error"); return; }
    toast("FPH menu saved (#" + r.id + ") — printing…", "success");
    // Print
    backend.print_fph_menu(payload, (json2) => {
      let r2; try { r2 = JSON.parse(json2); } catch { return; }
      if (!r2.success) toast("Print error: " + (r2.error || "unknown"), "error");
    });
  });
}

// ════════════════════════════════════════════════════════════
//  FPH RECORDS PAGE
// ════════════════════════════════════════════════════════════
// Open FPH menu tab pre-filled from a booking row click
function openFphForBooking(bookingId, customerName) {
  navigateTo("fph-menu");
  setTimeout(() => {
    const cname = document.getElementById("fph-cname");
    const bnum  = document.getElementById("fph-bnum");
    if (cname) cname.value = customerName || "";
    if (bnum)  bnum.value  = String(bookingId);
  }, 80);
}

function loadFphRecords() {
  if (!backend) return;
  backend.get_fph_menus((json) => {
    let rows; try { rows = JSON.parse(json); } catch { rows = []; }
    const tbody = document.getElementById("fph-records-tbody");
    if (!tbody) return;
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state"><p>No FPH orders saved yet</p></div></td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(r => {
      let sels = {};
      try { sels = typeof r.selections === "string" ? JSON.parse(r.selections) : r.selections; } catch {}
      const count = Object.values(sels).filter(v => v).length;
      return `<tr>
        <td class="td-id">#${r.id}</td>
        <td><div class="td-name"><div class="av ${avColor(r.customer_name||'?')}">${initials(r.customer_name||'?')}</div>${escHtml(r.customer_name||'—')}</div></td>
        <td>${escHtml(r.booking_number||'—')}</td>
        <td>${escHtml(r.created_at||'—')}</td>
        <td><span class="st-badge" style="background:var(--primary-light);color:var(--primary)">${count} items</span>&nbsp;${escHtml(r.notes||'')}</td>
        <td class="row-actions">
          <button class="btn btn-ghost" style="font-size:12px;padding:4px 10px;" onclick='reprintFphMenu(${JSON.stringify(JSON.stringify(r))})'>Reprint</button>
          <button class="btn btn-danger" style="font-size:12px;padding:4px 10px;" onclick="deleteFphRecord(${r.id})">Delete</button>
        </td>
      </tr>`;
    }).join("");
  });
}

function deleteFphRecord(id) {
  if (!backend) return;
  if (!confirm("Delete this FPH menu record? This cannot be undone.")) return;
  backend.delete_fph_menu(id, (json) => {
    let r; try { r = JSON.parse(json); } catch { toast("Delete error", "error"); return; }
    if (!r.success) { toast("Delete failed: " + (r.error || "unknown"), "error"); return; }
    toast("FPH menu deleted", "success");
    loadFphRecords();
  });
}

function reprintFphMenu(rowJson) {
  if (!backend) { toast("Backend not ready", "error"); return; }
  let row; try { row = JSON.parse(rowJson); } catch { toast("Parse error","error"); return; }
  backend.print_fph_menu(JSON.stringify(row), (json) => {
    let r; try { r = JSON.parse(json); } catch { return; }
    if (r.success) toast("FPH menu sent to printer", "success");
    else toast("Print error: " + r.error, "error");
  });
}

// ════════════════════════════════════════════════════════════
//  CANCELLED BOOKINGS PANEL (shown inside History page)
// ════════════════════════════════════════════════════════════
function renderCancelledPanel(rows) {
  // Create or update the cancelled panel inside the history page
  let panel = document.getElementById("cancelled-panel");
  if (!panel) {
    const histPage = document.getElementById("page-history");
    if (!histPage) return;
    panel = document.createElement("div");
    panel.id = "cancelled-panel";
    panel.className = "table-card";
    panel.style.marginTop = "12px";
    histPage.appendChild(panel);
  }
  if (!rows.length) {
    panel.innerHTML = `<div class="table-toolbar"><div><div class="table-title">Cancelled / Deleted Bookings</div><div class="table-sub" style="color:#A32D2D">No cancelled bookings on record</div></div></div>`;
    return;
  }
  panel.innerHTML = `
    <div class="table-toolbar">
      <div>
        <div class="table-title">Cancelled / Deleted Bookings</div>
        <div class="table-sub" style="color:#A32D2D">${rows.length} cancelled record${rows.length !== 1 ? "s" : ""}</div>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>ID</th><th>Customer</th><th>Date</th><th>Shift</th><th>Event</th><th>Persons</th><th>Total</th><th>Reason</th></tr></thead>
        <tbody>${rows.map(b => `
          <tr style="opacity:0.72;">
            <td class="td-id" style="color:#A32D2D">#${b.id}</td>
            <td><div class="td-name"><div class="av av-gray">${initials(b.customer_name||'?')}</div>${escHtml(b.customer_name||'—')}</div></td>
            <td>${fmt.date(b.event_date)}</td>
            <td>${escHtml(b.shift||'—')}</td>
            <td>${evBadge(b.event_type)}</td>
            <td class="mono">${Number(b.persons||0).toLocaleString()}</td>
            <td class="mono">${fmt.rupees((b.persons||0)*(b.rate||0))}</td>
            <td style="font-size:12px;color:#888">${escHtml(b.cancel_reason||'—')}</td>
          </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
}

// ════════════════════════════════════════════════════════════
//  MOCK BACKEND  (plain browser testing)
// ════════════════════════════════════════════════════════════
function makeMockBackend() {
  const data = [
    {id:3,name:"Nadia Arfan",phone:"0300-1111111",date:"2026-09-08",shift:"Day 1",event:"Birthday",menu_type:"FPH",persons:500,rate:200,total:100000,advance:100000,remaining:0,status:"CLEARED",notes:""},
    {id:1,name:"Musa Sher",  phone:"0311-2222222",date:"2026-03-14",shift:"Day 1",event:"Mehndi",  menu_type:"FPH",persons:400,rate:200,total:80000, advance:80000, remaining:0,status:"CLEARED",notes:""},
    {id:2,name:"Fatima Ali", phone:"0333-3333333",date:"2026-04-02",shift:"Night 1",event:"Walima",menu_type:"SPH",persons:700,rate:214,total:150000,advance:50000,remaining:100000,status:"PENDING",notes:"Extra floral"},
  ];
  return {
    get_bookings:          (cb) => cb(JSON.stringify(data)),
    get_bookings_filtered: (s, f, cb) => {
      let r = [...data];
      if (s) r = r.filter(b => b.name.toLowerCase().includes(s.toLowerCase()));
      if (f && f !== "all") r = r.filter(b => b.status.toLowerCase() === f.toLowerCase());
      cb(JSON.stringify(r));
    },
    get_stats:             (cb) => cb(JSON.stringify({total:3,pending:1,revenue:180000,upcoming:2,next_date:"2026-03-14"})),
    get_customers:         (cb) => cb(JSON.stringify([{name:"Nadia Arfan",phone:"0300-1111111",total_bookings:1,total_spent:100000,last_booking:"2026-09-08"}])),
    get_upcoming:          (cb) => cb(JSON.stringify(data.filter(b => b.date >= new Date().toISOString().split("T")[0]))),
    get_report_data:       (cb) => cb(JSON.stringify({by_event:[{event:"Mehndi",count:1,revenue:80000}],monthly:[]})),
    get_month_availability:(y,m,cb) => cb(JSON.stringify({year:y,month:m,days:{}})),
    get_day_availability:  (d,cb)  => cb(JSON.stringify({taken:[],count:0,full:false,open:true})),
    get_yearly_summary:    (y,cb)  => cb(JSON.stringify({year:y,months:[]})),
    add_booking:           (d,cb)  => { const obj=JSON.parse(d); obj.id=Math.floor(Math.random()*1000); obj.total=obj.persons*obj.rate; obj.remaining=obj.total-obj.advance; data.push(obj); cb(JSON.stringify({success:true,id:obj.id})); },
    update_booking:        (id,d,cb) => { const obj=JSON.parse(d); const i=data.findIndex(b=>b.id===id); if(i>=0){data[i]={...data[i],...obj,id};} cb(JSON.stringify({success:true})); },
    cancel_booking:        (id,cb) => { const b=data.find(x=>x.id===id); if(b) b.status="CANCELLED"; cb(JSON.stringify({success:true})); },
    clear_booking:         (id,cb) => { const b=data.find(x=>x.id===id); if(b){b.status="CLEARED";b.remaining=0;} cb(JSON.stringify({success:true})); },
    mark_cleared_with_charges:           (id,disc,seat,cb) => { const b=data.find(x=>x.id===id); if(b){b.status="CLEARED";b.remaining=0;b.discount=disc;b.surplus=seat;} cb(JSON.stringify({success:true})); },
    print_clearance_receipt_with_charges:(id,disc,seat,cb) => cb(JSON.stringify({success:true,path:"mock.html"})),
    print_booking_receipt: (id,cb) => cb(JSON.stringify({success:true,path:"mock.html"})),
    print_clearance_receipt:(id,cb)=> cb(JSON.stringify({success:true,path:"mock.html"})),
    get_config_value:      (k,cb)  => cb(JSON.stringify({key:k,value:""})),
    set_config_value:      (k,v,cb)=> cb(JSON.stringify({success:true})),
    backup_now:            (cb)    => cb(JSON.stringify({success:true,path:"backup.db"})),
    export_csv:            (cb)    => cb(JSON.stringify({success:true,path:"export.csv",rows:3})),
    sync_google_sheet:     (s,k,cb)=> cb(JSON.stringify({success:false,error:"Mock: not available"})),
    customer_history:      (p,cb)  => cb(JSON.stringify(data.filter(b=>b.phone===p))),
    search_bookings:       (q,c,cb)=> cb(JSON.stringify(data.filter(b=>b.name.toLowerCase().includes(q.toLowerCase())))),
    ai_query:              (t,cb)  => cb(JSON.stringify({success:true,reply:"Ji bilkul! Yeh mock mode chal raha hai — real backend connect hone par AI poori tarah kaam karega. 😊\n\nAap ne poucha: \""+t+"\""})),
    voice_interact:        (cb)    => cb(JSON.stringify({success:false,error:"Voice not available in mock mode"})),
    get_cancelled_bookings: (cb)   => cb(JSON.stringify([])),
    save_fph_menu:         (d,cb)  => { const o=JSON.parse(d); cb(JSON.stringify({success:true,id:Math.floor(Math.random()*100)})); },
    get_fph_menus:         (cb)    => cb(JSON.stringify([])),
    get_fph_menu_by_booking:(id,cb)=> cb(JSON.stringify({})),
    print_fph_menu:        (d,cb)  => cb(JSON.stringify({success:true,path:"mock_fph.html"})),
  };
}

// ── Calendar selects now use custom .csel component ──
