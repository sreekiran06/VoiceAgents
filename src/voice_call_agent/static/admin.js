// Admin Dashboard Controller

let allClients = [];
let activeDrawerClient = null;

// DOM Elements
const clientsTbody = document.getElementById("clients-tbody");
const emptyState = document.getElementById("empty-state");
const searchInput = document.getElementById("search-input");
const filterIndustry = document.getElementById("filter-industry");
const filterStatus = document.getElementById("filter-status");
const btnResetFilters = document.getElementById("btn-reset-filters");
const btnAddClient = document.getElementById("btn-add-client");
const btnRefresh = document.getElementById("btn-refresh");

// Modal Elements
const modalBackdrop = document.getElementById("modal-backdrop");
const modalTitle = document.getElementById("modal-title");
const modalClose = document.getElementById("modal-close");
const modalCancel = document.getElementById("modal-cancel");
const clientForm = document.getElementById("client-form");
const formClientId = document.getElementById("form-client-id");

// Drawer Elements
const drawerBackdrop = document.getElementById("drawer-backdrop");
const drawerClose = document.getElementById("drawer-close");
const btnDrawerToggleStatus = document.getElementById("btn-drawer-toggle-status");
const btnDrawerEdit = document.getElementById("btn-drawer-edit");

// Toast helper
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === "success" ? "✓" : "⚠"}</span> <div>${message}</div>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}

// Fetch stats and clients
async function loadDashboardData() {
  try {
    const [clientsRes, statsRes] = await Promise.all([
      fetch("/api/clients"),
      fetch("/api/clients/stats"),
    ]);

    if (!clientsRes.ok || !statsRes.ok) {
      throw new Error("Failed to load platform data");
    }

    allClients = await clientsRes.json();
    const stats = await statsRes.json();

    renderKPIs(stats);
    renderClientsTable();
  } catch (err) {
    showToast("Error loading clients: " + err.message, "error");
    clientsTbody.innerHTML = `<tr><td colspan="7" class="td-loading">Failed to load data. Please refresh.</td></tr>`;
  }
}

// Render KPI Cards
function renderKPIs(stats) {
  document.getElementById("kpi-total-clients").textContent = stats.total_clients || 0;
  document.getElementById("kpi-active-clients").textContent = `${stats.active_clients || 0} active calling accounts`;

  // Count distinct virtual numbers
  const activeNumbers = allClients.filter(c => c.virtual_number && c.status === "active").length;
  document.getElementById("kpi-active-numbers").textContent = activeNumbers || stats.active_clients || 0;

  document.getElementById("kpi-total-minutes").textContent = (stats.total_minutes_used || 0).toLocaleString() + " m";
  document.getElementById("kpi-total-leads").textContent = (stats.total_leads_captured || 0).toLocaleString();
  document.getElementById("kpi-total-appointments").textContent = `${stats.total_appointments_booked || 0} appointments booked`;
}

// Filter and Search Logic
function getFilteredClients() {
  const query = searchInput.value.toLowerCase().trim();
  const selectedIndustry = filterIndustry.value;
  const selectedStatus = filterStatus.value;

  return allClients.filter(c => {
    // Search match
    const matchSearch =
      !query ||
      c.name.toLowerCase().includes(query) ||
      c.contact_person.toLowerCase().includes(query) ||
      c.phone.includes(query) ||
      (c.virtual_number && c.virtual_number.includes(query)) ||
      c.email.toLowerCase().includes(query);

    // Industry match
    const matchIndustry = selectedIndustry === "All" || c.industry === selectedIndustry;

    // Status match
    const matchStatus = selectedStatus === "All" || c.status === selectedStatus;

    return matchSearch && matchIndustry && matchStatus;
  });
}

