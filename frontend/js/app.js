async function resolveApiBase() {
  try {
    const res = await fetch(".env", { cache: "no-store" });
    if (res.ok) {
      const text = await res.text();
      const match = text.match(/^\s*API_BASE\s*=\s*"?([^"\r\n]*?)"?\s*$/m);
      if (match && match[1]) return match[1];
    }
  } catch (err) {
    // .env missing or unreadable — fall through to the default below
  }
  return "http://localhost:8000";
}

const API_BASE = await resolveApiBase();

const state = {
  token: localStorage.getItem("slotwise_token") || null,
  user: JSON.parse(localStorage.getItem("slotwise_user") || "null"),
  conversation: [],
};

// ---------- API helper ----------

async function api(path, { method = "GET", body, form = false, auth = true } = {}) {
  const headers = {};
  if (auth && state.token) headers["Authorization"] = `Bearer ${state.token}`;
  let payload = body;
  if (body && !form) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });
  if (res.status === 401) {
    logout();
    throw new Error("Session expired, please log in again.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

// ---------- Auth ----------

function saveSession(token, user) {
  state.token = token;
  state.user = user;
  localStorage.setItem("slotwise_token", token);
  localStorage.setItem("slotwise_user", JSON.stringify(user));
}

function logout() {
  state.token = null;
  state.user = null;
  localStorage.removeItem("slotwise_token");
  localStorage.removeItem("slotwise_user");
  render();
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("login-error");
  errorEl.textContent = "";
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;
  try {
    const params = new URLSearchParams();
    params.set("username", email);
    params.set("password", password);
    const data = await api("/api/auth/login", { method: "POST", body: params, form: true, auth: false });
    saveSession(data.access_token, data.user);
    render();
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("register-error");
  errorEl.textContent = "";
  const body = {
    full_name: document.getElementById("register-name").value,
    email: document.getElementById("register-email").value,
    password: document.getElementById("register-password").value,
    phone: document.getElementById("register-phone").value || null,
    role: document.getElementById("register-role").value,
  };
  try {
    const data = await api("/api/auth/register", { method: "POST", body, auth: false });
    saveSession(data.access_token, data.user);
    render();
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("logout-btn").addEventListener("click", logout);

// ---------- Tab switching ----------

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});

function activateAppTab(viewName) {
  const btn = document.querySelector(`.app-tab-btn[data-view="${viewName}"]`);
  const view = document.getElementById(viewName);
  if (!btn || !view || btn.classList.contains("hidden")) return;

  document.querySelectorAll(".app-tab-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  btn.classList.add("active");
  view.classList.add("active");

  if (viewName === "assistant-view") loadServicePicker();
  if (viewName === "browse-view") loadBusinesses();
  if (viewName === "appointments-view") loadAppointments();
  if (viewName === "owner-view") loadOwnerBusinesses();
  if (viewName === "admin-view") loadAdminData();
}

document.querySelectorAll(".app-tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => activateAppTab(btn.dataset.view));
});

function toggleForm(buttonId, formId) {
  const btn = document.getElementById(buttonId);
  const form = document.getElementById(formId);
  btn.addEventListener("click", () => form.classList.toggle("hidden"));
}

// ---------- Chat / agent booking ----------

function appendChatMessage(role, text, pending = false) {
  const log = document.getElementById("chat-log");
  const el = document.createElement("div");
  el.className = `chat-message ${role}${pending ? " pending" : ""}`;
  if (pending) {
    el.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
  } else {
    el.textContent = text;
  }
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

function appendProposalCard(proposal) {
  const log = document.getElementById("chat-log");
  const el = document.createElement("div");
  el.className = "chat-message assistant";

  const when = new Date(proposal.start_time).toLocaleString([], {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });

  el.innerHTML = `
    <div class="proposal-card">
      <div><strong>${proposal.service_name}</strong> with ${proposal.staff_name}</div>
      <div class="meta">${proposal.business_name} &middot; ${when} &middot; $${proposal.price.toFixed(2)}</div>
      <div class="proposal-actions">
        <button type="button" class="btn btn-primary btn-sm proposal-confirm">Confirm booking</button>
        <button type="button" class="btn btn-ghost btn-sm proposal-decline">Not now</button>
      </div>
    </div>`;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;

  el.querySelector(".proposal-confirm").addEventListener("click", () => confirmProposal(proposal, el));
  el.querySelector(".proposal-decline").addEventListener("click", () => {
    el.querySelector(".proposal-actions").innerHTML = '<span class="meta">Okay — let me know if you\'d like something else.</span>';
  });
}

async function confirmProposal(proposal, cardEl) {
  const actions = cardEl.querySelector(".proposal-actions");
  actions.innerHTML = '<span class="meta">Booking...</span>';
  try {
    await api("/api/appointments", {
      method: "POST",
      body: { service_id: proposal.service_id, staff_id: proposal.staff_id, start_time: proposal.start_time },
    });
    actions.innerHTML = '<span class="meta">✓ Booked!</span>';
    loadAppointments();
    loadNotifications();
  } catch (err) {
    actions.innerHTML = `<span class="meta">${err.message}</span>`;
  }
}

async function sendChatMessage(text) {
  appendChatMessage("user", text);
  state.conversation.push({ role: "user", content: text });

  const pendingEl = appendChatMessage("assistant", "Thinking...", true);

  try {
    const data = await api("/api/agent/chat", { method: "POST", body: { conversation: state.conversation } });
    pendingEl.remove();
    appendChatMessage("assistant", data.reply);
    if (data.status === "proposed" && data.proposal) appendProposalCard(data.proposal);
    state.conversation = data.conversation.map((m) => ({ role: m.role, content: m.content }));
  } catch (err) {
    pendingEl.remove();
    appendChatMessage("assistant", `Something went wrong: ${err.message}`);
  }
}

document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendChatMessage(text);
});

// ---------- Quick booking picker ----------

const pickerState = { businesses: [] };

async function loadServicePicker() {
  const select = document.getElementById("picker-business");
  if (pickerState.businesses.length > 0) return; // populate once per session
  try {
    const businesses = await api("/api/businesses", { auth: false });
    pickerState.businesses = businesses.slice().sort((a, b) => a.name.localeCompare(b.name));
    pickerState.businesses.forEach((b) => {
      const opt = document.createElement("option");
      opt.value = b.id;
      opt.textContent = b.name;
      select.appendChild(opt);
    });
  } catch (err) {
    // non-critical — the free-text chat still works without the picker populated
  }
}

document.getElementById("picker-business").addEventListener("change", async (e) => {
  const businessId = e.target.value;
  const serviceSelect = document.getElementById("picker-service");
  serviceSelect.innerHTML = "";

  if (!businessId) {
    serviceSelect.disabled = true;
    serviceSelect.innerHTML = '<option value="">Choose a business first...</option>';
    updatePickerSubmitState();
    return;
  }

  serviceSelect.disabled = true;
  serviceSelect.innerHTML = '<option value="">Loading services...</option>';
  try {
    const services = await api(`/api/businesses/${businessId}/services`, { auth: false });
    serviceSelect.innerHTML = '<option value="">Choose a service...</option>';
    services.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = s.name;
      serviceSelect.appendChild(opt);
    });
    serviceSelect.disabled = services.length === 0;
    if (services.length === 0) serviceSelect.innerHTML = '<option value="">No services listed yet</option>';
  } catch (err) {
    serviceSelect.innerHTML = '<option value="">Could not load services</option>';
  }
  updatePickerSubmitState();
});

