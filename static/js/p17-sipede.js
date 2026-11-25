(() => {
  const form = document.querySelector('[data-p17-form]');
  if (!form) return;
  const button = form.querySelector('[data-p17-sipede]');
  const modal = form.querySelector('[data-p17-sipede-modal]');
  const message = form.querySelector('[data-p17-sipede-message]');
  const progress = form.querySelector('[data-p17-sipede-progress]');
  const confirm = form.querySelector('[data-p17-sipede-confirm]');
  const fields = Array.from(form.querySelectorAll('[data-p17-sipede-field]'));
  const dispositionModal = form.querySelector('[data-p17-disposition-modal]');
  const dispositionOptions = form.querySelector('[data-p17-disposition-options]');
  const dispositionAll = form.querySelector('[data-p17-disposition-all]');
  const dispositionConfirm = form.querySelector('[data-p17-disposition-confirm]');
  const pdfButton = form.querySelector('[data-p17-pdf-download]');
  const pages = form.querySelector('[data-p17-pages]');
  const dateInput = form.querySelector('[name="letter_date"]');
  const numberInput = form.querySelector('[name="letter_number"]');
  let number = '';

  const readJson = async (response) => { const text = await response.text(); try { return text ? JSON.parse(text) : {}; } catch (_) { return {message: text.replace(/<[^>]+>/g, ' ').trim()}; } };
  const requestLogin = () => new Promise((resolve, reject) => {
    const done = () => { window.removeEventListener('sipede-auth-success', success); window.removeEventListener('sipede-auth-cancelled', cancel); };
    const success = () => { done(); resolve(); }; const cancel = () => { done(); reject(new Error('Login SIPede dibatalkan.')); };
    window.addEventListener('sipede-auth-success', success); window.addEventListener('sipede-auth-cancelled', cancel);
    window.dispatchEvent(new CustomEvent('sipede-auth-start'));
  });
  async function post(data, allowLogin = true) {
    const response = await fetch(button?.dataset.url || pdfButton.dataset.url, {method:'POST', headers:{Accept:'application/json','X-CSRFToken':form.querySelector('[name="csrfmiddlewaretoken"]').value}, body:data});
    const result = await readJson(response);
    if (result.requires_sipede_login && allowLogin) { await requestLogin(); return post(data, false); }
    if (!response.ok) throw new Error(result.message || `Proses SIPede gagal (HTTP ${response.status}).`);
    return result;
  }
  const busy = (active, text) => { if (progress) progress.hidden = !active; if (confirm) confirm.disabled = active; if (message && text) message.textContent = text; };
  const imageData = async (image) => { if (!image.src || image.src.startsWith('data:image/')) return image.src; const response = await fetch(image.src); const blob = await response.blob(); return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob);}); };
  async function documentHtml(expected) {
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const rendered = Array.from(pages.querySelectorAll('[data-p17-output="number"]')).map(node => node.textContent.trim());
    if (expected && (!rendered.length || rendered.some(value => value !== expected))) throw new Error('Nomor SIPede belum masuk ke seluruh halaman P-17.');
    const clone = pages.cloneNode(true); const images = Array.from(clone.querySelectorAll('img'));
    const sources = await Promise.all(images.map(imageData)); images.forEach((image,index)=>{image.src=sources[index];});
    clone.querySelectorAll('.p17-paper').forEach(paper => { paper.style.transform='none'; });
    return clone.innerHTML;
  }
  pdfButton?.addEventListener('click', async () => {
    const original=pdfButton.textContent; pdfButton.disabled=true; pdfButton.textContent='Membuat PDF…';
    try { const data=new FormData(); data.append('action','pdf'); data.append('document_html',await documentHtml('')); const response=await fetch(pdfButton.dataset.url,{method:'POST',headers:{Accept:'application/pdf','X-CSRFToken':form.querySelector('[name="csrfmiddlewaretoken"]').value},body:data}); if(!response.ok) throw new Error((await readJson(response)).message||'PDF gagal dibuat.'); const url=URL.createObjectURL(await response.blob()); const link=document.createElement('a'); link.href=url; link.download='P-17.pdf'; link.click(); URL.revokeObjectURL(url); } catch(error){alert(error.message);} finally {pdfButton.disabled=false;pdfButton.textContent=original;}
  });
  button?.addEventListener('click', async () => { const original=button.textContent; button.disabled=true; button.textContent='Memeriksa sesi…'; try {const data=new FormData();data.append('action','session');await post(data);modal.hidden=false;document.body.classList.add('p16-sipede-open');}catch(error){alert(error.message);}finally{if(button.textContent!=='Sudah di SIPede'){button.disabled=false;button.textContent=original;}} });
  modal?.querySelectorAll('[data-p17-sipede-close]').forEach(node=>node.addEventListener('click',()=>{if(progress.hidden){modal.hidden=true;document.body.classList.remove('p16-sipede-open');}}));
  dispositionModal?.querySelectorAll('[data-p17-disposition-close]').forEach(node=>node.addEventListener('click',()=>{dispositionModal.hidden=true;document.body.classList.remove('p16-sipede-open');}));
  dispositionAll?.addEventListener('change',()=>form.querySelectorAll('[data-p17-disposition-choice]').forEach(node=>{node.checked=dispositionAll.checked;}));
  confirm?.addEventListener('click', async () => {
    const invalid=fields.find(field=>!field.checkValidity()); if(invalid){invalid.reportValidity();return;}
    busy(true,'Mencocokkan data dan mengambil nomor P-17…');
    try {const data=new FormData();data.append('action','number');data.append('letter_date',dateInput?.value||'');['acting_type','acting_name','acting_position','acting_nip'].forEach(name=>data.append(name,form.querySelector(`[name="${name}"]`)?.value||''));fields.forEach(field=>data.append(field.dataset.p17SipedeField,field.value.trim()));const result=await post(data);number=String(result.number||'').trim();if(!number)throw new Error('SIPede tidak mengembalikan nomor.');if(numberInput)numberInput.value=number.match(/^B-(\d+)\//i)?.[1]||number;numberInput?.dispatchEvent(new Event('input',{bubbles:true}));const next=new FormData();next.append('action','dispositions');const choices=await post(next);dispositionOptions.replaceChildren(...choices.options.map(option=>{const label=document.createElement('label');label.innerHTML=`<input type="checkbox" data-p17-disposition-choice value="${option.value}"> ${option.label}`;return label;}));modal.hidden=true;dispositionModal.hidden=false;busy(false,`Nomor ${number} sudah diperoleh.`);}catch(error){busy(false,error.message);alert(error.message);}
  });
  dispositionConfirm?.addEventListener('click', async () => {
    const selected=Array.from(form.querySelectorAll('[data-p17-disposition-choice]:checked')).map(node=>node.value);if(!selected.length){alert('Pilih minimal satu tujuan penerusan.');return;}
    dispositionModal.hidden=true;modal.hidden=false;modal.classList.add('is-finalizing');busy(true,'Membuat PDF P-17 dan mengunggah ke SIPede…');
    try {const data=new FormData();data.append('action','upload');data.append('document_html',await documentHtml(number));selected.forEach(value=>data.append('disposition_ids',value));const result=await post(data);button.disabled=true;button.textContent='Sudah di SIPede';modal.hidden=true;document.body.classList.remove('p16-sipede-open');}catch(error){modal.classList.remove('is-finalizing');busy(false,error.message);alert(error.message);}
  });
})();
