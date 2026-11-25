(() => {
  const button = document.querySelector('[data-cms-connect]');
  if (!button) return;
  const status = document.querySelector('[data-cms-status]');
  const csrf = document.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';

  button.addEventListener('click', async () => {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Menghubungkan CMS…';
    if (status) status.textContent = 'Mengambil halaman login dan memverifikasi sesi…';
    const body = new FormData();
    if (button.dataset.targetUser) body.set('target_user_id', button.dataset.targetUser);
    try {
      const response = await fetch(button.dataset.connectUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf },
        body,
      });
      const result = await response.json().catch(() => ({ message: 'Respons server CMS tidak dapat dibaca.' }));
      if (!response.ok) throw new Error(result.message || 'Koneksi CMS gagal.');
      if (status) status.textContent = result.message;
      button.textContent = 'CMS Terhubung';
      window.setTimeout(() => window.location.reload(), 900);
    } catch (error) {
      if (status) status.textContent = error.message;
      button.textContent = 'Coba Lagi';
      button.disabled = false;
      window.setTimeout(() => {
        if (button.textContent === 'Coba Lagi') button.textContent = original;
      }, 5000);
    }
  });
})();