function setupChipGroup(containerId, inputIdsToClear) {
  const container = document.getElementById(containerId);
  container.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const wasActive = chip.classList.contains("active");
      container.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      if (!wasActive) {
        chip.classList.add("active");
        inputIdsToClear.forEach((id) => (document.getElementById(id).value = ""));
      }
      updatePickerSubmitState();
    });
  });
}

setupChipGroup("picker-day-chips", ["picker-date"]);
setupChipGroup("picker-time-chips", ["picker-time-from", "picker-time-to"]);

["picker-date", "picker-time-from", "picker-time-to"].forEach((id) => {
  document.getElementById(id).addEventListener("input", (e) => {
    if (!e.target.value) return;
    const group = id === "picker-date" ? "picker-day-chips" : "picker-time-chips";
    document.getElementById(group).querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
    updatePickerSubmitState();
  });
});

document.getElementById("picker-service").addEventListener("change", updatePickerSubmitState);

function updatePickerSubmitState() {
  const businessSelected = !!document.getElementById("picker-business").value;
  const serviceSelected = !!document.getElementById("picker-service").value;
  document.getElementById("picker-submit-btn").disabled = !(businessSelected && serviceSelected);
}

function composePickerMessage() {
  const businessSelect = document.getElementById("picker-business");
  const serviceSelect = document.getElementById("picker-service");
  const businessName = businessSelect.options[businessSelect.selectedIndex].textContent;
  const serviceName = serviceSelect.options[serviceSelect.selectedIndex].textContent;
  const parts = [`Book ${serviceName} at ${businessName}`];

  const dayChip = document.querySelector("#picker-day-chips .chip.active");
  const dateValue = document.getElementById("picker-date").value;
  if (dateValue) {
    const formatted = new Date(`${dateValue}T00:00:00`).toLocaleDateString(undefined, {
      weekday: "long", month: "long", day: "numeric", year: "numeric",
    });
    parts.push(`on ${formatted}`);
  } else if (dayChip) {
    parts.push(dayChip.dataset.value === "today" ? "today" : `sometime ${dayChip.dataset.value}`);
  }

  const timeChip = document.querySelector("#picker-time-chips .chip.active");
  const timeFrom = document.getElementById("picker-time-from").value;
  const timeTo = document.getElementById("picker-time-to").value;
  if (timeFrom && timeTo) {
    parts.push(`between ${timeFrom} and ${timeTo}`);
  } else if (timeFrom) {
    parts.push(`after ${timeFrom}`);
  } else if (timeTo) {
    parts.push(`before ${timeTo}`);
  } else if (timeChip) {
    parts.push(`in the ${timeChip.dataset.value}`);
  }

  return parts.join(" ") + ".";
}

