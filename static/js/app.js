(() => {
  const state = {
    bootstrap: null,
    registrationEndDate: "2026-06-06",
    countdownTimer: null,
  };

  const ui = {
    countdown: document.getElementById("countdown"),
    globalNotice: document.getElementById("globalNotice"),
    launcher: document.getElementById("launcher"),
    countInput: document.getElementById("countInput"),
    agree: document.getElementById("agree"),
    startBtn: document.getElementById("startBtn"),
    formSection: document.getElementById("formSection"),
    participantsContainer: document.getElementById("participantsContainer"),
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

  async function loadBootstrap() {
    const response = await fetch("/api/bootstrap", { method: "GET" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.message || "無法讀取活動資訊，請稍後再試。");
    }
    state.bootstrap = payload;
    state.registrationEndDate = state.bootstrap.registration_end_date || "2026-06-06";

    const notices = [state.bootstrap.notice || "", state.bootstrap.warning || ""]
      .filter(Boolean)
      .join(" ");
    ui.globalNotice.textContent = notices;

    if (state.bootstrap.sold_out) {
      ui.countdown.textContent = "目前已額滿";
      ui.launcher.classList.add("hidden-ui");
      return;
    }

    startCountdown();
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
      ui.countdown.textContent = `報名開放中，距離 ${state.registrationEndDate} 截止還有 ${days} 天 ${hours} 小時 ${mins} 分 ${secs} 秒`;
      ui.launcher.classList.remove("hidden-ui");
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
            <input type="date" class="form-control mb-2 field-dob" required>
            <input type="text" class="form-control mb-2 field-id-number" placeholder="身分證" minlength="10" maxlength="10" pattern="[A-Za-z][12][0-9]{8}" title="請輸入正確身分證字號格式，例如 A123456789" required>
            <input type="tel" class="form-control mb-2 field-phone" placeholder="電話" inputmode="numeric" pattern="09[0-9]{8}" title="請輸入 09 開頭的 10 碼手機號碼" required>
            <input type="email" class="form-control field-email" placeholder="Email" maxlength="80" required>
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
            <div class="alert alert-success">
              ${escapeHtml(state.bootstrap.bank_info["銀行"])}<br>
              戶名：${escapeHtml(state.bootstrap.bank_info["戶名"])}<br>
              帳號：${escapeHtml(state.bootstrap.bank_info["帳號"])}
            </div>

            <input type="text" class="form-control mb-2 field-bank" placeholder="匯款銀行" minlength="2" maxlength="40" required>
            <input type="text" class="form-control mb-2 field-bank-last4" placeholder="末四碼" inputmode="numeric" pattern="[0-9]{4}" title="請輸入 4 碼數字" required>
            <input type="text" class="form-control field-note" placeholder="備註（選填）" maxlength="100">

            <div class="step-actions">
              <button type="button" class="btn btn-secondary btn-prev">上一步</button>
            </div>
          </div>
        </div>
      </article>
    `;
  }

  function switchStep(card, nextStep) {
    const targetStep = Math.max(1, Math.min(3, nextStep));
    card.dataset.currentStep = String(targetStep);

    const pill = card.querySelector(".step-pill");
    if (pill) {
      pill.textContent = `步驟 ${targetStep} / 3`;
    }

    card.querySelectorAll(".step-panel").forEach((panel) => {
      const isActive = toInt(panel.dataset.step, 1) === targetStep;
      panel.classList.toggle("active", isActive);
    });
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

    const bankLast4Field = card.querySelector(".field-bank-last4");
    if (bankLast4Field && bankLast4Field.value && !/^[0-9]{4}$/.test(bankLast4Field.value.trim())) {
      bankLast4Field.setCustomValidity("請輸入 4 碼數字");
      bankLast4Field.reportValidity();
      bankLast4Field.setCustomValidity("");
      return false;
    }

    return true;
  }

  function bindCardEvents() {
    ui.participantsContainer.querySelectorAll(".participant-card").forEach((card) => {
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
    });
  }

  function createParticipantCards(count) {
    ui.participantsContainer.innerHTML = "";
    const fragment = [];
    for (let i = 0; i < count; i += 1) {
      fragment.push(buildCard(i));
    }
    ui.participantsContainer.innerHTML = fragment.join("");
    bindCardEvents();
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
        id_number: card.querySelector(".field-id-number").value.trim(),
        phone: card.querySelector(".field-phone").value.trim(),
        email: card.querySelector(".field-email").value.trim(),
        ticket_type: card.querySelector(".field-ticket").value,
        food_types: card.querySelector(".field-food").value,
        bank_name: card.querySelector(".field-bank").value.trim(),
        bank_last4: card.querySelector(".field-bank-last4").value.trim(),
        note: card.querySelector(".field-note").value.trim(),
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
        [".field-bank-last4", /^[0-9]{4}$/, "請輸入 4 碼數字"],
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

  function renderConfirm(result) {
    ui.confirmCount.textContent = `本次報名 ${result.data.length} 位參加者，總金額 NT$ ${result.total_amount}`;

    ui.bankInfoList.innerHTML = [
      `<li>銀行：${escapeHtml(result.bank_info["銀行"])}</li>`,
      `<li>帳號：${escapeHtml(result.bank_info["帳號"])}</li>`,
      `<li>戶名：${escapeHtml(result.bank_info["戶名"])}</li>`,
    ].join("");

    ui.summaryTableBody.innerHTML = result.data
      .map(
        (person) => `
      <tr>
        <td>${escapeHtml(person["姓名"])}</td>
        <td>${escapeHtml(person["票種"])}</td>
        <td>${escapeHtml(person["金額"])}</td>
        <td>${escapeHtml(person["匯款末四碼"])}</td>
        <td>${escapeHtml(person["序號"] || "")}</td>
      </tr>
    `
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

  function onStartClick() {
    const count = Math.min(10, Math.max(1, toInt(ui.countInput.value, 1)));
    if (!ui.agree.checked) {
      ui.submitMessage.textContent = "請先勾選同意活動規範與退費條款。";
      ui.submitMessage.className = "submit-message error";
      return;
    }

    createParticipantCards(count);
    ui.formSection.classList.remove("hidden-ui");
    ui.confirmSection.classList.add("hidden-ui");
    ui.submitMessage.textContent = "";
    ui.formSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function init() {
    try {
      await loadBootstrap();
      ui.startBtn.addEventListener("click", onStartClick);
      ui.submitBtn.addEventListener("click", submitRegistration);
    } catch (error) {
      ui.countdown.textContent = error.message;
    }
  }

  init();
})();
