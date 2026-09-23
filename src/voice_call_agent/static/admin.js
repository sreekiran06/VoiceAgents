// Admin Dashboard Controller

let allClients = [];
let activeDrawerClient = null;

// Auth State
const TOKEN_KEY = "sk_admin_token";
const USER_KEY = "sk_admin_user";

function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function getAuthUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "{}");
  } catch {
    return {};
  }
}

function setAuthSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// Authenticated fetch helper
async function authFetch(url, options = {}) {
  const token = getAuthToken();
  const headers = Object.assign({}, options.headers || {});
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  options.headers = headers;

  const res = await fetch(url, options);
  if (res.status === 401) {
    clearAuthSession();
    showLoginModal("Session expired. Please log in again.");
    throw new Error("Unauthorized");
  }
  return res;
}

// Auth Modal Controls
const authOverlay = document.getElementById("auth-overlay");
const authLoginForm = document.getElementById("auth-login-form");
const authErrorBanner = document.getElementById("auth-error-banner");
const btnAuthSubmit = document.getElementById("btn-auth-submit");
const authBtnText = document.getElementById("auth-btn-text");
const btnFillDemoCreds = document.getElementById("btn-fill-demo-creds");
const adminUserBadge = document.getElementById("admin-user-badge");
const adminUserEmail = document.getElementById("admin-user-email");
const btnAdminLogout = document.getElementById("btn-admin-logout");

function showLoginModal(errorMsg = null) {
  document.documentElement.classList.add("not-authenticated");
  document.body.classList.add("not-authenticated");
  if (authOverlay) {
    authOverlay.classList.add("active");
    authOverlay.style.setProperty("display", "flex", "important");
  }
  if (adminUserBadge) adminUserBadge.style.display = "none";
  if (authErrorBanner) {
    if (errorMsg) {
      authErrorBanner.textContent = errorMsg;
      authErrorBanner.style.display = "block";
    } else {
      authErrorBanner.style.display = "none";
    }
  }
}