document.getElementById("picker-submit-btn").addEventListener("click", () => {
  const text = composePickerMessage();
  sendChatMessage(text);
});

// ---------- Browse ----------

async function loadBusinesses() {
  const container = document.getElementById("business-list");
  container.textContent = "Loading...";
  try {
    const businesses = await api("/api/businesses", { auth: false });
    container.innerHTML = "";
    if (businesses.length === 0) container.textContent = "No businesses yet.";
    businesses.forEach((b) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.innerHTML = `<div><strong>${b.name}</strong><div class="meta">${b.address || ""}</div></div>`;
      const btn = document.createElement("button");
      btn.className = "btn btn-ghost btn-sm";
      btn.textContent = "View services";
      btn.addEventListener("click", () => loadServices(b.id, b.name));
      item.appendChild(btn);
      container.appendChild(item);
    });
  } catch (err) {
    container.textContent = err.message;
  }
}

async function loadServices(businessId, businessName) {
  document.getElementById("services-heading").textContent = `Services — ${businessName}`;
  const container = document.getElementById("service-list");
  container.textContent = "Loading...";
  try {
    const services = await api(`/api/businesses/${businessId}/services`, { auth: false });
    container.innerHTML = "";
    if (services.length === 0) container.textContent = "No services listed yet.";
    services.forEach((s) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.innerHTML = `<div><strong>${s.name}</strong><div class="meta">${s.duration_minutes} min &middot; $${s.price}</div></div>`;
      container.appendChild(item);
    });
  } catch (err) {
    container.textContent = err.message;
  }
  loadReviews(businessId, businessName);
}

async function loadReviews(businessId, businessName) {
  const card = document.getElementById("reviews-card");
  const heading = document.getElementById("reviews-heading");
  const container = document.getElementById("review-list");
  card.style.display = "";
  container.textContent = "Loading...";
  try {
    const reviews = await api(`/api/businesses/${businessId}/reviews`, { auth: false });
    if (reviews.length === 0) {
      heading.textContent = `Reviews — ${businessName}`;
      container.textContent = "No reviews yet.";
      return;
    }
    const average = reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length;
    heading.textContent = `Reviews — ${businessName} (${average.toFixed(1)} ★, ${reviews.length})`;
    container.innerHTML = "";
    reviews.forEach((r) => {
      const item = document.createElement("div");
      item.className = "list-item";
      const stars = "★".repeat(r.rating) + "☆".repeat(5 - r.rating);
      item.innerHTML = `<div><strong>${stars}</strong> — ${r.customer_name}${r.comment ? `<div class="meta">${r.comment}</div>` : ""}</div>`;
      container.appendChild(item);
    });
  } catch (err) {
    container.textContent = err.message;
  }
}

// ---------- Appointments ----------

const customerCalState = { year: new Date().getFullYear(), month: new Date().getMonth() };

