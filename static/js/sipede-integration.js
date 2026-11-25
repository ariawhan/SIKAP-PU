(() => {
  const connectButton = document.querySelector("[data-sipede-connect]");
  const modal = document.querySelector("[data-sipede-modal]");
  if (!modal) return;

  const message = modal.querySelector("[data-sipede-message]");
  const loading = modal.querySelector("[data-sipede-loading]");
  const captchaForm = modal.querySelector("[data-sipede-captcha-form]");
  const captchaImage = modal.querySelector("[data-sipede-captcha-image]");
  const success = modal.querySelector("[data-sipede-success]");
  const errorPanel = modal.querySelector("[data-sipede-error]");
  const errorMessage = modal.querySelector("[data-sipede-error-message]");
  const retryButton = modal.querySelector("[data-sipede-retry]");
  const pageStatus = document.querySelector("#sipede-status");
  const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  const targetUserId = connectButton?.dataset.targetUser || "";
  let authId = null;
  let timer = null;
  let finished = false;
  let returnFocus = null;

  const endpoint = (template) => template.replace("__AUTH_ID__", authId || "");

  function statusEndpoint(template) {
    const url = new URL(endpoint(template), window.location.origin);
    if (targetUserId) url.searchParams.set("target_user_id", targetUserId);
    return `${url.pathname}${url.search}`;
  }

  function requestBody(form = null) {
    const body = form ? new FormData(form) : new FormData();
    if (targetUserId) body.set("target_user_id", targetUserId);
    return body;
  }

  function showModal() {
    returnFocus = document.activeElement;
    modal.hidden = false;
    document.body.classList.add("modal-open");
    modal.querySelector(".sipede-auth-dialog")?.focus();
  }

  function hideModal() {
    modal.hidden = true;
    document.body.classList.remove("modal-open");
    returnFocus?.focus?.();
  }

  function render(status, result = {}) {
    modal.querySelector(".sipede-auth-body").dataset.sipedeState = status;
    message.textContent = result.message || "Memproses login SIPede…";
    loading.hidden = !["starting", "loading"].includes(status);
    captchaForm.hidden = status !== "captcha";
    success.hidden = status !== "success";
    errorPanel.hidden = status !== "error";
    if (status === "captcha" && result.captcha) {
      captchaImage.src = result.captcha.startsWith("data:")
        ? result.captcha
        : `data:image/png;base64,${result.captcha}`;
      window.setTimeout(() => captchaForm.elements.captcha.focus(), 80);
    }
    if (status === "error") errorMessage.textContent = result.message || "Koneksi SIPede gagal.";
    if (["success", "error", "cancelled"].includes(status)) {
      finished = true;
      window.clearTimeout(timer);
      if (connectButton) connectButton.disabled = false;
    }
    if (status === "success") {
      if (pageStatus) pageStatus.textContent = result.message;
      window.dispatchEvent(new CustomEvent("sipede-auth-success", { detail: result }));
      if (modal.dataset.reloadOnSuccess === "true") {
        window.setTimeout(() => window.location.reload(), 1300);
      } else {
        window.setTimeout(hideModal, 700);
      }
    }
  }

  async function readJson(response) {
    try { return await response.json(); }
    catch (_) { return { message: "Respons server tidak dapat dibaca." }; }
  }

  async function poll() {
    if (!authId || finished) return;
    try {
      const response = await fetch(statusEndpoint(modal.dataset.statusUrl), { cache: "no-store" });
      const result = await readJson(response);
      if (!response.ok) throw new Error(result.message || "Sesi login SIPede tidak ditemukan.");
      render(result.status, result);
      if (!finished) timer = window.setTimeout(poll, 900);
    } catch (error) {
      render("error", { message: error.message });
    }
  }

  async function start() {
    showModal();
    finished = false;
    authId = null;
    captchaForm.reset();
    captchaImage.removeAttribute("src");
    if (connectButton) connectButton.disabled = true;
    render("starting", { message: "Menyiapkan Google Chrome di komputer server…" });
    try {
      const response = await fetch(modal.dataset.startUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrf },
        body: requestBody(),
      });
      const result = await readJson(response);
      if (!response.ok) throw new Error(result.message || "Tidak dapat memulai login SIPede.");
      authId = result.auth_id;
      poll();
    } catch (error) {
      render("error", { message: error.message });
    }
  }

  async function close() {
    window.clearTimeout(timer);
    if (authId && !finished) {
      try {
        await fetch(endpoint(modal.dataset.cancelUrl), {
          method: "POST",
          headers: { "X-CSRFToken": csrf },
          body: requestBody(),
        });
      } catch (_) {}
    }
    finished = true;
    authId = null;
    if (connectButton) connectButton.disabled = false;
    hideModal();
    window.dispatchEvent(new CustomEvent("sipede-auth-cancelled"));
  }

  connectButton?.addEventListener("click", start);
  retryButton.addEventListener("click", start);
  window.addEventListener("sipede-auth-start", start);
  modal.querySelectorAll("[data-sipede-close]").forEach((button) => button.addEventListener("click", close));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) close();
  });
  captchaForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = captchaForm.elements.captcha;
    const submit = captchaForm.querySelector("button[type=submit]");
    submit.disabled = true;
    try {
      const response = await fetch(endpoint(modal.dataset.captchaUrl), {
        method: "POST",
        headers: { "X-CSRFToken": csrf },
        body: requestBody(captchaForm),
      });
      const result = await readJson(response);
      if (!response.ok) throw new Error(result.message || "CAPTCHA tidak dapat dikirim.");
      input.value = "";
      render("loading", result);
    } catch (error) {
      render("error", { message: error.message });
    } finally {
      submit.disabled = false;
    }
  });
})();