function hideLoginModal() {
  document.documentElement.classList.remove("not-authenticated");
  document.body.classList.remove("not-authenticated");
  if (authOverlay) {
    authOverlay.classList.remove("active");
    authOverlay.style.setProperty("display", "none", "important");
  }
  const user = getAuthUser();
  if (adminUserBadge) {
    adminUserBadge.style.display = "flex";
    if (adminUserEmail) adminUserEmail.textContent = user.name || user.email || "Admin";
  }
}

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
  if (!getAuthToken()) {
    showLoginModal();
    return;
  }

  try {
    const [clientsRes, statsRes] = await Promise.all([
      authFetch("/api/clients"),
      authFetch("/api/clients/stats"),
    ]);

    if (!clientsRes.ok || !statsRes.ok) {
      throw new Error("Failed to load platform data");
    }

    allClients = await clientsRes.json();
    const stats = await statsRes.json();

    renderKPIs(stats);
    renderClientsTable();
  } catch (err) {
    if (err.message !== "Unauthorized") {
      showToast("Error loading clients: " + err.message, "error");
      clientsTbody.innerHTML = `<tr><td colspan="7" class="td-loading">Failed to load data. Please refresh.</td></tr>`;
    }
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
            <a href="/client?id=${encodeURIComponent(client.id)}" class="client-name" style="text-decoration: none; color: inherit; transition: color 0.15s ease;" onmouseover="this.style.color='#818cf8'" onmouseout="this.style.color='inherit'">${escapeHtml(client.name)}</a>
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
          <a href="/client?id=${encodeURIComponent(client.id)}" class="btn btn-primary btn-sm" title="Open Client Portal" style="text-decoration: none; font-weight: 600; padding: 6px 14px; display: inline-flex; align-items: center; gap: 4px;">
            Portal ↗
          </a>
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

// ==========================================================================
// Multi-Step Client Onboarding Wizard Controller
// ==========================================================================
let currentWizardStep = 1;
const totalWizardSteps = 4;

const modalSubtitle = document.getElementById("modal-subtitle");
const btnWizardPrev = document.getElementById("btn-wizard-prev");
const btnWizardNext = document.getElementById("btn-wizard-next");
const btnSaveClient = document.getElementById("btn-save-client");
const fileDropzone = document.getElementById("file-dropzone");
const formKnowledgeFile = document.getElementById("form-knowledge-file");
const fileUploadStatus = document.getElementById("file-upload-status");
const formKnowledgeText = document.getElementById("form-knowledge-text");

const stepSubtitles = {
  1: "Step 1 of 4: Company & Telephony Details",
  2: "Step 2 of 4: Business Knowledge & Persona Training",
  3: "Step 3 of 4: LLM & Voice Provider Configuration",
  4: "Step 4 of 4: Review Agent Summary & 1-Click Deploy",
};

function setWizardStep(step) {
  currentWizardStep = Math.max(1, Math.min(totalWizardSteps, step));

  // Update tabs
  document.querySelectorAll(".wizard-step-tab").forEach(tab => {
    const tabStep = parseInt(tab.dataset.step, 10);
    tab.classList.remove("active", "completed");
    if (tabStep === currentWizardStep) {
      tab.classList.add("active");
    } else if (tabStep < currentWizardStep) {
      tab.classList.add("completed");
    }
  });

  // Update panes
  for (let i = 1; i <= totalWizardSteps; i++) {
    const pane = document.getElementById(`wizard-step-${i}`);
    if (pane) {
      if (i === currentWizardStep) {
        pane.classList.add("active");
      } else {
        pane.classList.remove("active");
      }
    }
  }

  // Update subtitle
  if (modalSubtitle) {
    modalSubtitle.textContent = stepSubtitles[currentWizardStep] || "";
  }

  // Update navigation buttons
  if (btnWizardPrev) {
    btnWizardPrev.style.display = currentWizardStep > 1 ? "inline-flex" : "none";
  }
  if (btnWizardNext) {
    btnWizardNext.style.display = currentWizardStep < totalWizardSteps ? "inline-flex" : "none";
  }
  if (btnSaveClient) {
    btnSaveClient.style.display = currentWizardStep === totalWizardSteps ? "inline-flex" : "none";
  }

  if (currentWizardStep === 4) {
    populateWizardReview();
  }
}

function validateWizardStep(step) {
  if (step === 1) {
    const name = document.getElementById("form-name").value.trim();
    const contact = document.getElementById("form-contact").value.trim();
    const phone = document.getElementById("form-phone").value.trim();
    const email = document.getElementById("form-email").value.trim();
    const languages = Array.from(document.querySelectorAll("input[name='languages']:checked"));

    if (!name) {
      showToast("Please enter a business name.", "error");
      document.getElementById("form-name").focus();
      return false;
    }
    if (!contact) {
      showToast("Please enter a contact person.", "error");
      document.getElementById("form-contact").focus();
      return false;
    }
    if (!phone) {
      showToast("Please enter a contact phone number.", "error");
      document.getElementById("form-phone").focus();
      return false;
    }
    if (!email) {
      showToast("Please enter a contact email.", "error");
      document.getElementById("form-email").focus();
      return false;
    }
    if (languages.length === 0) {
      showToast("Please select at least one supported language.", "error");
      return false;
    }
  } else if (step === 2) {
    const agentName = document.getElementById("form-agent-name")?.value.trim();
    if (!agentName) {
      showToast("Please provide an AI agent persona name.", "error");
      document.getElementById("form-agent-name")?.focus();
      return false;
    }
  }
  return true;
}

function populateWizardReview() {
  const name = document.getElementById("form-name").value.trim() || "Untitled Business";
  const contact = document.getElementById("form-contact").value.trim() || "-";
  const industry = document.getElementById("form-industry").value;
  const plan = document.getElementById("form-plan").value;
  const virtualNumber = document.getElementById("form-virtual-number").value.trim() || "Auto-assigned";
  const agentName = document.getElementById("form-agent-name")?.value.trim() || "Kiran";
  const llmModel = document.getElementById("form-llm-model")?.value || "gemini-3.5-flash-lite";
  const knowledge = document.getElementById("form-knowledge-text")?.value.trim();
  const languages = Array.from(document.querySelectorAll("input[name='languages']:checked")).map(cb => cb.value);

  const reviewBizName = document.getElementById("review-business-name");
  const reviewIndustryPlan = document.getElementById("review-industry-plan");
  const reviewContact = document.getElementById("review-contact");
  const reviewVirtualNumber = document.getElementById("review-virtual-number");
  const reviewAgentName = document.getElementById("review-agent-name");
  const reviewLlmModel = document.getElementById("review-llm-model");
  const reviewLanguages = document.getElementById("review-languages");
  const reviewKnowledge = document.getElementById("review-knowledge-preview");

  if (reviewBizName) reviewBizName.textContent = name;
  if (reviewIndustryPlan) reviewIndustryPlan.textContent = `${industry} • ${plan} Plan`;
  if (reviewContact) reviewContact.textContent = contact;
  if (reviewVirtualNumber) reviewVirtualNumber.textContent = virtualNumber;
  if (reviewAgentName) reviewAgentName.textContent = agentName;
  if (reviewLlmModel) reviewLlmModel.textContent = llmModel;

  if (reviewLanguages) {
    reviewLanguages.innerHTML = languages
      .map(lang => `<span class="badge badge-subtle">${lang}</span>`)
      .join("");
  }

  if (reviewKnowledge) {
    reviewKnowledge.textContent = knowledge ? `${knowledge.substring(0, 180)}${knowledge.length > 180 ? "..." : ""}` : "Using industry template default FAQs";
  }
}

// Wizard Event Listeners
btnWizardNext?.addEventListener("click", () => {
  if (validateWizardStep(currentWizardStep)) {
    setWizardStep(currentWizardStep + 1);
  }
});

btnWizardPrev?.addEventListener("click", () => {
  setWizardStep(currentWizardStep - 1);
});

document.querySelectorAll(".wizard-step-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    const targetStep = parseInt(tab.dataset.step, 10);
    if (targetStep < currentWizardStep || validateWizardStep(currentWizardStep)) {
      setWizardStep(targetStep);
    }
  });
});