async function loadAppointments() {
  const container = document.getElementById("appointment-list");
  container.textContent = "Loading...";
  try {
    const appointments = await api("/api/appointments/me");
    renderCalendar("appointments-calendar", appointments, customerCalState, (a) => `${a.service_name} @ ${a.business_name}`);
    container.innerHTML = "";
    if (appointments.length === 0) container.textContent = "No appointments yet.";
    appointments.forEach((a) => {
      const item = document.createElement("div");
      item.className = "list-item";
      const when = new Date(a.start_time).toLocaleString();
      item.innerHTML = `<div><strong>${when}</strong><div class="meta">${a.service_name} at ${a.business_name} with ${a.staff_name}</div></div>`;

      const actions = document.createElement("div");
      actions.style.display = "flex";
      actions.style.alignItems = "center";
      actions.style.gap = ".5rem";

      const badge = document.createElement("span");
      badge.className = `status-badge status-${a.status}`;
      badge.textContent = a.status.replace("_", " ");
      actions.appendChild(badge);

      if (a.status === "confirmed" || a.status === "pending") {
        const btn = document.createElement("button");
        btn.className = "btn btn-ghost btn-sm";
        btn.textContent = "Cancel";
        btn.addEventListener("click", async () => {
          await api(`/api/appointments/${a.id}/cancel`, { method: "POST" });
          loadAppointments();
        });
        actions.appendChild(btn);
      } else if (a.status === "completed" && !a.has_review) {
        const btn = document.createElement("button");
        btn.className = "btn btn-ghost btn-sm";
        btn.textContent = "Leave a review";
        btn.addEventListener("click", () => showReviewForm(item, a.id));
        actions.appendChild(btn);
      } else if (a.status === "completed" && a.has_review) {
        const reviewed = document.createElement("span");
        reviewed.className = "meta";
        reviewed.textContent = "Reviewed";
        actions.appendChild(reviewed);
      }

      item.appendChild(actions);
      container.appendChild(item);
    });
  } catch (err) {
    container.textContent = err.message;
  }
}

function showReviewForm(itemEl, appointmentId) {
  if (itemEl.querySelector(".review-form")) return;

  const form = document.createElement("form");
  form.className = "review-form inline-form";

  const ratingLabel = document.createElement("label");
  ratingLabel.textContent = "Rating";
  const ratingSelect = document.createElement("select");
  [5, 4, 3, 2, 1].forEach((n) => {
    const opt = document.createElement("option");
    opt.value = n;
    opt.textContent = "★".repeat(n) + "☆".repeat(5 - n);
    ratingSelect.appendChild(opt);
  });
  ratingLabel.appendChild(ratingSelect);

  const commentLabel = document.createElement("label");
  commentLabel.textContent = "Comment (optional)";
  const commentInput = document.createElement("input");
  commentInput.type = "text";
  commentLabel.appendChild(commentInput);

  const submitBtn = document.createElement("button");
  submitBtn.type = "submit";
  submitBtn.className = "btn btn-primary btn-sm";
  submitBtn.textContent = "Submit";

  form.append(ratingLabel, commentLabel, submitBtn);
  itemEl.appendChild(form);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api(`/api/appointments/${appointmentId}/review`, {
        method: "POST",
        body: { rating: parseInt(ratingSelect.value, 10), comment: commentInput.value || null },
      });
      loadAppointments();
    } catch (err) {
      alert(err.message);
    }
  });
}

// ---------- Calendar (shared by customer + owner views) ----------

