(() => {
  const BOOTSTRAP_CACHE_KEY = "yartix_bootstrap_cache_v1";
  const BOOTSTRAP_CACHE_MAX_AGE_MS = 2 * 60 * 1000;
  const BOOTSTRAP_REQUEST_TIMEOUT_MS = 6000;

  const state = {
    bootstrap: null,
    registrationEndDate: "2026-06-06",
    countdownTimer: null,
    elderMode: false,
    currentCardIndex: 0,
    cardCount: 0,
    policyReadCompleted: false,
    bootstrapReady: false,
    bgPreloadStarted: false,
    bootstrapFetchPromise: null,
  };

  const ui = {
    heroSection: document.getElementById("heroSection"),
    countdown: document.getElementById("countdown"),
    globalNotice: document.getElementById("globalNotice"),
    launcher: document.getElementById("launcher"),
    countInput: document.getElementById("countInput"),
    agree: document.getElementById("agree"),
    elderModeToggle: document.getElementById("elderModeToggle"),
    startBtn: document.getElementById("startBtn"),
    launcherMessage: document.getElementById("launcherMessage"),
    agreeReadHint: document.getElementById("agreeReadHint"),
    policyDrawer: document.getElementById("policyDrawer"),
    policyContent: document.getElementById("policyContent"),
    formSection: document.getElementById("formSection"),
    participantPager: document.getElementById("participantPager"),
    prevParticipantBtn: document.getElementById("prevParticipantBtn"),
    nextParticipantBtn: document.getElementById("nextParticipantBtn"),
    participantProgress: document.getElementById("participantProgress"),
    participantsContainer: document.getElementById("participantsContainer"),
    submitBar: document.querySelector(".submit-bar"),
    submitBtn: document.getElementById("submitBtn"),
    submitMessage: document.getElementById("submitMessage"),
    confirmSection: document.getElementById("confirmSection"),
    confirmCount: document.getElementById("confirmCount"),
    bankInfoList: document.getElementById("bankInfoList"),
    summaryTableBody: document.querySelector("#summaryTable tbody"),
    lineLink: document.getElementById("lineLink"),
  };

  function toInt(value, fallback = 0) {
    const n = Number.parseInt(value, 10);
    return Number.isNaN(n) ? fallback : n;
  }

  function setMessage(element, text, className) {
    if (!element) {
      return;
    }
    element.textContent = text;
    element.className = className;
  }

  function applyBootstrapPayload(payload) {
    state.bootstrap = payload;
    state.bootstrapReady = true;
    state.registrationEndDate = state.bootstrap.registration_end_date || "2026-06-06";

    const notices = [state.bootstrap.warning || ""]
      .filter(Boolean)
      .join(" ");
    ui.globalNotice.textContent = notices;

    if (state.bootstrap.sold_out) {
      ui.countdown.textContent = "目前已額滿";
      ui.launcher.classList.add("hidden-ui");
      return;
    }

    ui.launcher.classList.remove("hidden-ui");
  }

  function saveBootstrapToLocalCache(payload) {
    try {
      window.localStorage.setItem(
        BOOTSTRAP_CACHE_KEY,
        JSON.stringify({
          ts: Date.now(),
          payload,
        })
      );
    } catch (_error) {
      // Ignore localStorage quota or privacy-mode errors.
    }
  }

  function loadBootstrapFromLocalCache() {
    try {
      const raw = window.localStorage.getItem(BOOTSTRAP_CACHE_KEY);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      if (!parsed || !parsed.payload || typeof parsed.ts !== "number") {
        return null;
      }
      if (Date.now() - parsed.ts > BOOTSTRAP_CACHE_MAX_AGE_MS) {
        return null;
      }
      return parsed.payload;
    } catch (_error) {
      return null;
    }
  }

  function preloadHeroBackground() {
    if (state.bgPreloadStarted) {
      return;
    }
    state.bgPreloadStarted = true;

    const img = new Image();
    img.src = "/static/www.png";
    img.onload = () => {
      document.body.classList.add("bg-ready");
    };
  }

  function scheduleDeferredBackgroundLoad() {
    if (state.bgPreloadStarted) {
      return;
    }

    if ("requestIdleCallback" in window) {
      window.requestIdleCallback(() => preloadHeroBackground(), { timeout: 1500 });
      return;
    }

    window.setTimeout(() => preloadHeroBackground(), 300);
  }

  function setAgreeEnabled(enabled, hintText) {
    if (!ui.agree) {
      return;
    }
    ui.agree.disabled = !enabled;
    if (!enabled) {
      ui.agree.checked = false;
    }
    if (ui.agreeReadHint && hintText) {
      ui.agreeReadHint.textContent = hintText;
    }
  }

  async function ensurePolicyLoaded() {
    if (!ui.policyContent || ui.policyContent.dataset.loaded === "1") {
      return;
    }

    try {
      const response = await fetch("/static/content/policy.html?v=20260417-1");
      const html = await response.text();
      if (!response.ok) {
        throw new Error("公告內容讀取失敗");
      }
      ui.policyContent.innerHTML = html;
      ui.policyContent.dataset.loaded = "1";

      const noScrollNeeded = ui.policyContent.scrollHeight <= ui.policyContent.clientHeight + 4;
      if (noScrollNeeded) {
        state.policyReadCompleted = true;
        setAgreeEnabled(true, "已閱讀完成，可勾選同意後開始填寫。");
      }
    } catch (_error) {
      ui.policyContent.innerHTML = "<p class=\"mb-0 text-danger\">公告內容暫時無法載入，請稍後重試。</p>";
      ui.policyContent.dataset.loaded = "0";
    }
  }

  function setupPolicyReadGate() {
    if (!ui.policyDrawer || !ui.policyContent || !ui.agree) {
      return;
    }

    setAgreeEnabled(false, "請先展開下方公告並捲動閱讀到底，才可勾選同意。");

    ui.policyDrawer.addEventListener("toggle", async () => {
      if (!ui.policyDrawer.open) {
        return;
      }
      await ensurePolicyLoaded();
    });

    ui.policyContent.addEventListener("scroll", () => {
      if (state.policyReadCompleted) {
        return;
      }

      const threshold = 18;
      const reachBottom = ui.policyContent.scrollTop + ui.policyContent.clientHeight >= ui.policyContent.scrollHeight - threshold;
      if (reachBottom) {
        state.policyReadCompleted = true;
        setAgreeEnabled(true, "已閱讀完成，可勾選同意後開始填寫。");
      }
    });
  }

  function setElderMode(enabled) {
    state.elderMode = Boolean(enabled);
    document.body.classList.toggle("elder-mode", state.elderMode);
    window.localStorage.setItem("yartix_elder_mode", state.elderMode ? "1" : "0");
    if (ui.elderModeToggle) {
      ui.elderModeToggle.checked = state.elderMode;
    }
  }

  function initElderMode() {
    setElderMode(false);
    if (ui.elderModeToggle) {
      ui.elderModeToggle.addEventListener("change", (event) => {
        setElderMode(event.target.checked);
      });
    }
  }

  async function loadBootstrap(timeoutMs = BOOTSTRAP_REQUEST_TIMEOUT_MS) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch("/api/bootstrap", { method: "GET", signal: controller.signal });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.message || "無法讀取活動資訊，請稍後再試。");
      }

      applyBootstrapPayload(payload);
      saveBootstrapToLocalCache(payload);
      return payload;
    } catch (error) {
      if (error && error.name === "AbortError") {
        throw new Error("系統載入較慢，正在重試連線。");
      }
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }

  async function ensureBootstrapReady() {
    if (state.bootstrapReady && state.bootstrap) {
      return state.bootstrap;
    }

    if (!state.bootstrapFetchPromise) {
      state.bootstrapFetchPromise = (async () => {
        try {
          return await loadBootstrap(BOOTSTRAP_REQUEST_TIMEOUT_MS);
        } catch (firstError) {
          if (String(firstError.message || "").includes("正在重試連線")) {
            return loadBootstrap(12000);
          }
          throw firstError;
        }
      })().finally(() => {
        state.bootstrapFetchPromise = null;
      });
    }

    return state.bootstrapFetchPromise;
  }

  async function refreshBootstrapInBackground() {
    try {
      await ensureBootstrapReady();
    } catch (error) {
      const hasCache = Boolean(state.bootstrapReady && state.bootstrap);
      if (hasCache) {
        ui.globalNotice.textContent = "系統資料同步中，畫面將持續更新最新資訊。";
        return;
      }
      ui.countdown.textContent = error.message || "系統連線較慢，請稍後。";
    }
  }

  function startCountdown() {
    if (state.countdownTimer) {
      window.clearInterval(state.countdownTimer);
    }

    const tick = () => {
      const now = new Date();
      const endTime = new Date(`${state.registrationEndDate}T23:59:59`);
      const diff = Math.floor((endTime.getTime() - now.getTime()) / 1000);

      if (diff < 0) {
        ui.countdown.textContent = "報名已截止";
        ui.launcher.classList.add("hidden-ui");
        return;
      }

      const days = Math.floor(diff / 86400);
      const hours = Math.floor((diff % 86400) / 3600);
      const mins = Math.floor((diff % 3600) / 60);
      const secs = diff % 60;
      ui.countdown.textContent = `活動還剩 ${days} 天 ${hours} 時 ${mins} 分 ${secs} 秒`;
      if (state.bootstrapReady) {
        ui.launcher.classList.remove("hidden-ui");
      }
    };

    tick();
    state.countdownTimer = window.setInterval(tick, 1000);
  }

  function escapeHtml(text) {
    const map = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };
    return String(text).replace(/[&<>"']/g, (m) => map[m]);
  }

  function buildSelectOptions(dict) {
    return Object.entries(dict)
      .map(([label, price]) => `<option value="${escapeHtml(label)}">${escapeHtml(label)} (${price}元)</option>`)
      .join("");
  }

  function buildFoodOptions(list) {
    return list.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`).join("");
  }

  function buildAddonInputs(addons) {
    return Object.entries(addons)
      .map(
        ([key, cfg]) => `
        <label class="form-label mt-2">${escapeHtml(cfg.label)} (+${cfg.price})</label>
        <input type="number" class="form-control addon-input" data-addon-key="${escapeHtml(key)}" value="0" min="0" max="20" required>
      `
      )
      .join("");
  }

  function buildCard(index) {
    const ticketOptions = buildSelectOptions(state.bootstrap.ticket_types || {});
    const foodOptions = buildFoodOptions(state.bootstrap.food_types || []);
    const addonInputs = buildAddonInputs(state.bootstrap.addons || {});

    const sameAsPreviousControls = index > 0
      ? `
        <div class="copy-toggle-row mb-2">
          <label class="form-check-label d-block"><input type="checkbox" class="form-check-input me-1 copy-from-prev-phone">電話同上一位</label>
          <label class="form-check-label d-block"><input type="checkbox" class="form-check-input me-1 copy-from-prev-email">Email同上一位</label>
        </div>
      `
      : "";

    return `
      <article class="participant-card" data-card-index="${index}" data-current-step="1">
        <div class="participant-head">
          <h3>第 ${index + 1} 位參加者</h3>
          <span class="step-pill">步驟 1 / 3</span>
        </div>
        <div class="participant-body">
          <div class="step-panel active" data-step="1">
            <input type="text" class="form-control mb-2 field-name" placeholder="姓名" minlength="2" maxlength="20" required>
            <select class="form-select mb-2 field-gender" required>
              <option value="">選擇性別</option>
              <option value="男">男</option>
              <option value="女">女</option>
            </select>
            <input type="date" class="form-control mb-2 field-dob" title="請選擇西元出生日期，例如 1990-05-20" required>
            <input type="text" class="form-control mb-2 field-id-number" placeholder="身分證" minlength="10" maxlength="10" pattern="[A-Za-z][12][0-9]{8}" title="請輸入正確身分證字號格式，例如 A123456789" required>
            <input type="tel" class="form-control mb-2 field-phone" placeholder="電話" inputmode="numeric" pattern="09[0-9]{8}" title="請輸入 09 開頭的 10 碼手機號碼" required>
            <input type="email" class="form-control field-email" placeholder="Email" maxlength="80" required>
            ${sameAsPreviousControls}
            <div class="step-actions">
              <button type="button" class="btn btn-primary btn-next">下一步</button>
            </div>
          </div>

          <div class="step-panel" data-step="2">
            <select class="form-select mb-2 field-ticket" required>
              <option value="">選擇票種</option>
              ${ticketOptions}
            </select>

            <select class="form-select mb-2 field-food" required>
              <option value="">飲食選擇</option>
              ${foodOptions}
            </select>

            ${addonInputs}

            <div class="step-actions">
              <button type="button" class="btn btn-secondary btn-prev">上一步</button>
              <button type="button" class="btn btn-primary btn-next">下一步</button>
            </div>
          </div>

          <div class="step-panel" data-step="3">
            <div class="alert alert-info">
              第三步為資料確認，確認無誤後可直接送出。
            </div>
            <div class="confirm-preview"></div>
            <div class="confirm-amount fw-bold text-primary mt-2"></div>

            <div class="step-actions">
              <button type="button" class="btn btn-secondary btn-prev">上一步</button>
              <button type="button" class="btn btn-outline-primary btn-next-person">儲存並下一位</button>
            </div>
          </div>
        </div>
      </article>
    `;
  }

  function switchStep(card, nextStep) {
    const targetStep = Math.max(1, Math.min(3, nextStep));
    if (targetStep === 3) {
      renderConfirmPreview(card);
    }
    card.dataset.currentStep = String(targetStep);

    const pill = card.querySelector(".step-pill");
    if (pill) {
      pill.textContent = `步驟 ${targetStep} / 3`;
    }

    card.querySelectorAll(".step-panel").forEach((panel) => {
      const isActive = toInt(panel.dataset.step, 1) === targetStep;
      panel.classList.toggle("active", isActive);
    });

    updateSubmitBarVisibility();
  }

  function updateSubmitBarVisibility() {
    if (!ui.submitBar) {
      return;
    }

    const cards = Array.from(ui.participantsContainer.querySelectorAll(".participant-card"));
    if (cards.length === 0) {
      ui.submitBar.classList.add("hidden-ui");
      return;
    }

    const allConfirmed = cards.every((card) => toInt(card.dataset.currentStep, 1) === 3);
    ui.submitBar.classList.toggle("hidden-ui", !allConfirmed);
  }

  function updateParticipantPager() {
    if (!ui.participantPager) {
      return;
    }

    const isMulti = state.cardCount > 1;
    ui.participantPager.classList.toggle("hidden-ui", !isMulti);
    if (!isMulti) {
      return;
    }

    if (ui.participantProgress) {
      ui.participantProgress.textContent = `第 ${state.currentCardIndex + 1} 位，共 ${state.cardCount} 位`;
    }

    if (ui.prevParticipantBtn) {
      ui.prevParticipantBtn.disabled = state.currentCardIndex <= 0;
    }
    if (ui.nextParticipantBtn) {
      ui.nextParticipantBtn.disabled = state.currentCardIndex >= state.cardCount - 1;
    }
  }

  function updateParticipantVisibility() {
    const cards = ui.participantsContainer.querySelectorAll(".participant-card");
    const isMulti = state.cardCount > 1;

    cards.forEach((card, idx) => {
      const isActive = idx === state.currentCardIndex;
      card.classList.toggle("hidden-card", isMulti && !isActive);
      card.classList.toggle("active-card", !isMulti || isActive);
    });

    updateParticipantPager();
  }

  function goToParticipant(index) {
    const bounded = Math.max(0, Math.min(state.cardCount - 1, index));
    state.currentCardIndex = bounded;
    updateParticipantVisibility();
  }

  function moveToNextParticipantFromCard(card) {
    const index = toInt(card.dataset.cardIndex, 0);
    if (index < state.cardCount - 1) {
      goToParticipant(index + 1);
      const nextCard = ui.participantsContainer.querySelector(`.participant-card[data-card-index="${index + 1}"]`);
      const firstField = nextCard?.querySelector(".field-name");
      if (firstField) {
        firstField.focus();
      }
    }
  }

  function renderConfirmPreview(card) {
    const preview = card.querySelector(".confirm-preview");
    const amountNode = card.querySelector(".confirm-amount");
    if (!preview) {
      return;
    }

    const addonLines = [];
    let addonTotal = 0;
    card.querySelectorAll(".addon-input").forEach((addonInput) => {
      const key = addonInput.dataset.addonKey;
      const qty = toInt(addonInput.value, 0);
      if (qty > 0) {
        const cfg = (state.bootstrap.addons || {})[key];
        if (cfg) {
          const lineAmount = qty * toInt(cfg.price, 0);
          addonTotal += lineAmount;
          addonLines.push(`${escapeHtml(cfg.label)} x ${qty}（NT$ ${lineAmount}）`);
        }
      }
    });

    const name = card.querySelector(".field-name")?.value.trim() || "";
    const gender = card.querySelector(".field-gender")?.value || "";
    const dob = card.querySelector(".field-dob")?.value || "";
    const idNumber = card.querySelector(".field-id-number")?.value.trim() || "";
    const phone = card.querySelector(".field-phone")?.value.trim() || "";
    const email = card.querySelector(".field-email")?.value.trim() || "";
    const ticket = card.querySelector(".field-ticket")?.value || "";
    const food = card.querySelector(".field-food")?.value || "";
    const ticketPrice = toInt((state.bootstrap.ticket_types || {})[ticket], 0);
    const personTotal = ticketPrice + addonTotal;

    preview.innerHTML = [
      `<p class="mb-1">姓名：${escapeHtml(name)}</p>`,
      `<p class="mb-1">性別：${escapeHtml(gender)}</p>`,
      `<p class="mb-1">出生年月日：${escapeHtml(dob)}</p>`,
      `<p class="mb-1">身分證字號：${escapeHtml(idNumber)}</p>`,
      `<p class="mb-1">電話：${escapeHtml(phone)}</p>`,
      `<p class="mb-1">Email：${escapeHtml(email)}</p>`,
      `<p class="mb-1">票種：${escapeHtml(ticket)}</p>`,
      `<p class="mb-1">飲食：${escapeHtml(food)}</p>`,
      `<p class="mb-0">加購：${addonLines.length ? addonLines.join("、") : "無"}</p>`,
    ].join("");

    if (amountNode) {
      amountNode.textContent = `本位參加者金額：NT$ ${personTotal}`;
    }
  }

  function validateCurrentStep(card) {
    const current = toInt(card.dataset.currentStep, 1);
    const panel = card.querySelector(`.step-panel[data-step="${current}"]`);
    if (!panel) {
      return false;
    }

    const fields = panel.querySelectorAll("input, select");
    for (const field of fields) {
      if (!field.checkValidity()) {
        field.reportValidity();
        return false;
      }
    }

    const idField = card.querySelector(".field-id-number");
    if (idField && idField.value && !/^[A-Za-z][12][0-9]{8}$/.test(idField.value.trim())) {
      idField.setCustomValidity("請輸入正確身分證字號格式");
      idField.reportValidity();
      idField.setCustomValidity("");
      return false;
    }

    const phoneField = card.querySelector(".field-phone");
    if (phoneField && phoneField.value && !/^09[0-9]{8}$/.test(phoneField.value.trim())) {
      phoneField.setCustomValidity("請輸入 09 開頭的 10 碼手機號碼");
      phoneField.reportValidity();
      phoneField.setCustomValidity("");
      return false;
    }

    return true;
  }

  function bindCardEvents() {
    ui.participantsContainer.querySelectorAll(".participant-card").forEach((card) => {
      const idField = card.querySelector(".field-id-number");
      if (idField) {
        idField.addEventListener("input", () => {
          idField.value = idField.value.toUpperCase();
        });
      }

      card.querySelectorAll(".btn-next").forEach((btn) => {
        btn.addEventListener("click", () => {
          if (!validateCurrentStep(card)) {
            return;
          }
          const current = toInt(card.dataset.currentStep, 1);
          switchStep(card, current + 1);
        });
      });

      card.querySelectorAll(".btn-prev").forEach((btn) => {
        btn.addEventListener("click", () => {
          const current = toInt(card.dataset.currentStep, 1);
          switchStep(card, current - 1);
        });
      });

      card.querySelectorAll(".btn-next-person").forEach((btn) => {
        btn.addEventListener("click", () => {
          if (!validateCurrentStep(card)) {
            return;
          }
          moveToNextParticipantFromCard(card);
        });
      });
    });

    if (ui.prevParticipantBtn) {
      ui.prevParticipantBtn.onclick = () => {
        goToParticipant(state.currentCardIndex - 1);
      };
    }
    if (ui.nextParticipantBtn) {
      ui.nextParticipantBtn.onclick = () => {
        goToParticipant(state.currentCardIndex + 1);
      };
    }
  }

  function bindCopyFromPrevious() {
    const cards = Array.from(ui.participantsContainer.querySelectorAll(".participant-card"));
    cards.forEach((card, idx) => {
      if (idx === 0) {
        return;
      }

      const prevCard = cards[idx - 1];
      const prevPhone = prevCard.querySelector(".field-phone");
      const prevEmail = prevCard.querySelector(".field-email");
      const phoneField = card.querySelector(".field-phone");
      const emailField = card.querySelector(".field-email");
      const phoneToggle = card.querySelector(".copy-from-prev-phone");
      const emailToggle = card.querySelector(".copy-from-prev-email");

      if (phoneToggle && phoneField && prevPhone) {
        const syncPhone = () => {
          if (!phoneToggle.checked) {
            return;
          }
          phoneField.value = prevPhone.value;
        };

        phoneToggle.addEventListener("change", () => {
          phoneField.readOnly = phoneToggle.checked;
          syncPhone();
        });
        prevPhone.addEventListener("input", syncPhone);
      }

      if (emailToggle && emailField && prevEmail) {
        const syncEmail = () => {
          if (!emailToggle.checked) {
            return;
          }
          emailField.value = prevEmail.value;
        };

        emailToggle.addEventListener("change", () => {
          emailField.readOnly = emailToggle.checked;
          syncEmail();
        });
        prevEmail.addEventListener("input", syncEmail);
      }
    });
  }

  function applyDateFallbackHints() {
    const probe = document.createElement("input");
    probe.setAttribute("type", "date");
    const unsupportedDateInput = probe.type !== "date";

    ui.participantsContainer.querySelectorAll(".field-dob").forEach((dobField) => {
      if (unsupportedDateInput) {
        dobField.setAttribute("type", "text");
        dobField.setAttribute("placeholder", "例如：1990-05-20");
        dobField.setAttribute("pattern", "\\d{4}-\\d{2}-\\d{2}");
        dobField.setAttribute("inputmode", "numeric");
      }

      const hint = dobField.parentElement?.querySelector(".field-hint");
      if (hint) {
        hint.textContent = unsupportedDateInput
          ? "此裝置不支援日期選擇器，請輸入西元格式 YYYY-MM-DD，例如 1990-05-20。"
          : "可點選日期欄位開啟日期選擇器；若未顯示，請輸入西元格式 YYYY-MM-DD。";
      }
    });
  }

  function createParticipantCards(count) {
    state.cardCount = count;
    state.currentCardIndex = 0;
    ui.participantsContainer.innerHTML = "";
    const fragment = [];
    for (let i = 0; i < count; i += 1) {
      fragment.push(buildCard(i));
    }
    ui.participantsContainer.innerHTML = fragment.join("");

    if (count <= 1) {
      ui.participantsContainer.querySelectorAll(".btn-next-person").forEach((btn) => {
        btn.classList.add("hidden-ui");
      });
    }

    bindCardEvents();
    bindCopyFromPrevious();
    applyDateFallbackHints();
    updateParticipantVisibility();
    updateSubmitBarVisibility();
  }

  function collectParticipants() {
    const cards = ui.participantsContainer.querySelectorAll(".participant-card");
    const participants = [];

    for (const card of cards) {
      const addons = {};
      card.querySelectorAll(".addon-input").forEach((addonInput) => {
        const key = addonInput.dataset.addonKey;
        addons[key] = toInt(addonInput.value, 0);
      });

      const person = {
        name: card.querySelector(".field-name").value.trim(),
        gender: card.querySelector(".field-gender").value,
        dob: card.querySelector(".field-dob").value,
        id_number: card.querySelector(".field-id-number").value.trim().toUpperCase(),
        phone: card.querySelector(".field-phone").value.trim(),
        email: card.querySelector(".field-email").value.trim(),
        ticket_type: card.querySelector(".field-ticket").value,
        food_types: card.querySelector(".field-food").value,
        bank_name: "",
        bank_last4: "",
        note: "",
        addons,
      };

      participants.push(person);
    }

    return participants;
  }

  function validateAllCards() {
    const cards = ui.participantsContainer.querySelectorAll(".participant-card");
    for (const card of cards) {
      const fields = card.querySelectorAll("input, select");
      for (const field of fields) {
        if (!field.checkValidity()) {
          field.reportValidity();
          return false;
        }
      }

      const validators = [
        [".field-id-number", /^[A-Za-z][12][0-9]{8}$/, "請輸入正確身分證字號格式"],
        [".field-phone", /^09[0-9]{8}$/, "請輸入 09 開頭的 10 碼手機號碼"],
      ];

      for (const [selector, pattern, message] of validators) {
        const field = card.querySelector(selector);
        if (field && !pattern.test(field.value.trim())) {
          field.setCustomValidity(message);
          field.reportValidity();
          field.setCustomValidity("");
          return false;
        }
        if (field) {
          field.setCustomValidity("");
        }
      }
    }
    return true;
  }

  function getSerialValue(person) {
    const directKeys = ["報名序號", "序號", "serial_number", "serial", "registration_serial", "車次"];
    for (const key of directKeys) {
      const value = person[key];
      if (value !== undefined && value !== null && String(value).trim() !== "") {
        return String(value);
      }
    }

    for (const [key, value] of Object.entries(person)) {
      if (/序號|serial/i.test(key) && value !== undefined && value !== null && String(value).trim() !== "") {
        return String(value);
      }
    }

    return "";
  }

  function getEasycardDetail(person) {
    const easycardPrice = toInt(((state.bootstrap || {}).addons || {}).easycard?.price, 0);
    const qty = toInt(
      person["加購_easycard"]
      ?? person.easycard_qty
      ?? person.addon_easycard
      ?? 0,
      0
    );
    if (qty <= 0) {
      return "無";
    }
    return `有（${qty} 張 / NT$ ${qty * easycardPrice}）`;
  }

  function renderConfirm(result) {
    const emailStatusText = result.email_sent ? "付款資訊 Email 已寄出" : "付款資訊 Email 寄送失敗（可由後台重送）";
    ui.confirmCount.textContent = `本次報名 ${result.data.length} 位參加者，總金額 NT$ ${result.total_amount}。${emailStatusText}`;

    ui.bankInfoList.innerHTML = [
      `<li>銀行：${escapeHtml(result.bank_info["銀行"])}</li>`,
      `<li>帳號：${escapeHtml(result.bank_info["帳號"])}</li>`,
      `<li>戶名：${escapeHtml(result.bank_info["戶名"])}</li>`,
    ].join("");

    ui.summaryTableBody.innerHTML = result.data
      .map(
        (person) => {
          const serialText = getSerialValue(person);
          return `
      <tr>
        <td>${escapeHtml(person["姓名"])}</td>
        <td>${escapeHtml(person["票種"])}</td>
        <td>${escapeHtml(person["金額"])}</td>
        <td>${escapeHtml(getEasycardDetail(person))}</td>
        <td>${escapeHtml(person["電子郵件"])}</td>
        <td>${escapeHtml(serialText)}</td>
      </tr>
    `;
        }
      )
      .join("");

    ui.lineLink.href = result.line_link;

    ui.formSection.classList.add("hidden-ui");
    ui.confirmSection.classList.remove("hidden-ui");
    ui.confirmSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function submitRegistration() {
    if (!validateAllCards()) {
      ui.submitMessage.textContent = "請先完成所有欄位。";
      ui.submitMessage.className = "submit-message error";
      return;
    }

    const participants = collectParticipants();
    ui.submitBtn.disabled = true;
    ui.submitMessage.textContent = "送出中，請稍候...";
    ui.submitMessage.className = "submit-message";

    try {
      const response = await fetch("/api/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ participants }),
      });

      const result = await response.json();
      if (!response.ok || !result.ok) {
        throw new Error(result.message || "送出失敗，請稍後再試");
      }

      ui.submitMessage.textContent = "送出成功。";
      ui.submitMessage.className = "submit-message ok";
      renderConfirm(result);
    } catch (error) {
      ui.submitMessage.textContent = error.message;
      ui.submitMessage.className = "submit-message error";
    } finally {
      ui.submitBtn.disabled = false;
    }
  }

  async function onStartClick() {
    if (!state.bootstrapReady || !state.bootstrap) {
      setMessage(ui.launcherMessage, "系統資料同步中，稍候自動進入填寫頁...", "submit-message");
      if (ui.startBtn) {
        ui.startBtn.disabled = true;
      }
      try {
        await ensureBootstrapReady();
      } catch (error) {
        setMessage(ui.launcherMessage, error.message || "系統資料同步失敗，請稍後再試。", "submit-message error");
        if (ui.startBtn) {
          ui.startBtn.disabled = false;
        }
        return;
      }
      if (ui.startBtn) {
        ui.startBtn.disabled = false;
      }
    }

    const count = Math.min(10, Math.max(1, toInt(ui.countInput.value, 1)));
    if (!ui.agree.checked) {
      setMessage(ui.launcherMessage, "請先勾選同意活動規範與退費條款。", "submit-message error");
      return;
    }

    setMessage(ui.launcherMessage, "", "submit-message");
    scheduleDeferredBackgroundLoad();
    createParticipantCards(count);
    if (ui.heroSection) {
      ui.heroSection.classList.add("hidden-ui");
    }
    if (ui.formSection) {
      ui.formSection.classList.remove("hidden-ui");
    }
    if (ui.confirmSection) {
      ui.confirmSection.classList.add("hidden-ui");
    }
    if (ui.submitBar) {
      ui.submitBar.classList.add("hidden-ui");
    }
    setMessage(ui.submitMessage, "", "submit-message");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function init() {
    try {
      setupPolicyReadGate();
      initElderMode();
      startCountdown();

      const cachedBootstrap = loadBootstrapFromLocalCache();
      if (cachedBootstrap) {
        applyBootstrapPayload(cachedBootstrap);
      }

      ui.startBtn.addEventListener("click", onStartClick);
      ui.submitBtn.addEventListener("click", submitRegistration);
      refreshBootstrapInBackground();
    } catch (error) {
      ui.globalNotice.textContent = error.message || "系統載入較慢，請稍後再試。";
    }
  }

  init();
})();