// File Upload & Drag-and-Drop
fileDropzone?.addEventListener("click", () => {
  formKnowledgeFile?.click();
});

fileDropzone?.addEventListener("dragover", e => {
  e.preventDefault();
  fileDropzone.classList.add("dragover");
});

fileDropzone?.addEventListener("dragleave", () => {
  fileDropzone.classList.remove("dragover");
});

fileDropzone?.addEventListener("drop", e => {
  e.preventDefault();
  fileDropzone.classList.remove("dragover");
  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    handleKnowledgeFileUpload(e.dataTransfer.files[0]);
  }
});

formKnowledgeFile?.addEventListener("change", e => {
  if (e.target.files && e.target.files.length > 0) {
    handleKnowledgeFileUpload(e.target.files[0]);
  }
});

function handleKnowledgeFileUpload(file) {
  if (!file) return;

  const reader = new FileReader();
  reader.onload = e => {
    const content = e.target.result;
    if (typeof content === "string") {
      const existing = formKnowledgeText.value.trim();
      formKnowledgeText.value = existing ? `${existing}\n\n${content.trim()}` : content.trim();

      const words = content.trim().split(/\s+/).length;
      if (fileUploadStatus) {
        fileUploadStatus.style.display = "block";
        fileUploadStatus.textContent = `✓ Ingested ${file.name} (~${words} words extracted for LLM training)`;
      }
      showToast(`Uploaded ${file.name} successfully!`);
    }
  };
  reader.onerror = () => {
    showToast(`Error reading file ${file.name}`, "error");
  };
  reader.readAsText(file);
}

// Open Add Client Modal
function openAddModal() {
  clientForm.reset();
  formClientId.value = "";
  modalTitle.textContent = "Onboard New Business Client";
  document.getElementById("form-minutes-limit").value = "2500";
  if (fileUploadStatus) fileUploadStatus.style.display = "none";
  setWizardStep(1);
  modalBackdrop.classList.remove("hidden");
}

// Open Edit Client Modal
function openEditModal(client) {
  formClientId.value = client.id;
  modalTitle.textContent = "Edit Client: " + client.name;
  document.getElementById("form-name").value = client.name || "";
  document.getElementById("form-contact").value = client.contact_person || "";
  document.getElementById("form-phone").value = client.phone || "";
  document.getElementById("form-email").value = client.email || "";
  document.getElementById("form-industry").value = client.industry || "Real Estate";
  document.getElementById("form-virtual-number").value = client.virtual_number || "";
  document.getElementById("form-plan").value = client.plan || "Starter";
  document.getElementById("form-minutes-limit").value = client.monthly_minutes_limit || 1000;
  document.getElementById("form-webhook").value = client.webhook_url || "";
  document.getElementById("form-agent-name").value = client.agent_name || "Kiran";
  document.getElementById("form-greeting").value = client.greeting_text || "నమస్కారం! మీకు ఎలా సహాయం చేయగలను?";
  document.getElementById("form-knowledge-text").value = client.knowledge_text || "";
  document.getElementById("form-llm-model").value = client.llm_model || "gemini-3.5-flash-lite";

  // Checkboxes
  const selectedLangs = client.languages || [];
  document.querySelectorAll("input[name='languages']").forEach(cb => {
    cb.checked = selectedLangs.includes(cb.value);
  });

  if (fileUploadStatus) fileUploadStatus.style.display = "none";
  setWizardStep(1);
  modalBackdrop.classList.remove("hidden");
}

function closeModal() {
  modalBackdrop.classList.add("hidden");
}