const CAL_MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const CAL_WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function dateKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function renderCalendar(containerId, appointments, calState, getLabel) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const { year, month } = calState;

  const byDate = {};
  appointments.forEach((a) => {
    const key = dateKey(new Date(a.start_time));
    (byDate[key] = byDate[key] || []).push(a);
  });

  const firstOfMonth = new Date(year, month, 1);
  const startWeekday = firstOfMonth.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();

  let html = `
    <div class="cal-header">
      <button type="button" class="btn btn-ghost btn-sm cal-nav" data-dir="-1">&lsaquo;</button>
      <strong>${CAL_MONTH_NAMES[month]} ${year}</strong>
      <button type="button" class="btn btn-ghost btn-sm cal-nav" data-dir="1">&rsaquo;</button>
    </div>
    <div class="cal-grid cal-weekdays">
      ${CAL_WEEKDAYS.map((d) => `<div class="cal-weekday">${d}</div>`).join("")}
    </div>
    <div class="cal-grid cal-days">`;

  for (let i = 0; i < startWeekday; i++) html += `<div class="cal-day empty"></div>`;

  const MAX_DOTS = 5;

  for (let day = 1; day <= daysInMonth; day++) {
    const key = dateKey(new Date(year, month, day));
    const dayAppts = (byDate[key] || []).slice().sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
    const isToday = today.getFullYear() === year && today.getMonth() === month && today.getDate() === day;
    const visibleDots = dayAppts.slice(0, MAX_DOTS);
    const overflow = dayAppts.length - visibleDots.length;

    html += `<div class="cal-day${isToday ? " today" : ""}${dayAppts.length ? " has-appts" : ""}" data-date="${key}">
      <span class="cal-day-num">${day}</span>
      ${
        dayAppts.length
          ? `<div class="cal-dots">
              ${visibleDots.map((a) => `<span class="cal-dot status-${a.status}"></span>`).join("")}
              ${overflow > 0 ? `<span class="cal-dot-more">+${overflow}</span>` : ""}
            </div>`
          : ""
      }
    </div>`;
  }

  html += `</div><div class="cal-detail"></div>`;
  container.innerHTML = html;

  container.querySelectorAll(".cal-nav").forEach((btn) => {
    btn.addEventListener("click", () => {
      calState.month += parseInt(btn.dataset.dir, 10);
      if (calState.month < 0) {
        calState.month = 11;
        calState.year -= 1;
      } else if (calState.month > 11) {
        calState.month = 0;
        calState.year += 1;
      }
      renderCalendar(containerId, appointments, calState, getLabel);
    });
  });

  container.querySelectorAll(".cal-day.has-appts").forEach((cell) => {
    cell.addEventListener("click", () => {
      const key = cell.dataset.date;
      const items = (byDate[key] || []).slice().sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
      const detail = container.querySelector(".cal-detail");
      const label = new Date(`${key}T00:00:00`).toLocaleDateString(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
      });
      detail.innerHTML =
        `<h4>${label}</h4>` +
        items
          .map(
            (a) => `<div class="list-item">
              <div><strong>${new Date(a.start_time).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</strong>
              <div class="meta">${getLabel(a)}</div></div>
              <span class="status-badge status-${a.status}">${a.status.replace("_", " ")}</span>
            </div>`
          )
          .join("");
    });
  });
}

// ---------- Owner dashboard ----------

const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

const ownerState = { businessId: null, staffId: null };
let categoriesCache = [];

toggleForm("owner-new-business-btn", "owner-business-form");
toggleForm("owner-new-service-btn", "owner-service-form");
toggleForm("owner-new-staff-btn", "owner-staff-form");

async function loadCategoriesCache() {
  categoriesCache = await api("/api/categories", { auth: false });
  return categoriesCache;
}

function populateCategorySelect(select, selectedId) {
  select.innerHTML = '<option value="">None</option>';
  categoriesCache.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = c.name;
    if (selectedId === c.id) opt.selected = true;
    select.appendChild(opt);
  });
}

async function loadOwnerBusinesses() {
  const container = document.getElementById("owner-business-list");
  container.textContent = "Loading...";
  try {
    await loadCategoriesCache();
    populateCategorySelect(document.getElementById("owner-business-category"), null);

    const businesses = await api("/api/businesses/mine");
    container.innerHTML = "";
    if (businesses.length === 0) {
      container.textContent = "You don't have a business yet — create one above.";
      return;
    }
    businesses.forEach((b) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.innerHTML = `<div><strong>${b.name}</strong><div class="meta">${b.address || ""}</div></div>`;
      const btn = document.createElement("button");
      btn.className = "btn btn-ghost btn-sm";
      btn.textContent = "Manage";
      btn.addEventListener("click", () => selectOwnerBusiness(b));
      item.appendChild(btn);
      container.appendChild(item);
    });
    if (ownerState.businessId && businesses.some((b) => b.id === ownerState.businessId)) {
      selectOwnerBusiness(businesses.find((b) => b.id === ownerState.businessId));
    }
  } catch (err) {
    container.textContent = err.message;
  }
}