// Render Table Rows
function renderClientsTable() {
  const filtered = getFilteredClients();

  if (filtered.length === 0) {
    clientsTbody.innerHTML = "";
    emptyState.classList.remove("hidden");
    return;
  }

  emptyState.classList.add("hidden");
  clientsTbody.innerHTML = filtered
    .map(client => {
      const percentage = Math.min(
        100,
        Math.round((client.minutes_used / (client.monthly_minutes_limit || 1000)) * 100)
      );
      const isWarning = percentage >= 85;

      const langBadges = (client.languages || [])
        .map(lang => `<span class="badge badge-lang">${escapeHtml(lang)}</span>`)
        .join("");

      const statusBadge = `<span class="badge badge-status-${client.status}">${escapeHtml(client.status)}</span>`;

      return `
      <tr data-id="${client.id}">
        <td>
          <div class="client-info-cell">
            <span class="client-name">${escapeHtml(client.name)}</span>
            <span class="client-contact">${escapeHtml(client.contact_person)} · ${escapeHtml(client.phone)}</span>
          </div>
        </td>
        <td>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <span class="badge badge-industry">${escapeHtml(client.industry)}</span>
            <span class="badge badge-plan">${escapeHtml(client.plan)}</span>
          </div>
        </td>
        <td>
          <div style="display: flex; flex-wrap: wrap;">${langBadges}</div>
        </td>
        <td>
          <span class="mono-text">${escapeHtml(client.virtual_number || "Not assigned")}</span>
        </td>
        <td>
          <div class="quota-box">
            <div class="quota-label">
              <span>${client.minutes_used.toLocaleString()} m</span>
              <span>${client.monthly_minutes_limit.toLocaleString()} m</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill ${isWarning ? "warning" : ""}" style="width: ${percentage}%"></div>
            </div>
          </div>
        </td>
        <td>
          ${statusBadge}
        </td>
        <td class="td-actions">
          <button class="btn btn-ghost btn-sm btn-view-client" data-id="${client.id}" title="View Details">
            Details ↗
          </button>
          <button class="btn btn-ghost btn-sm btn-edit-client" data-id="${client.id}" title="Edit Client">
            ✏
          </button>
          <button class="btn btn-ghost btn-sm btn-toggle-status" data-id="${client.id}" title="Toggle Active/Paused">
            ${client.status === "active" ? "⏸" : "▶"}
          </button>
          <button class="btn btn-ghost btn-sm btn-delete-client" data-id="${client.id}" title="Delete Client" style="color: var(--accent-danger);">
            🗑
          </button>
        </td>
      </tr>
    `;
    })
    .join("");

  attachTableListeners();
}

function attachTableListeners() {
  // View Details
  document.querySelectorAll(".btn-view-client").forEach(btn => {
    btn.addEventListener("click", () => {
      const client = allClients.find(c => c.id === btn.dataset.id);
      if (client) openDrawer(client);
    });
  });

  // Edit Client
  document.querySelectorAll(".btn-edit-client").forEach(btn => {
    btn.addEventListener("click", () => {
      const client = allClients.find(c => c.id === btn.dataset.id);
      if (client) openEditModal(client);
    });
  });

  // Toggle Status
  document.querySelectorAll(".btn-toggle-status").forEach(btn => {
    btn.addEventListener("click", async () => {
      const client = allClients.find(c => c.id === btn.dataset.id);
      if (!client) return;
      const newStatus = client.status === "active" ? "paused" : "active";
      await updateClientStatus(client.id, newStatus);
    });
  });

  // Delete Client
  document.querySelectorAll(".btn-delete-client").forEach(btn => {
    btn.addEventListener("click", async () => {
      const client = allClients.find(c => c.id === btn.dataset.id);
      if (!client) return;
      if (confirm(`Are you sure you want to remove ${client.name}?`)) {
        await deleteClient(client.id);
      }
    });
  });
}

// Open Add Client Modal
function openAddModal() {
  clientForm.reset();
  formClientId.value = "";
  modalTitle.textContent = "Add Business Client";
  document.getElementById("form-minutes-limit").value = "1000";
  modalBackdrop.classList.remove("hidden");
}

