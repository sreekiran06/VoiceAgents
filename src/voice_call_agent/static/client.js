/**
 * SK Voice Agents - Dedicated Client Portal JavaScript
 * Handles individual client management, calls, audio playback, chat transcripts, leads CRM, and settings editing.
 */

// State
let currentClient = null;
let allClients = [];
let selectedCallId = null;
let audioPlayer = null;

// Get Client ID from URL query parameters
function getClientIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id") || "";
}

// Toast Notification
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// Escape HTML
function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// Format duration
function formatSeconds(secs) {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", async () => {
  audioPlayer = document.getElementById("client-portal-audio");
  setupTabNavigation();
  setupAudioPlayer();
  setupEditForm();
  setupFileUpload();
  setupTestCalls();
  setupOutboundCalls();

  await loadAllClientsAndCurrent();
});

// Load all clients for dropdown switcher and load the current client
async function loadAllClientsAndCurrent() {
  try {
    const res = await fetch("/api/clients");
    if (!res.ok) throw new Error("Failed to load clients list");
    allClients = await res.json();

    // Populate switcher dropdown
    const switcher = document.getElementById("client-select-switcher");
    switcher.innerHTML = allClients
      .map(c => `<option value="${c.id}">${escapeHtml(c.name)} (${escapeHtml(c.industry)})</option>`)
      .join("");

    switcher.addEventListener("change", (e) => {
      const selectedId = e.target.value;
      if (selectedId && selectedId !== currentClient?.id) {
        window.location.href = `/client?id=${encodeURIComponent(selectedId)}`;
      }
    });

    let targetId = getClientIdFromUrl();
    if (!targetId && allClients.length > 0) {
      targetId = allClients[0].id;
    }

    if (targetId) {
      switcher.value = targetId;
      await loadClientDetails(targetId);
    } else {
      showToast("No clients registered in the system", "error");
    }
  } catch (err) {
    showToast("Error loading client data: " + err.message, "error");
  }
}

// Load a specific client
async function loadClientDetails(clientId) {
  try {
    const res = await fetch(`/api/clients/${clientId}`);
    if (!res.ok) throw new Error("Client not found");
    currentClient = await res.json();

    document.title = `${currentClient.name} | SK Voice Agents Client Portal`;
    renderClientHero();
    renderCallsTab();
    renderLeadsTab();
    populateEditForm();
  } catch (err) {
    showToast("Error loading client: " + err.message, "error");
  }
}

// Render Header & Hero info
function renderClientHero() {
  if (!currentClient) return;

  document.getElementById("breadcrumb-client-name").textContent = currentClient.name;
  document.getElementById("client-hero-name").textContent = currentClient.name;
  document.getElementById("client-hero-industry").textContent = currentClient.industry;
  document.getElementById("client-hero-plan").textContent = `${currentClient.plan} Plan`;

  const statusBadge = document.getElementById("client-hero-status");
  statusBadge.textContent = currentClient.status;
  statusBadge.className = `badge badge-status-${currentClient.status}`;

  document.getElementById("client-hero-number").textContent = `📞 ${currentClient.virtual_number || "No number assigned"}`;

  const toggleBtn = document.getElementById("btn-toggle-client-status");
  toggleBtn.textContent = currentClient.status === "active" ? "⏸ Pause Agent" : "▶ Activate Agent";

  // KPIs
  document.getElementById("hero-minutes-val").textContent = `${(currentClient.minutes_used || 0).toLocaleString()} / ${(currentClient.monthly_minutes_limit || 1000).toLocaleString()} m`;
  
  const calls = currentClient.recent_calls || [];
  document.getElementById("hero-calls-val").textContent = calls.length;
  document.getElementById("portal-count-calls").textContent = calls.length;
  document.getElementById("sidebar-calls-total").textContent = calls.length;

  const leads = currentClient.leads || [];
  document.getElementById("hero-leads-val").textContent = leads.length;
  document.getElementById("portal-count-leads").textContent = leads.length;

  const convertedLeads = leads.filter(l => l.status === "converted" || l.status === "qualified").length;
  document.getElementById("hero-leads-sub").textContent = `${convertedLeads} qualified / booked`;

  document.getElementById("hero-agent-name").textContent = currentClient.agent_name || "Kiran";
  document.getElementById("hero-llm-sub").textContent = currentClient.llm_model || "gemini-3.5-flash-lite";

  // Avatar Icon
  const avatars = {
    "Real Estate": "🏢",
    "Clinics & Healthcare": "🏥",
    "Coaching & EdTech": "🎓",
    "Local Services": "🛠️",
    "Other": "💼"
  };
  document.getElementById("client-hero-avatar").textContent = avatars[currentClient.industry] || "🏢";
}