document.getElementById("owner-business-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("owner-business-name").value;
  const address = document.getElementById("owner-business-address").value || null;
  const categoryValue = document.getElementById("owner-business-category").value;
  const category_id = categoryValue ? parseInt(categoryValue, 10) : null;
  try {
    const business = await api("/api/businesses", { method: "POST", body: { name, address, category_id } });
    document.getElementById("owner-business-form").reset();
    document.getElementById("owner-business-form").classList.add("hidden");
    await loadOwnerBusinesses();
    selectOwnerBusiness(business);
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById("owner-detail-category").addEventListener("change", async (e) => {
  const value = e.target.value;
  try {
    await api(`/api/businesses/${ownerState.businessId}`, {
      method: "PATCH",
      body: { category_id: value ? parseInt(value, 10) : null },
    });
  } catch (err) {
    alert(err.message);
  }
});

function selectOwnerBusiness(business) {
  ownerState.businessId = business.id;
  document.getElementById("owner-detail-panel").classList.remove("hidden");
  document.getElementById("owner-detail-heading").textContent = business.name;
  populateCategorySelect(document.getElementById("owner-detail-category"), business.category_id);
  loadOwnerServices(business.id);
  loadOwnerStaff(business.id);
  loadOwnerAppointments(business.id);
}

async function loadOwnerServices(businessId) {
  const container = document.getElementById("owner-service-list");
  container.textContent = "Loading...";
  try {
    const services = await api(`/api/businesses/${businessId}/services`);
    container.innerHTML = "";
    if (services.length === 0) container.textContent = "No services yet.";
    services.forEach((s) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.innerHTML = `<div><strong>${s.name}</strong><div class="meta">${s.duration_minutes} min &middot; $${s.price}</div></div>`;
      container.appendChild(item);
    });
  } catch (err) {
    container.textContent = err.message;
  }
}

document.getElementById("owner-service-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!ownerState.businessId) return;
  const body = {
    name: document.getElementById("owner-service-name").value,
    duration_minutes: parseInt(document.getElementById("owner-service-duration").value, 10),
    price: parseFloat(document.getElementById("owner-service-price").value),
  };
  try {
    await api(`/api/businesses/${ownerState.businessId}/services`, { method: "POST", body });
    document.getElementById("owner-service-form").reset();
    document.getElementById("owner-service-form").classList.add("hidden");
    loadOwnerServices(ownerState.businessId);
  } catch (err) {
    alert(err.message);
  }
});

async function loadOwnerStaff(businessId) {
  const container = document.getElementById("owner-staff-list");
  const select = document.getElementById("owner-hours-staff-select");
  container.textContent = "Loading...";
  try {
    const staff = await api(`/api/businesses/${businessId}/staff`);
    container.innerHTML = "";
    select.innerHTML = "";
    staff.forEach((s) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.innerHTML = `<div><strong>${s.full_name}</strong></div>`;
      container.appendChild(item);

      const option = document.createElement("option");
      option.value = s.id;
      option.textContent = s.full_name;
      select.appendChild(option);
    });
    if (staff.length > 0) {
      ownerState.staffId = staff[0].id;
      loadOwnerHours(staff[0].id);
    }
  } catch (err) {
    container.textContent = err.message;
  }
}

document.getElementById("owner-staff-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!ownerState.businessId) return;
  const full_name = document.getElementById("owner-staff-name").value;
  try {
    await api(`/api/businesses/${ownerState.businessId}/staff`, { method: "POST", body: { full_name } });
    document.getElementById("owner-staff-form").reset();
    document.getElementById("owner-staff-form").classList.add("hidden");
    loadOwnerStaff(ownerState.businessId);
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById("owner-hours-staff-select").addEventListener("change", (e) => {
  ownerState.staffId = parseInt(e.target.value, 10);
  loadOwnerHours(ownerState.staffId);
});

async function loadOwnerHours(staffId) {
  const container = document.getElementById("owner-hours-list");
  container.textContent = "Loading...";
  try {
    const hours = await api(`/api/staff/${staffId}/working-hours`);
    container.innerHTML = "";
    if (hours.length === 0) container.textContent = "No working hours set for this staff member yet.";
    hours.forEach((h) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.innerHTML = `<div><strong>${DAY_NAMES[h.day_of_week]}</strong><div class="meta">${h.start_time.slice(0, 5)} - ${h.end_time.slice(0, 5)}</div></div>`;
      const btn = document.createElement("button");
      btn.className = "btn btn-ghost btn-sm";
      btn.textContent = "Remove";
      btn.addEventListener("click", async () => {
        await api(`/api/working-hours/${h.id}`, { method: "DELETE" });
        loadOwnerHours(staffId);
      });
      item.appendChild(btn);
      container.appendChild(item);
    });
  } catch (err) {
    container.textContent = err.message;
  }
}

document.getElementById("owner-hours-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const staffId = parseInt(document.getElementById("owner-hours-staff-select").value, 10);
  if (!staffId) {
    alert("Add a staff member first.");
    return;
  }
  const body = {
    day_of_week: parseInt(document.getElementById("owner-hours-day").value, 10),
    start_time: document.getElementById("owner-hours-start").value,
    end_time: document.getElementById("owner-hours-end").value,
  };
  try {
    await api(`/api/staff/${staffId}/working-hours`, { method: "POST", body });
    loadOwnerHours(staffId);
  } catch (err) {
    alert(err.message);
  }
});