// Submit Form (Create or Update)
clientForm.addEventListener("submit", async event => {
  event.preventDefault();

  if (!validateWizardStep(1) || !validateWizardStep(2)) {
    return;
  }

  const id = formClientId.value;
  const languages = Array.from(document.querySelectorAll("input[name='languages']:checked")).map(cb => cb.value);

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
    agent_name: document.getElementById("form-agent-name")?.value.trim() || "Kiran",
    greeting_text: document.getElementById("form-greeting")?.value.trim() || "నమస్కారం! మీకు ఎలా సహాయం చేయగలను?",
    knowledge_text: document.getElementById("form-knowledge-text")?.value.trim() || null,
    custom_llm_api_key: document.getElementById("form-custom-api-key")?.value.trim() || null,
    llm_model: document.getElementById("form-llm-model")?.value || "gemini-3.5-flash-lite",
  };

  btnSaveClient.disabled = true;
  btnSaveClient.textContent = "Deploying AI Agent...";

  try {
    const isEdit = Boolean(id);
    const url = isEdit ? `/api/clients/${id}` : "/api/clients";
    const method = isEdit ? "PATCH" : "POST";

    const res = await authFetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Request failed");
    }

    closeModal();
    showToast(isEdit ? "Client configuration updated." : `🚀 AI Voice Agent successfully deployed for ${payload.name}!`);
    await loadDashboardData();

    if (activeDrawerClient && activeDrawerClient.id === id) {
      const updated = allClients.find(c => c.id === id);
      if (updated) openDrawer(updated);
    }
  } catch (err) {
    showToast("Error deploying client: " + err.message, "error");
  } finally {
    btnSaveClient.disabled = false;
    btnSaveClient.textContent = "🚀 Deploy AI Agent";
  }
});