// Open Edit Client Modal
function openEditModal(client) {
  formClientId.value = client.id;
  modalTitle.textContent = "Edit Client: " + client.name;
  document.getElementById("form-name").value = client.name;
  document.getElementById("form-contact").value = client.contact_person;
  document.getElementById("form-phone").value = client.phone;
  document.getElementById("form-email").value = client.email;
  document.getElementById("form-industry").value = client.industry;
  document.getElementById("form-virtual-number").value = client.virtual_number || "";
  document.getElementById("form-plan").value = client.plan;
  document.getElementById("form-minutes-limit").value = client.monthly_minutes_limit || 1000;
  document.getElementById("form-webhook").value = client.webhook_url || "";

  // Checkboxes
  const selectedLangs = client.languages || [];
  document.querySelectorAll("input[name='languages']").forEach(cb => {
    cb.checked = selectedLangs.includes(cb.value);
  });

  modalBackdrop.classList.remove("hidden");
}

function closeModal() {
  modalBackdrop.classList.add("hidden");
}

// Submit Form (Create or Update)
clientForm.addEventListener("submit", async event => {
  event.preventDefault();

  const id = formClientId.value;
  const languages = Array.from(document.querySelectorAll("input[name='languages']:checked")).map(cb => cb.value);

  if (languages.length === 0) {
    alert("Please select at least one supported language.");
    return;
  }

  const payload = {
    name: document.getElementById("form-name").value.trim(),
    contact_person: document.getElementById("form-contact").value.trim(),
    phone: document.getElementById("form-phone").value.trim(),
    email: document.getElementById("form-email").value.trim(),
    industry: document.getElementById("form-industry").value,
    virtual_number: document.getElementById("form-virtual-number").value.trim(),
    plan: document.getElementById("form-plan").value,
    monthly_minutes_limit: parseInt(document.getElementById("form-minutes-limit").value, 10) || 1000,
    webhook_url: document.getElementById("form-webhook").value.trim() || null,
    languages: languages,
  };

  try {
    const isEdit = Boolean(id);
    const url = isEdit ? `/api/clients/${id}` : "/api/clients";
    const method = isEdit ? "PATCH" : "POST";

    const res = await fetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: json.stringify ? JSON.stringify(payload) : "{}",
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Request failed");
    }

    closeModal();
    showToast(isEdit ? "Client details updated successfully." : "New client registered successfully.");
    await loadDashboardData();

    if (activeDrawerClient && activeDrawerClient.id === id) {
      const updated = allClients.find(c => c.id === id);
      if (updated) openDrawer(updated);
    }
  } catch (err) {
    showToast("Error saving client: " + err.message, "error");
  }
});