const ownerCalState = { year: new Date().getFullYear(), month: new Date().getMonth() };

async function loadOwnerAppointments(businessId) {
  const container = document.getElementById("owner-appointment-list");
  container.textContent = "Loading...";
  try {
    const appointments = await api(`/api/businesses/${businessId}/appointments`);
    renderCalendar("owner-appointments-calendar", appointments, ownerCalState, (a) => `${a.service_name} — ${a.customer_name}`);
    container.innerHTML = "";
    if (appointments.length === 0) container.textContent = "No appointments yet.";
    appointments.forEach((a) => {
      const item = document.createElement("div");
      item.className = "list-item";
      const when = new Date(a.start_time).toLocaleString();
      item.innerHTML = `<div><strong>${when}</strong><div class="meta">${a.service_name} with ${a.customer_name} (${a.customer_email})</div></div>
        <span class="status-badge status-${a.status}">${a.status.replace("_", " ")}</span>`;
      if (a.status === "confirmed" || a.status === "pending") {
        const actions = document.createElement("div");
        actions.style.display = "flex";
        actions.style.gap = ".4rem";
        [
          ["Complete", "completed"],
          ["No-show", "no_show"],
          ["Cancel", "cancelled"],
        ].forEach(([label, value]) => {
          const btn = document.createElement("button");
          btn.className = "btn btn-ghost btn-sm";
          btn.textContent = label;
          btn.addEventListener("click", async () => {
            await api(`/api/appointments/${a.id}/status`, { method: "PATCH", body: { status: value } });
            loadOwnerAppointments(businessId);
          });
          actions.appendChild(btn);
        });
        item.appendChild(actions);
      }
      container.appendChild(item);
    });
  } catch (err) {
    container.textContent = err.message;
  }
}

// ---------- Admin dashboard ----------

toggleForm("admin-new-category-btn", "admin-category-form");

function loadAdminData() {
  loadAdminCategories();
  loadAdminBusinesses();
  loadAdminUsers();
}

async function loadAdminCategories() {
  const container = document.getElementById("admin-category-list");
  container.textContent = "Loading...";
  try {
    const categories = await api("/api/categories", { auth: false });
    container.innerHTML = "";
    if (categories.length === 0) container.textContent = "No categories yet.";
    categories.forEach((c) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.innerHTML = `<div><strong>${c.name}</strong></div>`;
      const btn = document.createElement("button");
      btn.className = "btn btn-ghost btn-sm";
      btn.textContent = "Delete";
      btn.addEventListener("click", async () => {
        try {
          await api(`/api/admin/categories/${c.id}`, { method: "DELETE" });
          loadAdminCategories();
        } catch (err) {
          alert(err.message);
        }
      });
      item.appendChild(btn);
      container.appendChild(item);
    });
  } catch (err) {
    container.textContent = err.message;
  }
}

document.getElementById("admin-category-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("admin-category-name").value;
  try {
    await api("/api/admin/categories", { method: "POST", body: { name } });
    document.getElementById("admin-category-form").reset();
    document.getElementById("admin-category-form").classList.add("hidden");
    loadAdminCategories();
  } catch (err) {
    alert(err.message);
  }
});

async function loadAdminBusinesses() {
  const container = document.getElementById("admin-business-list");
  container.textContent = "Loading...";
  try {
    const businesses = await api("/api/admin/businesses");
    container.innerHTML = "";
    if (businesses.length === 0) container.textContent = "No businesses yet.";
    businesses.forEach((b) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.innerHTML = `<div><strong>${b.name}</strong><div class="meta">${b.owner_name} (${b.owner_email})${b.category_name ? " &middot; " + b.category_name : ""}</div></div>`;

      const select = document.createElement("select");
      ["active", "pending", "suspended"].forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s;
        opt.textContent = s;
        if (s === b.status) opt.selected = true;
        select.appendChild(opt);
      });
      select.addEventListener("change", async () => {
        try {
          await api(`/api/admin/businesses/${b.id}/status`, { method: "PATCH", body: { status: select.value } });
        } catch (err) {
          alert(err.message);
          loadAdminBusinesses();
        }
      });
      item.appendChild(select);
      container.appendChild(item);
    });
  } catch (err) {
    container.textContent = err.message;
  }
}