// Update Status (Active / Paused)
async function updateClientStatus(clientId, newStatus) {
  try {
    const res = await authFetch(`/api/clients/${clientId}`, {
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
    const res = await authFetch(`/api/clients/${clientId}`, { method: "DELETE" });
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

// ==========================================================================
// Enhanced Drawer Controller: Calls, Chat Transcripts, Leads & Config
// ==========================================================================
let activeSelectedCall = null;
let currentDrawerTab = "calls";

// Drawer Tab Switching
function initDrawerTabs() {
  const tabBtns = document.querySelectorAll(".drawer-tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.dataset.tab;
      switchDrawerTab(targetTab);
    });
  });
}

function switchDrawerTab(tabName) {
  currentDrawerTab = tabName;

  // Update tab buttons
  document.querySelectorAll(".drawer-tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });

  // Show/Hide tab content panes
  document.getElementById("tab-pane-calls").style.display = tabName === "calls" ? "block" : "none";
  document.getElementById("tab-pane-leads").style.display = tabName === "leads" ? "block" : "none";
  document.getElementById("tab-pane-config").style.display = tabName === "config" ? "block" : "none";

  // Pause audio if leaving calls tab
  if (tabName !== "calls") {
    const audioEl = document.getElementById("drawer-audio-element");
    if (audioEl && !audioEl.paused) {
      audioEl.pause();
      updateAudioPlayBtn(false);
    }
  }
}

// Audio Player Controller
const drawerAudioElement = document.getElementById("drawer-audio-element");
const btnAudioPlay = document.getElementById("btn-audio-play");
const audioScrubber = document.getElementById("audio-scrubber");
const audioCurrentTime = document.getElementById("audio-current-time");
const audioTotalDuration = document.getElementById("audio-total-duration");
const btnAudioDownload = document.getElementById("btn-audio-download");

function updateAudioPlayBtn(isPlaying) {
  if (!btnAudioPlay) return;
  btnAudioPlay.classList.toggle("playing", isPlaying);
  const playIcon = document.getElementById("play-icon");
  if (playIcon) playIcon.textContent = isPlaying ? "⏸" : "▶";
}

function formatAudioTime(seconds) {
  if (isNaN(seconds) || seconds < 0) return "00:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

if (btnAudioPlay && drawerAudioElement) {
  btnAudioPlay.addEventListener("click", () => {
    if (!drawerAudioElement.src) {
      showToast("No audio recording loaded for this call", "warning");
      return;
    }

    if (drawerAudioElement.paused) {
      drawerAudioElement.play().then(() => {
        updateAudioPlayBtn(true);
      }).catch(err => {
        showToast("Audio playback error: " + err.message, "error");
      });
    } else {
      drawerAudioElement.pause();
      updateAudioPlayBtn(false);
    }
  });

  drawerAudioElement.addEventListener("timeupdate", () => {
    if (!drawerAudioElement.duration) return;
    const pct = (drawerAudioElement.currentTime / drawerAudioElement.duration) * 100;
    if (audioScrubber) audioScrubber.value = pct || 0;
    if (audioCurrentTime) audioCurrentTime.textContent = formatAudioTime(drawerAudioElement.currentTime);
  });

  drawerAudioElement.addEventListener("loadedmetadata", () => {
    if (audioTotalDuration) audioTotalDuration.textContent = formatAudioTime(drawerAudioElement.duration);
  });

  drawerAudioElement.addEventListener("ended", () => {
    updateAudioPlayBtn(false);
    if (audioScrubber) audioScrubber.value = 0;
    if (audioCurrentTime) audioCurrentTime.textContent = "00:00";
  });

  audioScrubber?.addEventListener("input", e => {
    if (!drawerAudioElement.duration) return;
    const seekTime = (e.target.value / 100) * drawerAudioElement.duration;
    drawerAudioElement.currentTime = seekTime;
  });
}

function setupAudioPlayerForCall(call) {
  if (!drawerAudioElement) return;

  // Reset player
  drawerAudioElement.pause();
  updateAudioPlayBtn(false);
  if (audioScrubber) audioScrubber.value = 0;
  if (audioCurrentTime) audioCurrentTime.textContent = "00:00";

  const totalSecs = call.duration_seconds || 120;
  if (audioTotalDuration) audioTotalDuration.textContent = formatAudioTime(totalSecs);

  const audioUrl = call.recording_url || `/api/calls/${call.call_id}/audio`;
  drawerAudioElement.src = audioUrl;

  document.getElementById("audio-call-title").textContent = `Call with ${call.caller_phone}`;
  document.getElementById("audio-call-meta").textContent = `${call.call_time} • ${call.duration_seconds}s • Telephony WAV`;
  document.getElementById("audio-lang-badge").textContent = call.language_detected || "Telugu";

  if (btnAudioDownload) {
    btnAudioDownload.href = audioUrl;
    btnAudioDownload.setAttribute("download", `recording_${call.call_id}.wav`);
  }
}

// Render Active Call Chat Transcript (WhatsApp / iMessage Style)
function renderActiveCallChat(call, agentName) {
  setupAudioPlayerForCall(call);

  // Call Summary
  document.getElementById("call-sentiment-badge").textContent = call.sentiment || "🔥 High Intent";
  document.getElementById("call-summary-text").textContent = call.summary || "Conversation completed.";

  // Chat messages thread
  const chatThread = document.getElementById("chat-thread-messages");
  const transcript = call.transcript || [];

  if (transcript.length === 0) {
    chatThread.innerHTML = `
      <div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
        No spoken dialogue turns recorded for this call session.
      </div>
    `;
    return;
  }

  const effectiveAgent = agentName || "AI Voice Agent";

  chatThread.innerHTML = transcript
    .map(msg => {
      const isUser = msg.role === "user" || (msg.speaker && (msg.speaker.toLowerCase().includes("caller") || msg.speaker.toLowerCase().includes("user")));
      const speakerDisplay = isUser ? `Caller (${escapeHtml(call.caller_phone)})` : `${escapeHtml(effectiveAgent)} (AI)`;
      const avatarIcon = isUser ? "👤" : "🤖";
      const rowClass = isUser ? "user-row" : "agent-row";
      const timeStr = msg.time || msg.timestamp || "";

      return `
      <div class="chat-bubble-row ${rowClass}">
        <div class="chat-avatar">${avatarIcon}</div>
        <div class="chat-bubble-content">
          <div class="chat-bubble-header">
            <span class="chat-speaker-name">${speakerDisplay}</span>
          </div>
          <div class="chat-bubble">
            <span class="chat-bubble-text">${escapeHtml(msg.text || msg.content || "")}</span>
            ${timeStr ? `<span class="chat-time">${escapeHtml(timeStr)}</span>` : ""}
          </div>
        </div>
      </div>
    `;
    })
    .join("");
}

// Render Calls Tab
function renderDrawerCalls(client) {
  const calls = client.recent_calls || [];
  const badgeCallsCount = document.getElementById("badge-calls-count");
  if (badgeCallsCount) badgeCallsCount.textContent = calls.length;

  const selectorBar = document.getElementById("call-selector-bar");
  const activeContainer = document.getElementById("active-call-container");
  const emptyCalls = document.getElementById("empty-calls-state");

  if (calls.length === 0) {
    selectorBar.innerHTML = "";
    activeContainer.style.display = "none";
    emptyCalls.classList.remove("hidden");
    return;
  }

  emptyCalls.classList.add("hidden");
  activeContainer.style.display = "block";

  // If no active call or active call belongs to another client, select first
  if (!activeSelectedCall || !calls.some(c => c.call_id === activeSelectedCall.call_id)) {
    activeSelectedCall = calls[0];
  }

  // Populate call chips
  selectorBar.innerHTML = calls
    .map(call => {
      const isActive = activeSelectedCall && activeSelectedCall.call_id === call.call_id;
      return `
      <div class="call-chip ${isActive ? "active" : ""}" data-call-id="${call.call_id}">
        <div class="call-chip-top">
          <span>📞 ${escapeHtml(call.caller_phone)}</span>
          <span style="color: #93c5fd;">${call.duration_seconds}s</span>
        </div>
        <div class="call-chip-sub">
          <span>${escapeHtml(call.call_time)}</span> · <span>${escapeHtml(call.language_detected || "Telugu")}</span>
        </div>
      </div>
    `;
    })
    .join("");

  // Attach chip click listeners
  selectorBar.querySelectorAll(".call-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const callId = chip.dataset.callId;
      const found = calls.find(c => c.call_id === callId);
      if (found) {
        activeSelectedCall = found;
        selectorBar.querySelectorAll(".call-chip").forEach(c => c.classList.toggle("active", c.dataset.callId === callId));
        renderActiveCallChat(found, client.agent_name);
      }
    });
  });

  renderActiveCallChat(activeSelectedCall, client.agent_name);
}

