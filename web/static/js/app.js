// AI-Telefonist Client-Side Controller
document.addEventListener("DOMContentLoaded", () => {
  // Navigation & Tabs
  const navBtns = document.querySelectorAll(".nav-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");
  const pageTitle = document.getElementById("page-title");
  const pageSubtitle = document.getElementById("page-subtitle");

  const tabTitles = {
    "tab-console": { title: "Live Telefonie Console", subtitle: "Real-time spraak-naar-spraak cascade (Silero VAD + Whisper + Qwen2.5 + Piper ONNX)" },
    "tab-appointments": { title: "Afspraken & Intake Database", subtitle: "Overzicht van geboekte gesprekken, .ics kalenderdownloads en notificatie logs" },
    "tab-settings": { title: "Systeem Instellingen", subtitle: "Configureer bedrijfsinformatie, SMTP mailer, webhooks en lokale modellen" }
  };

  navBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      navBtns.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      document.getElementById(tabId).classList.add("active");

      if (tabTitles[tabId]) {
        pageTitle.innerText = tabTitles[tabId].title;
        pageSubtitle.innerText = tabTitles[tabId].subtitle;
      }

      if (tabId === "tab-appointments") {
        loadAppointments();
      }
    });
  });

  // Call Console State
  let ws = null;
  let audioContext = null;
  let micStream = null;
  let micNode = null;
  let isCallActive = false;
  let audioQueue = [];
  let isPlayingAudio = false;

  const btnCallToggle = document.getElementById("btn-call-toggle");
  const callToggleLabel = document.getElementById("call-toggle-label");
  const chatFeed = document.getElementById("chat-feed");
  const vadTag = document.getElementById("vad-tag");
  const canvas = document.getElementById("waveform-canvas");
  const canvasCtx = canvas.getContext("2d");
  const currentLangFlag = document.getElementById("current-lang-flag");
  const currentLangText = document.getElementById("current-lang-text");

  // Intake Slots
  const slotName = document.getElementById("slot-name");
  const slotCompany = document.getElementById("slot-company");
  const slotPhone = document.getElementById("slot-phone");
  const slotEmail = document.getElementById("slot-email");
  const slotReason = document.getElementById("slot-reason");
  const slotTime = document.getElementById("slot-time");
  const intakeStatusPill = document.getElementById("intake-status-pill");
  const btnManualConfirm = document.getElementById("btn-manual-confirm");

  // Waveform Animation Loop
  let analyser = null;
  let dataArray = null;

  function drawWaveform() {
    requestAnimationFrame(drawWaveform);
    canvasCtx.fillStyle = "rgba(15, 23, 42, 0.4)";
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);

    if (!analyser || !isCallActive) {
      // Idle straight line
      canvasCtx.beginPath();
      canvasCtx.moveTo(0, canvas.height / 2);
      canvasCtx.lineTo(canvas.width, canvas.height / 2);
      canvasCtx.strokeStyle = "rgba(255, 255, 255, 0.1)";
      canvasCtx.lineWidth = 2;
      canvasCtx.stroke();
      return;
    }

    analyser.getByteTimeDomainData(dataArray);
    canvasCtx.lineWidth = 2.5;
    canvasCtx.strokeStyle = "#3b82f6";
    canvasCtx.beginPath();

    const sliceWidth = canvas.width * 1.0 / analyser.frequencyBinCount;
    let x = 0;

    for (let i = 0; i < analyser.frequencyBinCount; i++) {
      const v = dataArray[i] / 128.0;
      const y = v * canvas.height / 2;
      if (i === 0) {
        canvasCtx.moveTo(x, y);
      } else {
        canvasCtx.lineTo(x, y);
      }
      x += sliceWidth;
    }
    canvasCtx.stroke();
  }
  drawWaveform();

  // Start / Stop Microphone Call
  btnCallToggle.addEventListener("click", async () => {
    if (isCallActive) {
      stopCall();
    } else {
      await startCall();
    }
  });

  async function startCall() {
    try {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/ws/call`;
      ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";

      ws.onopen = async () => {
        isCallActive = true;
        callToggleLabel.innerText = "Oproep Beëindigen";
        btnCallToggle.classList.remove("btn-primary");
        btnCallToggle.classList.add("btn-danger");
        appendMessage("system", "Oproep verbonden. De receptioniste luistert...");

        // Start Mic Audio
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        micStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true } });
        
        const source = audioContext.createMediaStreamSource(micStream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 512;
        dataArray = new Uint8Array(analyser.frequencyBinCount);
        source.connect(analyser);

        // Process audio in 512-sample blocks (16-bit PCM @ 16kHz)
        micNode = audioContext.createScriptProcessor(512, 1, 1);
        micNode.onaudioprocess = (e) => {
          if (!isCallActive || ws.readyState !== WebSocket.OPEN) return;
          const inputData = e.inputBuffer.getChannelData(0);
          
          // Convert Float32 to 16-bit PCM
          const pcm16 = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          ws.send(pcm16.buffer);
        };
        source.connect(micNode);
        micNode.connect(audioContext.destination);
      };

      ws.onmessage = async (event) => {
        const msg = JSON.parse(event.data);
        handleServerEvent(msg);
      };

      ws.onclose = () => {
        stopCall();
      };
    } catch (err) {
      console.error("Call error:", err);
      showToast("Kon microfoon niet openen: " + err.message);
      stopCall();
    }
  }

  function stopCall() {
    isCallActive = false;
    callToggleLabel.innerText = "Start Oproep (Mic)";
    btnCallToggle.classList.remove("btn-danger");
    btnCallToggle.classList.add("btn-primary");
    vadTag.innerText = "VAD: Standby";
    vadTag.style.color = "var(--text-muted)";

    if (micStream) {
      micStream.getTracks().forEach(track => track.stop());
      micStream = null;
    }
    if (micNode) {
      micNode.disconnect();
      micNode = null;
    }
    if (audioContext) {
      audioContext.close();
      audioContext = null;
      analyser = null;
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.close();
      ws = null;
    }
    appendMessage("system", "Oproep beëindigd.");
  }

  // Handle incoming server events
  function handleServerEvent(msg) {
    if (msg.type === "vad_state") {
      vadTag.innerText = msg.is_speaking ? "VAD: Spraak Gedetecteerd" : "VAD: Stilte";
      vadTag.style.color = msg.is_speaking ? "#34d399" : "var(--text-muted)";
    } else if (msg.type === "user_transcript") {
      updateLanguageBadge(msg.language);
      appendMessage("caller", msg.text, msg.language);
      if (msg.intake) updateIntakeSlots(msg.intake);
    } else if (msg.type === "agent_chunk") {
      appendMessage("agent", msg.text, msg.language);
      if (msg.audio_base64) {
        queueAudioPlayback(msg.audio_base64);
      }
    } else if (msg.type === "intake_update") {
      if (msg.intake) updateIntakeSlots(msg.intake);
    } else if (msg.type === "booking_confirmed") {
      showToast("🎉 Afspraak bevestigd & notificaties verstuurd!");
      intakeStatusPill.className = "status-pill confirmed";
      intakeStatusPill.innerText = "Afspraak Bevestigd";
      btnManualConfirm.disabled = true;
    }
  }

  function updateLanguageBadge(lang) {
    if (lang === "en") {
      currentLangFlag.innerText = "🇬🇧";
      currentLangText.innerText = "English";
    } else {
      currentLangFlag.innerText = "🇳🇱";
      currentLangText.innerText = "Nederlands";
    }
  }

  function appendMessage(role, text, lang = null) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-msg ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "msg-bubble";

    if (role === "caller") {
      const flag = lang === "en" ? "🇬🇧" : "🇳🇱";
      bubble.innerHTML = `<strong>Beller (${flag}):</strong> ${escapeHtml(text)}`;
    } else if (role === "agent") {
      bubble.innerHTML = `<strong>Sarah:</strong> ${escapeHtml(text)}`;
    } else {
      bubble.innerText = text;
    }

    msgDiv.appendChild(bubble);
    chatFeed.appendChild(msgDiv);
    chatFeed.scrollTop = chatFeed.scrollHeight;
  }

  function updateIntakeSlots(intake) {
    if (intake.caller_name) slotName.innerText = intake.caller_name;
    if (intake.company) slotCompany.innerText = intake.company;
    if (intake.phone) slotPhone.innerText = intake.phone;
    if (intake.email) slotEmail.innerText = intake.email;
    if (intake.reason) slotReason.innerText = intake.reason;
    if (intake.appointment_time_raw || intake.appointment_time_iso) {
      slotTime.innerText = intake.appointment_time_raw || intake.appointment_time_iso;
    }

    if (intake.caller_name && (intake.phone || intake.email)) {
      btnManualConfirm.disabled = false;
    }
  }

  // Audio Queue Playback
  function queueAudioPlayback(base64Wav) {
    audioQueue.push(base64Wav);
    if (!isPlayingAudio) {
      playNextAudio();
    }
  }

  function playNextAudio() {
    if (audioQueue.length === 0) {
      isPlayingAudio = false;
      return;
    }

    isPlayingAudio = true;
    const b64 = audioQueue.shift();
    const audio = new Audio("data:audio/wav;base64," + b64);
    audio.onended = () => {
      playNextAudio();
    };
    audio.onerror = () => {
      playNextAudio();
    };
    audio.play().catch(e => {
      console.warn("Audio playback error:", e);
      playNextAudio();
    });
  }

  // Text Simulator Input
  const simInput = document.getElementById("sim-input");
  const simSendBtn = document.getElementById("sim-send-btn");

  simSendBtn.addEventListener("click", sendSimulatedMessage);
  simInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendSimulatedMessage();
  });

  async function sendSimulatedMessage() {
    const text = simInput.value.trim();
    if (!text) return;
    simInput.value = "";

    // If WebSocket is open, send via WebSocket
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "text_input", text: text }));
      return;
    }

    // Otherwise use REST simulator endpoint
    appendMessage("caller", text);
    try {
      const res = await fetch("/api/simulate-call", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
      });
      const data = await res.json();
      appendMessage("agent", data.agent_text);
      if (data.intake) updateIntakeSlots(data.intake);
      if (data.booking_created) {
        showToast("🎉 Afspraak automatisch ingepland via simulatie!");
      }
    } catch (err) {
      console.error(err);
      showToast("Fout bij simulatie.");
    }
  }

  // Appointments Database Table
  let appointmentsData = [];
  const searchInput = document.getElementById("appointment-search");
  const filterPills = document.querySelectorAll(".filter-pill");
  const btnRefresh = document.getElementById("btn-refresh-appointments");
  let currentFilter = "all";

  async function loadAppointments() {
    const tbody = document.getElementById("appointments-tbody");
    tbody.innerHTML = '<tr><td colspan="6" class="loading-td">Afspraken laden...</td></tr>';

    try {
      const res = await fetch("/api/appointments");
      appointmentsData = await res.json();
      renderAppointmentsTable();
    } catch (err) {
      tbody.innerHTML = '<tr><td colspan="6" class="loading-td">Kon afspraken niet laden.</td></tr>';
    }
  }

  function renderAppointmentsTable() {
    const tbody = document.getElementById("appointments-tbody");
    const query = searchInput.value.toLowerCase().trim();

    let filtered = appointmentsData.filter(app => {
      if (currentFilter !== "all" && app.status !== currentFilter) return false;
      if (query) {
        const fullStr = `${app.caller_name} ${app.company} ${app.phone} ${app.email} ${app.reason}`.toLowerCase();
        return fullStr.includes(query);
      }
      return true;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="loading-td">Geen afspraken gevonden.</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map(app => `
      <tr>
        <td>
          <strong>${escapeHtml(app.caller_name)}</strong>
          ${app.company ? `<br><small style="color:var(--text-subtle);">${escapeHtml(app.company)}</small>` : ''}
        </td>
        <td>
          ${escapeHtml(app.phone || '—')}<br>
          <small style="color:var(--text-subtle);">${escapeHtml(app.email || '')}</small>
        </td>
        <td>
          <strong>${formatDateTime(app.start_time)}</strong>
        </td>
        <td>${escapeHtml(app.reason || '—')}</td>
        <td>
          <span class="status-pill ${app.status === 'confirmed' ? 'confirmed' : 'pending'}">
            ${app.status === 'confirmed' ? 'Bevestigd' : app.status}
          </span>
        </td>
        <td>
          <div style="display:flex; gap:6px;">
            <a href="/api/appointments/${app.id}/ics" class="btn btn-secondary" style="padding:6px 10px; font-size:12px;" title="Download .ics kalenderbestand">
              📅 .ics
            </a>
            <button onclick="dispatchNotification('${app.id}')" class="btn btn-secondary" style="padding:6px 10px; font-size:12px;" title="Verstuur e-mail & webhooks opnieuw">
              ✉️
            </button>
            <button onclick="deleteAppointment('${app.id}')" class="btn btn-danger" style="padding:6px 10px; font-size:12px;" title="Verwijderen">
              ✕
            </button>
          </div>
        </td>
      </tr>
    `).join("");
  }

  searchInput.addEventListener("input", renderAppointmentsTable);
  filterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      filterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      currentFilter = pill.getAttribute("data-filter");
      renderAppointmentsTable();
    });
  });
  btnRefresh.addEventListener("click", loadAppointments);

  // Global table actions
  window.dispatchNotification = async (id) => {
    try {
      const res = await fetch(`/api/appointments/${id}/dispatch`, { method: "POST" });
      if (res.ok) showToast("Notificatie opnieuw verstuurd!");
    } catch (e) {
      showToast("Fout bij versturen notificatie.");
    }
  };

  window.deleteAppointment = async (id) => {
    if (!confirm("Weet u zeker dat u deze afspraak wilt verwijderen?")) return;
    try {
      const res = await fetch(`/api/appointments/${id}`, { method: "DELETE" });
      if (res.ok) {
        showToast("Afspraak verwijderd.");
        loadAppointments();
      }
    } catch (e) {
      showToast("Fout bij verwijderen.");
    }
  };

  // Settings Save
  const btnSaveSettings = document.getElementById("btn-save-settings");
  if (btnSaveSettings) {
    btnSaveSettings.addEventListener("click", async () => {
      const payload = {
        "business.name": document.getElementById("cfg-biz-name").value,
        "business.receptionist_name": document.getElementById("cfg-biz-receptionist").value,
        "business.opening_hours": document.getElementById("cfg-biz-hours").value,
        "business.greeting_nl": document.getElementById("cfg-biz-greeting-nl").value,
        "business.greeting_en": document.getElementById("cfg-biz-greeting-en").value,
        "notifications.smtp.enabled": document.getElementById("cfg-smtp-enabled").checked,
        "notifications.smtp.host": document.getElementById("cfg-smtp-host").value,
        "notifications.smtp.port": parseInt(document.getElementById("cfg-smtp-port").value) || 587,
        "notifications.smtp.username": document.getElementById("cfg-smtp-user").value,
        "notifications.smtp.recipient_email": document.getElementById("cfg-smtp-recipient").value,
        "notifications.webhooks.enabled": document.getElementById("cfg-webhooks-enabled").checked,
        "notifications.webhooks.discord_url": document.getElementById("cfg-webhook-discord").value,
        "notifications.webhooks.slack_url": document.getElementById("cfg-webhook-slack").value,
        "notifications.webhooks.generic_webhook_url": document.getElementById("cfg-webhook-generic").value,
        "pipeline.asr.model_size": document.getElementById("cfg-whisper-model").value,
        "pipeline.asr.device": document.getElementById("cfg-whisper-device").value,
        "pipeline.llm.api_url": document.getElementById("cfg-llm-url").value,
        "pipeline.tts.voice_nl": document.getElementById("cfg-piper-nl").value,
        "pipeline.tts.voice_en": document.getElementById("cfg-piper-en").value
      };

      try {
        const res = await fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          showToast("Instellingen succesvol opgeslagen!");
        } else {
          showToast("Opslaan mislukt.");
        }
      } catch (e) {
        showToast("Fout bij opslaan instellingen.");
      }
    });
  }

  // Utilities
  function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.innerText = msg;
    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function formatDateTime(isoStr) {
    if (!isoStr) return "—";
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch (e) {
      return isoStr;
    }
  }
});