async function loadAdminUsers() {
  const container = document.getElementById("admin-user-list");
  container.textContent = "Loading...";
  try {
    const users = await api("/api/admin/users");
    container.innerHTML = "";
    if (users.length === 0) container.textContent = "No users yet.";
    users.forEach((u) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.innerHTML = `<div><strong>${u.full_name}</strong><div class="meta">${u.email}</div></div>`;

      const select = document.createElement("select");
      ["customer", "business_owner", "admin"].forEach((r) => {
        const opt = document.createElement("option");
        opt.value = r;
        opt.textContent = r;
        if (r === u.role) opt.selected = true;
        select.appendChild(opt);
      });
      const isSelf = state.user && u.id === state.user.id;
      if (isSelf) select.disabled = true;
      select.addEventListener("change", async () => {
        try {
          await api(`/api/admin/users/${u.id}/role`, { method: "PATCH", body: { role: select.value } });
        } catch (err) {
          alert(err.message);
          loadAdminUsers();
        }
      });
      item.appendChild(select);
      container.appendChild(item);
    });
  } catch (err) {
    container.textContent = err.message;
  }
}

// ---------- Notifications ----------

function timeAgo(dateStr) {
  const diffMs = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

async function loadNotifications() {
  if (!state.token) return;
  try {
    const notifications = await api("/api/notifications/me");
    const container = document.getElementById("notif-list");
    container.innerHTML = "";
    if (notifications.length === 0) container.textContent = "No notifications yet.";
    notifications.forEach((n) => {
      const item = document.createElement("div");
      item.className = `list-item${n.is_read ? "" : " unread"}`;
      item.innerHTML = `<div>${n.message}</div><div class="meta">${timeAgo(n.created_at)}</div>`;
      if (!n.is_read) {
        item.style.cursor = "pointer";
        item.addEventListener("click", async () => {
          await api(`/api/notifications/${n.id}/read`, { method: "POST" });
          loadNotifications();
        });
      }
      container.appendChild(item);
    });
    const unreadCount = notifications.filter((n) => !n.is_read).length;
    const badge = document.getElementById("notif-badge");
    badge.textContent = String(unreadCount);
    badge.classList.toggle("hidden", unreadCount === 0);
  } catch (err) {
    // notifications are non-critical to the rest of the app; fail silently
  }
}

document.getElementById("notif-bell-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  const panel = document.getElementById("notif-panel");
  panel.classList.toggle("hidden");
  if (!panel.classList.contains("hidden")) loadNotifications();
});

document.getElementById("notif-mark-all-btn").addEventListener("click", async () => {
  await api("/api/notifications/read-all", { method: "POST" });
  loadNotifications();
});

document.addEventListener("click", (e) => {
  const wrap = document.querySelector(".notif-wrap");
  if (wrap && !wrap.contains(e.target)) document.getElementById("notif-panel").classList.add("hidden");
});

// ---------- Render ----------

function render() {
  const loggedIn = !!state.token;
  document.getElementById("auth-section").classList.toggle("hidden", loggedIn);
  document.getElementById("app-section").classList.toggle("hidden", !loggedIn);
  document.getElementById("user-info").classList.toggle("hidden", !loggedIn);
  if (loggedIn) {
    document.getElementById("user-name").textContent = state.user.full_name;
    loadNotifications();
  }
  const role = loggedIn ? state.user.role : null;
  const isCustomer = role === "customer";
  const isOwner = role === "business_owner";
  const isAdmin = role === "admin";

  document.getElementById("assistant-tab-btn").classList.toggle("hidden", !isCustomer);
  document.getElementById("appointments-tab-btn").classList.toggle("hidden", !isCustomer);
  document.getElementById("owner-tab-btn").classList.toggle("hidden", !isOwner);
  document.getElementById("admin-tab-btn").classList.toggle("hidden", !isAdmin);

  if (isCustomer) loadServicePicker();

  if (loggedIn) {
    const currentActiveBtn = document.querySelector(".app-tab-btn.active");
    const needsDefault = !currentActiveBtn || currentActiveBtn.classList.contains("hidden");
    if (needsDefault) {
      const defaultView = isAdmin ? "admin-view" : isOwner ? "owner-view" : "assistant-view";
      activateAppTab(defaultView);
    }
  }
}

render();
