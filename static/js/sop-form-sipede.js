(() => {
  const form = document.querySelector('[data-sop-form], [data-case-document-form], [data-p21-form]');
  const button = form?.querySelector('[data-sop-sipede]');
  if (!form || !button) return;
  const modal = form.querySelector('[data-sop-sipede-modal]');
  const displayNumber = String(Number(form.dataset.sopKind || ''));
  const modalTitle = modal?.querySelector('header h2');
  if (modalTitle && displayNumber !== 'NaN') {
    modalTitle.textContent = `Upload SOP Form ${displayNumber} ke SIPede`;
  }
  const dispositionModal = form.querySelector('[data-sop-disposition-modal]');
  const progress = form.querySelector('[data-sop-sipede-progress]');
  const message = form.querySelector('[data-sop-sipede-message]');
  const confirm = form.querySelector('[data-sop-sipede-confirm]');
  const optionsNode = form.querySelector('[data-sop-disposition-options]');
  const paper = form.querySelector('[data-sop-paper], [data-p21-paper], [data-document-pages]');
  const fields = Array.from(form.querySelectorAll('[data-sop-sipede-field]'));
  let officialNumber = '';
  const csrf = form.querySelector('[name="csrfmiddlewaretoken"]').value;
  const imageData=async image=>{if(!image.src||image.src.startsWith('data:image/'))return image.src;const response=await fetch(image.src);const blob=await response.blob();return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob)})};
  const parse = async response => { const text = await response.text(); try { return JSON.parse(text); } catch (_) { return {message:text}; } };
  const login = () => new Promise((resolve, reject) => {
    const success = () => { cleanup(); resolve(); }; const cancel = () => { cleanup(); reject(new Error('Login SIPede dibatalkan.')); };
    const cleanup = () => { removeEventListener('sipede-auth-success', success); removeEventListener('sipede-auth-cancelled', cancel); };
    addEventListener('sipede-auth-success', success); addEventListener('sipede-auth-cancelled', cancel); dispatchEvent(new CustomEvent('sipede-auth-start'));
  });
  async function post(data, retry=true) { const response=await fetch(button.dataset.url,{method:'POST',headers:{Accept:'application/json','X-CSRFToken':csrf},body:data}); const result=await parse(response); if(result.requires_sipede_login&&retry){await login();return post(data,false);} if(!response.ok)throw new Error(result.message||'Proses SIPede gagal.'); return result; }
  const busy=(on,text)=>{progress.hidden=!on;confirm.disabled=on;if(text)message.textContent=text;};
  button.addEventListener('click',async()=>{button.disabled=true;try{const data=new FormData();data.append('action','session');await post(data);modal.hidden=false;document.body.classList.add('p16-sipede-open');}catch(error){alert(error.message);}finally{if(button.textContent!=='Sudah di SIPede')button.disabled=false;}});
  form.querySelectorAll('[data-sop-sipede-close]').forEach(node=>node.addEventListener('click',()=>{if(progress.hidden){modal.hidden=true;document.body.classList.remove('p16-sipede-open');}}));
  form.querySelectorAll('[data-sop-disposition-close]').forEach(node=>node.addEventListener('click',()=>{dispositionModal.hidden=true;document.body.classList.remove('p16-sipede-open');}));
  form.querySelector('[data-sop-disposition-all]')?.addEventListener('change',event=>form.querySelectorAll('[data-sop-disposition-choice]').forEach(node=>node.checked=event.target.checked));
  confirm.addEventListener('click',async()=>{const invalid=fields.find(field=>!field.checkValidity());if(invalid){invalid.reportValidity();return;}busy(true,'Mengambil nomor surat dari SIPede…');try{const data=new FormData();data.append('action','number');data.append('letter_date',form.querySelector('[name="letter_date"]').value);['acting_type','acting_name','acting_position','acting_nip'].forEach(name=>data.append(name,form.querySelector(`[name="${name}"]`)?.value||''));fields.forEach(field=>data.append(field.dataset.sopSipedeField,field.value.trim()));const result=await post(data);officialNumber=result.number;const numberInput=form.querySelector('[name="letter_number"]');numberInput.value=officialNumber.match(/^B-(\d+)\//i)?.[1]||officialNumber;numberInput.dispatchEvent(new Event('input',{bubbles:true}));await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));const next=new FormData();next.append('action','dispositions');const choices=await post(next);optionsNode.replaceChildren(...choices.options.map(option=>{const label=document.createElement('label');label.innerHTML=`<input type="checkbox" data-sop-disposition-choice value="${option.value}"> ${option.label}`;return label;}));modal.hidden=true;dispositionModal.hidden=false;}catch(error){busy(false,error.message);alert(error.message);}});
  form.querySelector('[data-sop-disposition-confirm]')?.addEventListener('click',async()=>{const selected=Array.from(form.querySelectorAll('[data-sop-disposition-choice]:checked')).map(node=>node.value);if(!selected.length){alert('Pilih minimal satu tujuan penerusan.');return;}dispositionModal.hidden=true;modal.hidden=false;busy(true,'Membuat PDF dan mengunggah ke SIPede…');try{const clone=paper.cloneNode(true);clone.querySelectorAll('[data-sop-output="number"],[data-p21-output="number"],[data-document-output="number"]').forEach(node=>node.textContent=officialNumber);const images=Array.from(clone.querySelectorAll('img'));const sources=await Promise.all(images.map(imageData));images.forEach((image,index)=>image.src=sources[index]);const data=new FormData();data.append('action','upload');data.append('document_html',clone.outerHTML);selected.forEach(value=>data.append('disposition_ids',value));await post(data);button.disabled=true;button.textContent='Sudah di SIPede';modal.hidden=true;document.body.classList.remove('p16-sipede-open');}catch(error){busy(false,error.message);alert(error.message);}});
})();