// Update Status (Active / Paused)
async function updateClientStatus(clientId, newStatus) {
  try {
    const res = await fetch(`/api/clients/${clientId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });

    if (!res.ok) throw new Error("Failed to update status");

    showToast(`Client status changed to ${newStatus}.`);
    await loadDashboardData();

    if (activeDrawerClient && activeDrawerClient.id === clientId) {
      const updated = allClients.find(c => c.id === clientId);
      if (updated) openDrawer(updated);
    }
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
}

// Delete Client
async function deleteClient(clientId) {
  try {
    const res = await fetch(`/api/clients/${clientId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete client");

    showToast("Client removed from platform.");
    if (activeDrawerClient && activeDrawerClient.id === clientId) {
      closeDrawer();
    }
    await loadDashboardData();
  } catch (err) {
    showToast("Error deleting client: " + err.message, "error");
  }
}

// Drawer Controller
function openDrawer(client) {
  activeDrawerClient = client;

  document.getElementById("drawer-industry").textContent = client.industry;
  document.getElementById("drawer-name").textContent = client.name;

  // Drawer tags
  const tagsContainer = document.getElementById("drawer-tags");
  tagsContainer.innerHTML = `
    <span class="badge badge-status-${client.status}">${client.status}</span>
    <span class="badge badge-plan">${client.plan} Plan</span>
    ${client.languages.map(l => `<span class="badge badge-lang">${l}</span>`).join("")}
  `;

  // Performance numbers
  const pct = Math.min(100, Math.round((client.minutes_used / (client.monthly_minutes_limit || 1000)) * 100));
  document.getElementById("drawer-minutes-display").textContent = `${client.minutes_used.toLocaleString()} / ${client.monthly_minutes_limit.toLocaleString()} mins`;
  document.getElementById("drawer-progress-bar").style.width = `${pct}%`;
  document.getElementById("drawer-leads-display").textContent = client.leads_captured || 0;
  document.getElementById("drawer-bookings-display").textContent = client.appointments_booked || 0;
  document.getElementById("drawer-number-display").textContent = client.virtual_number || "Not assigned";

  // Account details
  document.getElementById("drawer-contact").textContent = client.contact_person;
  document.getElementById("drawer-phone-email").textContent = `${client.phone} · ${client.email}`;
  document.getElementById("drawer-plan").textContent = `${client.plan} (${client.monthly_minutes_limit} monthly minutes)`;
  document.getElementById("drawer-webhook").textContent = client.webhook_url || "None configured";

  // Calls list
  const callsContainer = document.getElementById("drawer-calls-list");
  const calls = client.recent_calls || [];
  document.getElementById("drawer-call-count").textContent = `${calls.length} calls logged`;

  if (calls.length === 0) {
    callsContainer.innerHTML = `
      <div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
        No call logs recorded yet. Inbound calls to this virtual number will appear here in real time.
      </div>
    `;
  } else {
    callsContainer.innerHTML = calls
      .map(call => {
        const transcriptLines = (call.transcript || [])
          .map(t => `<div class="transcript-line"><b>${escapeHtml(t.speaker)}:</b> <span>${escapeHtml(t.text)}</span></div>`)
          .join("");

        return `
        <div class="call-card-item">
          <div class="call-card-top">
            <span>📞 <b>${escapeHtml(call.caller_phone)}</b></span>
            <span>${escapeHtml(call.call_time)} · ${call.duration_seconds}s</span>
          </div>
          <div style="display: flex; gap: 6px; margin-top: 2px;">
            <span class="badge badge-lang">${escapeHtml(call.language_detected || "Telugu")}</span>
            <span class="badge badge-status-${call.status === "completed" ? "active" : "paused"}">${call.status}</span>
          </div>
          <p class="call-card-summary">${escapeHtml(call.summary)}</p>
          ${transcriptLines ? `<div class="call-transcript-box">${transcriptLines}</div>` : ""}
        </div>
      `;
      })
      .join("");
  }

  // Footer Actions
  btnDrawerToggleStatus.textContent = client.status === "active" ? "Pause Account" : "Activate Account";
  btnDrawerToggleStatus.onclick = () => {
    const nextStatus = client.status === "active" ? "paused" : "active";
    updateClientStatus(client.id, nextStatus);
  };

  btnDrawerEdit.onclick = () => {
    closeDrawer();
    openEditModal(client);
  };

  drawerBackdrop.classList.remove("hidden");
}

function closeDrawer() {
  drawerBackdrop.classList.add("hidden");
  activeDrawerClient = null;
}

// HTML escape helper
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Event Listeners
searchInput.addEventListener("input", renderClientsTable);
filterIndustry.addEventListener("change", renderClientsTable);
filterStatus.addEventListener("change", renderClientsTable);

btnResetFilters.addEventListener("click", () => {
  searchInput.value = "";
  filterIndustry.value = "All";
  filterStatus.value = "All";
  renderClientsTable();
});

btnAddClient.addEventListener("click", openAddModal);
modalClose.addEventListener("click", closeModal);
modalCancel.addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", e => {
  if (e.target === modalBackdrop) closeModal();
});

drawerClose.addEventListener("click", closeDrawer);
drawerBackdrop.addEventListener("click", e => {
  if (e.target === drawerBackdrop) closeDrawer();
});

btnRefresh.addEventListener("click", () => {
  showToast("Refreshing data...");
  loadDashboardData();
});

document.getElementById("btn-admin-test-call")?.addEventListener("click", () => {
  if (window.webPhone) window.webPhone.show();
});

// Initial boot
loadDashboardData();