// Render Leads Tab
function renderDrawerLeads(client) {
  const leads = client.leads || [];
  const badgeLeadsCount = document.getElementById("badge-leads-count");
  if (badgeLeadsCount) badgeLeadsCount.textContent = leads.length;

  // Update KPI counters
  const total = leads.length;
  const converted = leads.filter(l => l.status === "converted").length;
  const qualified = leads.filter(l => l.status === "qualified").length;
  const newCount = leads.filter(l => l.status === "new" || l.status === "contacted").length;

  document.getElementById("lead-kpi-total").textContent = total;
  document.getElementById("lead-kpi-converted").textContent = converted;
  document.getElementById("lead-kpi-qualified").textContent = qualified;
  document.getElementById("lead-kpi-new").textContent = newCount;

  const leadsList = document.getElementById("drawer-leads-list");
  const emptyLeads = document.getElementById("empty-leads-state");

  if (leads.length === 0) {
    leadsList.innerHTML = "";
    emptyLeads.classList.remove("hidden");
    return;
  }

  emptyLeads.classList.add("hidden");
  leadsList.innerHTML = leads
    .map(lead => {
      const budgetHtml = lead.budget ? `<div class="lead-meta-item">💰 Budget: <strong>${escapeHtml(lead.budget)}</strong></div>` : "";
      const locationHtml = lead.location ? `<div class="lead-meta-item">📍 Location: <strong>${escapeHtml(lead.location)}</strong></div>` : "";
      const timelineHtml = lead.timeline ? `<div class="lead-meta-item">⏱ Timeline: <strong>${escapeHtml(lead.timeline)}</strong></div>` : "";
      const callLinkHtml = lead.call_id ? `<button type="button" class="btn btn-ghost btn-sm btn-lead-view-call" data-call-id="${lead.call_id}" style="color: #93c5fd; padding: 2px 6px;">💬 View Call Chat</button>` : "";

      return `
      <div class="lead-card" data-lead-id="${lead.id}">
        <div class="lead-card-top">
          <div class="lead-name-col">
            <h4>${escapeHtml(lead.name || "Customer Lead")}</h4>
            <div class="lead-contact-line">
              <span>📞 <b>${escapeHtml(lead.phone)}</b></span>
              <button type="button" class="btn-copy-phone" title="Copy Phone" data-phone="${escapeHtml(lead.phone)}">📋 Copy</button>
              ${lead.email ? `<span>· ✉️ ${escapeHtml(lead.email)}</span>` : ""}
            </div>
          </div>
          <select class="lead-status-select status-${lead.status}" data-lead-id="${lead.id}">
            <option value="new" ${lead.status === "new" ? "selected" : ""}>🟣 New Lead</option>
            <option value="contacted" ${lead.status === "contacted" ? "selected" : ""}>🟡 Contacted</option>
            <option value="qualified" ${lead.status === "qualified" ? "selected" : ""}>🔵 Qualified</option>
            <option value="converted" ${lead.status === "converted" ? "selected" : ""}>🟢 Converted</option>
            <option value="lost" ${lead.status === "lost" ? "selected" : ""}>⚪ Lost</option>
          </select>
        </div>

        <div class="lead-req-box">
          <strong>Requirement:</strong> ${escapeHtml(lead.requirement)}
        </div>

        <div class="lead-meta-grid">
          ${budgetHtml}
          ${locationHtml}
          ${timelineHtml}
        </div>

        <div class="lead-footer">
          <span style="color: var(--text-muted);">Captured: ${escapeHtml(lead.created_at)}</span>
          ${callLinkHtml}
        </div>
      </div>
    `;
    })
    .join("");

  // Attach status change listeners
  leadsList.querySelectorAll(".lead-status-select").forEach(select => {
    select.addEventListener("change", async e => {
      const leadId = select.dataset.leadId;
      const newStatus = select.value;
      select.className = `lead-status-select status-${newStatus}`;

      try {
        const res = await authFetch(`/api/clients/${client.id}/leads/${leadId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        });

        if (!res.ok) throw new Error("Failed to update status");

        const targetLead = leads.find(l => l.id === leadId);
        if (targetLead) targetLead.status = newStatus;

        showToast(`Lead status updated to ${newStatus.toUpperCase()}`);
        renderDrawerLeads(client);
      } catch (err) {
        showToast("Error updating lead: " + err.message, "error");
      }
    });
  });

  // Attach copy phone listeners
  leadsList.querySelectorAll(".btn-copy-phone").forEach(btn => {
    btn.addEventListener("click", () => {
      const phone = btn.dataset.phone;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(phone);
        showToast(`Copied ${phone} to clipboard!`);
      }
    });
  });

  // Attach view call transcript listeners
  leadsList.querySelectorAll(".btn-lead-view-call").forEach(btn => {
    btn.addEventListener("click", () => {
      const callId = btn.dataset.callId;
      const calls = client.recent_calls || [];
      const matched = calls.find(c => c.call_id === callId);
      if (matched) {
        activeSelectedCall = matched;
        switchDrawerTab("calls");
        renderDrawerCalls(client);
      }
    });
  });
}

// Drawer Controller
function openDrawer(client) {
  activeDrawerClient = client;

  // Eyebrow & Titles
  document.getElementById("drawer-industry").textContent = client.industry;
  document.getElementById("drawer-header-number").textContent = client.virtual_number ? `📞 ${client.virtual_number}` : "No Virtual DID";
  document.getElementById("drawer-name").textContent = client.name;

  // Drawer tags
  const tagsContainer = document.getElementById("drawer-tags");
  tagsContainer.innerHTML = `
    <span class="badge badge-status-${client.status}">${client.status}</span>
    <span class="badge badge-plan">${client.plan} Plan</span>
    ${(client.languages || []).map(l => `<span class="badge badge-lang">${l}</span>`).join("")}
  `;

  // Performance numbers & Config Tab
  const pct = Math.min(100, Math.round((client.minutes_used / (client.monthly_minutes_limit || 1000)) * 100));
  document.getElementById("drawer-minutes-display").textContent = `${client.minutes_used.toLocaleString()} / ${client.monthly_minutes_limit.toLocaleString()} mins`;
  document.getElementById("drawer-progress-bar").style.width = `${pct}%`;
  document.getElementById("drawer-leads-display").textContent = client.leads ? client.leads.length : (client.leads_captured || 0);
  document.getElementById("drawer-bookings-display").textContent = client.appointments_booked || 0;
  document.getElementById("drawer-number-display").textContent = client.virtual_number || "Not assigned";

  // Persona & Brain settings
  document.getElementById("drawer-agent-name").textContent = client.agent_name || "Kiran (Voice Agent)";
  document.getElementById("drawer-greeting").textContent = client.greeting_text || "నమస్కారం! మీకు ఎలా సహాయం చేయగలను?";
  document.getElementById("drawer-llm-model").textContent = client.llm_model || "Google Gemini 3.5 Flash-Lite";
  document.getElementById("drawer-contact").textContent = client.contact_person;
  document.getElementById("drawer-phone-email").textContent = `${client.phone} · ${client.email}`;
  document.getElementById("drawer-plan").textContent = `${client.plan} (${client.monthly_minutes_limit} monthly minutes)`;
  document.getElementById("drawer-webhook").textContent = client.webhook_url || "None configured";

  // Render Tabs
  renderDrawerCalls(client);
  renderDrawerLeads(client);
  switchDrawerTab(currentDrawerTab || "calls");

  // Footer Actions
  const btnDrawerOpenPage = document.getElementById("btn-drawer-open-page");
  if (btnDrawerOpenPage) {
    btnDrawerOpenPage.href = `/client?id=${encodeURIComponent(client.id)}`;
  }

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
  if (drawerAudioElement && !drawerAudioElement.paused) {
    drawerAudioElement.pause();
    updateAudioPlayBtn(false);
  }
  drawerBackdrop.classList.add("hidden");
  activeDrawerClient = null;
}

initDrawerTabs();

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

// Outbound Call Modal Elements
const outboundModalBackdrop = document.getElementById("outbound-modal-backdrop");
const outboundModalClose = document.getElementById("outbound-modal-close");
const outboundModalCancel = document.getElementById("outbound-modal-cancel");
const outboundCallForm = document.getElementById("outbound-call-form");
const outboundProvider = document.getElementById("outbound-provider");
const outboundAppIdGroup = document.getElementById("outbound-app-id-group");
const btnAdminOutboundCall = document.getElementById("btn-admin-outbound-call");

function openOutboundModal() {
  if (outboundModalBackdrop) {
    outboundModalBackdrop.classList.remove("hidden");
  }
}

function closeOutboundModal() {
  if (outboundModalBackdrop) {
    outboundModalBackdrop.classList.add("hidden");
  }
}

if (outboundProvider && outboundAppIdGroup) {
  outboundProvider.addEventListener("change", () => {
    if (outboundProvider.value === "exotel") {
      outboundAppIdGroup.style.display = "block";
    } else {
      outboundAppIdGroup.style.display = "none";
    }
  });
}

btnAdminOutboundCall?.addEventListener("click", openOutboundModal);
outboundModalClose?.addEventListener("click", closeOutboundModal);
outboundModalCancel?.addEventListener("click", closeOutboundModal);
outboundModalBackdrop?.addEventListener("click", e => {
  if (e.target === outboundModalBackdrop) closeOutboundModal();
});

outboundCallForm?.addEventListener("submit", async e => {
  e.preventDefault();
  const provider = outboundProvider.value;
  const toNumber = document.getElementById("outbound-phone").value.trim();
  const appId = document.getElementById("outbound-app-id").value.trim() || undefined;
  const callerId = document.getElementById("outbound-caller-id").value.trim() || undefined;

  const btnSubmit = document.getElementById("btn-submit-outbound-call");
  btnSubmit.disabled = true;
  btnSubmit.textContent = "Placing call...";

  try {
    const res = await fetch("/telephony/call", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to_number: toNumber,
        from_number: callerId,
        provider: provider,
        app_id: appId,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || "Failed to trigger call");
    }

    showToast(`Call initiated via ${provider.toUpperCase()}! SID: ${data.call_sid || "queued"}`, "success");
    closeOutboundModal();
    loadDashboardData();
  } catch (err) {
    showToast(`Call error: ${err.message}`, "error");
  } finally {
    btnSubmit.disabled = false;
    btnSubmit.textContent = "Initiate Outbound Call";
  }
});

document.getElementById("btn-admin-test-call")?.addEventListener("click", () => {
  if (window.webPhone) window.webPhone.show();
});

// Auth Event Listeners
authLoginForm?.addEventListener("submit", async e => {
  e.preventDefault();
  const emailInput = document.getElementById("auth-email");
  const passwordInput = document.getElementById("auth-password");
  const email = emailInput.value.trim();
  const password = passwordInput.value.trim();

  if (!email || !password) {
    showLoginModal("Please provide both email and password.");
    return;
  }

  btnAuthSubmit.disabled = true;
  authBtnText.textContent = "Verifying...";
  if (authErrorBanner) authErrorBanner.style.display = "none";

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Invalid email or password");
    }

    setAuthSession(data.token, {
      id: data.user_id,
      name: data.name,
      user_type: data.user_type,
      email: email,
    });

    hideLoginModal();
    showToast(`Welcome back, ${data.name || "Admin"}!`);
    await loadDashboardData();
  } catch (err) {
    showLoginModal(err.message || "Failed to sign in.");
  } finally {
    btnAuthSubmit.disabled = false;
    authBtnText.textContent = "Sign In to Admin";
  }
});

btnFillDemoCreds?.addEventListener("click", () => {
  const emailInput = document.getElementById("auth-email");
  const passwordInput = document.getElementById("auth-password");
  if (emailInput) emailInput.value = "admin@skvoiceagents.com";
  if (passwordInput) passwordInput.value = "admin123";
  if (authLoginForm) {
    if (typeof authLoginForm.requestSubmit === "function") {
      authLoginForm.requestSubmit();
    } else {
      btnAuthSubmit?.click();
    }
  }
});

btnAdminLogout?.addEventListener("click", () => {
  clearAuthSession();
  showToast("Logged out successfully.");
  showLoginModal();
});

// Initial boot
if (!getAuthToken()) {
  showLoginModal();
} else {
  hideLoginModal();
  loadDashboardData();
}