// Tab Navigation
function setupTabNavigation() {
  const tabs = document.querySelectorAll(".portal-tab-btn");
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetTab = btn.dataset.tab;
      tabs.forEach(t => t.classList.remove("active"));
      btn.classList.add("active");

      document.getElementById("pane-calls").style.display = targetTab === "calls" ? "block" : "none";
      document.getElementById("pane-leads").style.display = targetTab === "leads" ? "block" : "none";
      document.getElementById("pane-edit").style.display = targetTab === "edit" ? "block" : "none";
    });
  });

  document.getElementById("btn-scroll-to-edit").addEventListener("click", () => {
    document.getElementById("portal-tab-edit").click();
  });

  document.getElementById("btn-toggle-client-status").addEventListener("click", async () => {
    if (!currentClient) return;
    const newStatus = currentClient.status === "active" ? "paused" : "active";
    try {
      const res = await fetch(`/api/clients/${currentClient.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus })
      });
      if (!res.ok) throw new Error("Failed to update status");
      currentClient.status = newStatus;
      renderClientHero();
      showToast(`Agent is now ${newStatus}`, "success");
    } catch (err) {
      showToast("Error updating status: " + err.message, "error");
    }
  });
}

// ---------------------------------------------------------------------------
// Calls Tab Logic
// ---------------------------------------------------------------------------
function renderCallsTab() {
  const calls = currentClient.recent_calls || [];
  const listContainer = document.getElementById("calls-list-container");
  const emptyCalls = document.getElementById("empty-portal-calls");
  const activeWrap = document.getElementById("active-call-view-wrap");

  if (calls.length === 0) {
    listContainer.innerHTML = "";
    emptyCalls.classList.remove("hidden");
    activeWrap.style.display = "none";
    return;
  }

  emptyCalls.classList.add("hidden");
  activeWrap.style.display = "flex";
  activeWrap.style.flexDirection = "column";
  activeWrap.style.gap = "20px";

  listContainer.innerHTML = calls
    .map(call => {
      const isSelected = selectedCallId === call.call_id || (!selectedCallId && calls[0].call_id === call.call_id);
      if (isSelected && !selectedCallId) selectedCallId = call.call_id;

      return `
        <div class="call-card-item ${isSelected ? "selected" : ""}" data-call-id="${call.call_id}">
          <div class="call-card-top">
            <span class="call-card-phone">📞 ${escapeHtml(call.caller_phone)}</span>
            <span class="badge badge-intent">${escapeHtml(call.sentiment || "Inquiry")}</span>
          </div>
          <div class="call-card-meta">
            <span class="call-card-time">${escapeHtml(call.call_time)}</span>
            <span>•</span>
            <span class="badge badge-lang">${escapeHtml(call.language_detected || "Telugu")}</span>
            <span>•</span>
            <span>${formatSeconds(call.duration_seconds || 0)}</span>
          </div>
          <p class="call-card-summary-snip">${escapeHtml(call.summary || "No summary available")}</p>
        </div>
      `;
    })
    .join("");

  // Attach card click handlers
  listContainer.querySelectorAll(".call-card-item").forEach(card => {
    card.addEventListener("click", () => {
      selectedCallId = card.dataset.callId;
      listContainer.querySelectorAll(".call-card-item").forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      renderActiveCallDetail();
    });
  });

  renderActiveCallDetail();
}

function renderActiveCallDetail() {
  const calls = currentClient.recent_calls || [];
  const call = calls.find(c => c.call_id === selectedCallId) || calls[0];
  if (!call) return;

  // Title & Metadata
  document.getElementById("client-audio-title").textContent = `Call from ${call.caller_phone}`;
  document.getElementById("client-audio-meta").textContent = `${call.call_time} • ${formatSeconds(call.duration_seconds || 0)} • Telephony Stream`;
  document.getElementById("client-audio-lang").textContent = `${call.language_detected || "Telugu"}`;

  // Sentiment badge
  const sentimentBadge = document.getElementById("client-sentiment-badge");
  sentimentBadge.textContent = call.sentiment ? `🔥 ${call.sentiment} Intent` : "General Inquiry";

  // Summary
  document.getElementById("client-summary-text").textContent = call.summary || "No detailed summary available.";

  // Audio setup
  const audioUrl = call.recording_url || `/api/calls/${call.call_id}/audio`;
  audioPlayer.src = audioUrl;
  audioPlayer.load();

  const playIcon = document.getElementById("client-play-icon");
  playIcon.textContent = "▶";
  document.getElementById("client-audio-current").textContent = "00:00";
  document.getElementById("client-audio-total").textContent = formatSeconds(call.duration_seconds || 18);
  document.getElementById("client-audio-scrubber").value = 0;

  const downloadLink = document.getElementById("client-btn-download-audio");
  downloadLink.href = audioUrl;
  downloadLink.download = `recording_${call.call_id}.wav`;

  // Render WhatsApp / iMessage Chat-Style Transcript
  const chatThread = document.getElementById("client-chat-thread");
  const transcript = call.transcript || [];

  if (transcript.length === 0) {
    chatThread.innerHTML = `
      <div style="text-align: center; color: var(--text-muted); padding: 24px; font-size: 0.88rem;">
        No spoken transcript turns recorded for this call.
      </div>
    `;
    return;
  }

  const agentName = currentClient.agent_name || "AI Agent";

  chatThread.innerHTML = transcript
    .map(msg => {
      const isCaller = msg.role === "user" || msg.speaker === "Caller" || (msg.speaker && msg.speaker.toLowerCase().includes("caller"));
      const speakerDisplay = isCaller ? `Caller (${escapeHtml(call.caller_phone)})` : `AI Agent (${escapeHtml(agentName)})`;
      const timeDisplay = msg.time || "";

      return `
        <div class="chat-message ${isCaller ? "chat-caller" : "chat-agent"}">
          <div class="chat-avatar">${isCaller ? "👤" : "🤖"}</div>
          <div class="chat-bubble">
            <div class="chat-sender">
              <span>${escapeHtml(speakerDisplay)}</span>
              <span class="chat-timestamp">${escapeHtml(timeDisplay)}</span>
            </div>
            <div class="chat-text">${escapeHtml(msg.text)}</div>
          </div>
        </div>
      `;
    })
    .join("");
}

// Setup audio controls
function setupAudioPlayer() {
  const playBtn = document.getElementById("client-btn-audio-play");
  const playIcon = document.getElementById("client-play-icon");
  const scrubber = document.getElementById("client-audio-scrubber");
  const timeCur = document.getElementById("client-audio-current");
  const timeTot = document.getElementById("client-audio-total");

  playBtn.addEventListener("click", () => {
    if (!audioPlayer.src) return;
    if (audioPlayer.paused) {
      audioPlayer.play().catch(err => showToast("Audio play error: " + err.message, "error"));
      playIcon.textContent = "⏸";
    } else {
      audioPlayer.pause();
      playIcon.textContent = "▶";
    }
  });

  audioPlayer.addEventListener("timeupdate", () => {
    if (!isNaN(audioPlayer.duration) && audioPlayer.duration > 0) {
      const pct = (audioPlayer.currentTime / audioPlayer.duration) * 100;
      scrubber.value = pct;
      timeCur.textContent = formatSeconds(audioPlayer.currentTime);
      timeTot.textContent = formatSeconds(audioPlayer.duration);
    }
  });

  audioPlayer.addEventListener("ended", () => {
    playIcon.textContent = "▶";
    scrubber.value = 0;
    timeCur.textContent = "00:00";
  });

  scrubber.addEventListener("input", (e) => {
    if (!isNaN(audioPlayer.duration) && audioPlayer.duration > 0) {
      const seekTime = (e.target.value / 100) * audioPlayer.duration;
      audioPlayer.currentTime = seekTime;
    }
  });
}

// ---------------------------------------------------------------------------
// Leads Tab Logic
// ---------------------------------------------------------------------------
function renderLeadsTab() {
  const leads = currentClient.leads || [];
  const listContainer = document.getElementById("client-leads-list");
  const emptyLeads = document.getElementById("empty-portal-leads");

  // Update lead KPI counts
  document.getElementById("lead-stat-total").textContent = leads.length;
  document.getElementById("lead-stat-converted").textContent = leads.filter(l => l.status === "converted").length;
  document.getElementById("lead-stat-qualified").textContent = leads.filter(l => l.status === "qualified").length;
  document.getElementById("lead-stat-new").textContent = leads.filter(l => l.status === "new" || l.status === "contacted").length;

  if (leads.length === 0) {
    listContainer.innerHTML = "";
    emptyLeads.classList.remove("hidden");
    return;
  }

  emptyLeads.classList.add("hidden");

  listContainer.innerHTML = leads
    .map(lead => {
      return `
        <div class="lead-card status-${lead.status}" id="lead-card-${lead.id}">
          <div class="lead-card-header">
            <div class="lead-identity">
              <span class="lead-avatar">👤</span>
              <div>
                <strong class="lead-name">${escapeHtml(lead.name || "Anonymous Lead")}</strong>
                <span class="lead-phone">${escapeHtml(lead.phone || "-")}</span>
              </div>
            </div>
            <div class="lead-status-actions">
              <select class="lead-status-select" data-lead-id="${lead.id}">
                <option value="new" ${lead.status === "new" ? "selected" : ""}>New Inquiry</option>
                <option value="contacted" ${lead.status === "contacted" ? "selected" : ""}>Contacted</option>
                <option value="qualified" ${lead.status === "qualified" ? "selected" : ""}>Qualified</option>
                <option value="converted" ${lead.status === "converted" ? "selected" : ""}>Converted / Booked</option>
                <option value="lost" ${lead.status === "lost" ? "selected" : ""}>Lost</option>
              </select>
            </div>
          </div>

          <div class="lead-body">
            <div class="lead-requirement">
              <strong>Requirement:</strong> ${escapeHtml(lead.requirement || "-")}
            </div>

            <div class="lead-details-grid">
              ${lead.budget ? `<div class="lead-detail-item"><span>Budget:</span> <strong>${escapeHtml(lead.budget)}</strong></div>` : ""}
              ${lead.location ? `<div class="lead-detail-item"><span>Location:</span> <strong>${escapeHtml(lead.location)}</strong></div>` : ""}
              ${lead.timeline ? `<div class="lead-detail-item"><span>Timeline:</span> <strong>${escapeHtml(lead.timeline)}</strong></div>` : ""}
              <div class="lead-detail-item"><span>Captured:</span> <strong style="color: var(--text-muted);">${escapeHtml(lead.created_at || "Recent")}</strong></div>
            </div>

            ${lead.notes ? `<div class="lead-notes"><strong>Notes:</strong> ${escapeHtml(lead.notes)}</div>` : ""}
          </div>
        </div>
      `;
    })
    .join("");

  // Attach status change listeners
  listContainer.querySelectorAll(".lead-status-select").forEach(select => {
    select.addEventListener("change", async (e) => {
      const leadId = e.target.dataset.leadId;
      const newStatus = e.target.value;
      try {
        const res = await fetch(`/api/clients/${currentClient.id}/leads/${leadId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus })
        });
        if (!res.ok) throw new Error("Failed to update lead status");
        
        // Update local object
        const targetLead = currentClient.leads.find(l => l.id === leadId);
        if (targetLead) targetLead.status = newStatus;

        // Re-render KPI stats
        renderLeadsTab();
        showToast("Lead status updated to " + newStatus, "success");
      } catch (err) {
        showToast("Error updating lead: " + err.message, "error");
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Edit Tab Logic & Form Submission
// ---------------------------------------------------------------------------
function populateEditForm() {
  if (!currentClient) return;

  document.getElementById("edit-name").value = currentClient.name || "";
  document.getElementById("edit-contact").value = currentClient.contact_person || "";
  document.getElementById("edit-phone").value = currentClient.phone || "";
  document.getElementById("edit-email").value = currentClient.email || "";
  document.getElementById("edit-industry").value = currentClient.industry || "Real Estate";
  document.getElementById("edit-virtual-number").value = currentClient.virtual_number || "";
  document.getElementById("edit-plan").value = currentClient.plan || "Growth";
  document.getElementById("edit-minutes-limit").value = currentClient.monthly_minutes_limit || 2500;
  document.getElementById("edit-status").value = currentClient.status || "active";

  // Languages checkboxes
  const clientLangs = currentClient.languages || ["Telugu", "English"];
  document.querySelectorAll("input[name='edit-languages']").forEach(cb => {
    cb.checked = clientLangs.includes(cb.value);
  });

  // Persona & Brain
  document.getElementById("edit-agent-name").value = currentClient.agent_name || "Kiran";
  document.getElementById("edit-greeting").value = currentClient.greeting_text || "నమస్కారం! మీకు ఎలా సహాయం చేయగలను?";
  document.getElementById("edit-knowledge-text").value = currentClient.knowledge_text || "";

  // LLM & Integrations
  document.getElementById("edit-llm-model").value = currentClient.llm_model || "gemini-3.5-flash-lite";
  document.getElementById("edit-custom-api-key").value = currentClient.custom_llm_api_key || "";
  document.getElementById("edit-webhook").value = currentClient.webhook_url || "";
}

function setupEditForm() {
  const form = document.getElementById("client-edit-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentClient) return;

    const selectedLanguages = Array.from(
      document.querySelectorAll("input[name='edit-languages']:checked")
    ).map(cb => cb.value);

    if (selectedLanguages.length === 0) {
      showToast("Please select at least one supported language", "warning");
      return;
    }

    const payload = {
      name: document.getElementById("edit-name").value.trim(),
      contact_person: document.getElementById("edit-contact").value.trim(),
      phone: document.getElementById("edit-phone").value.trim(),
      email: document.getElementById("edit-email").value.trim(),
      industry: document.getElementById("edit-industry").value,
      virtual_number: document.getElementById("edit-virtual-number").value.trim(),
      plan: document.getElementById("edit-plan").value,
      monthly_minutes_limit: parseInt(document.getElementById("edit-minutes-limit").value, 10) || 1000,
      status: document.getElementById("edit-status").value,
      languages: selectedLanguages,
      agent_name: document.getElementById("edit-agent-name").value.trim(),
      greeting_text: document.getElementById("edit-greeting").value.trim(),
      knowledge_text: document.getElementById("edit-knowledge-text").value.trim(),
      llm_model: document.getElementById("edit-llm-model").value,
      custom_llm_api_key: document.getElementById("edit-custom-api-key").value.trim() || null,
      webhook_url: document.getElementById("edit-webhook").value.trim() || null
    };

    try {
      const res = await fetch(`/api/clients/${currentClient.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to update client");
      }

      currentClient = await res.json();
      renderClientHero();
      showToast("Client details & AI Agent configuration saved successfully!", "success");
    } catch (err) {
      showToast("Error saving changes: " + err.message, "error");
    }
  });
}

// File Upload to Knowledge Base
function setupFileUpload() {
  const dropzone = document.getElementById("edit-file-dropzone");
  const fileInput = document.getElementById("edit-knowledge-file");
  const statusDiv = document.getElementById("edit-file-upload-status");
  const knowledgeText = document.getElementById("edit-knowledge-text");

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    statusDiv.style.display = "block";
    statusDiv.textContent = `Reading ${file.name}...`;

    try {
      const text = await file.text();
      statusDiv.textContent = `✓ Ingested ${file.name} (${Math.round(file.size / 1024)} KB)`;
      statusDiv.style.color = "#10b981";

      const current = knowledgeText.value.trim();
      knowledgeText.value = current ? `${current}\n\n--- Ingested from ${file.name} ---\n${text}` : text;
      showToast(`Document text extracted into knowledge base`, "success");
    } catch (err) {
      statusDiv.textContent = `✗ Failed to read document: ${err.message}`;
      statusDiv.style.color = "#ef4444";
    }
  });
}

// ---------------------------------------------------------------------------
// Testing Calls
// ---------------------------------------------------------------------------
function setupTestCalls() {
  const testBtn = document.getElementById("btn-client-test-call");
  testBtn.addEventListener("click", () => {
    if (window.WebPhone) {
      window.WebPhone.open();
    } else {
      showToast("Web phone module loading...", "info");
    }
  });
}

function setupOutboundCalls() {
  const outboundBtn = document.getElementById("btn-client-outbound-call");
  const backdrop = document.getElementById("outbound-modal-backdrop");
  const closeBtn = document.getElementById("outbound-modal-close");
  const cancelBtn = document.getElementById("outbound-modal-cancel");
  const form = document.getElementById("outbound-call-form");

  outboundBtn.addEventListener("click", () => {
    if (currentClient && currentClient.phone) {
      document.getElementById("outbound-phone").value = currentClient.phone;
    }
    backdrop.classList.remove("hidden");
  });

  const closeModal = () => backdrop.classList.add("hidden");
  closeBtn.addEventListener("click", closeModal);
  cancelBtn.addEventListener("click", closeModal);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const provider = document.getElementById("outbound-provider").value;
    const phone = document.getElementById("outbound-phone").value.trim();
    const appId = document.getElementById("outbound-app-id").value.trim();

    const endpoint = provider === "exotel" ? "/api/telephony/exotel/call" : "/api/telephony/twilio/call";
    const payload = { customer_number: phone };
    if (appId) payload.app_id = appId;

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to trigger call");
      }
      showToast("Outbound call triggered successfully to " + phone, "success");
      closeModal();
    } catch (err) {
      showToast("Error triggering outbound call: " + err.message, "error");
    }
  });
}
