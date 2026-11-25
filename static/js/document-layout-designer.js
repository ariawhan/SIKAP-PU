(function () {
  const designer = document.querySelector('[data-layout-designer]');
  const paper = designer?.querySelector('[data-layout-paper]');
  const frame = designer?.querySelector('[data-layout-paper-frame]');
  if (!designer || !paper || !frame) return;

  const initialNode = document.getElementById('layout-initial-data');
  const defaultNode = document.getElementById('layout-default-data');
  const initial = JSON.parse(initialNode?.textContent || '{}');
  const defaults = JSON.parse(defaultNode?.textContent || '{}');
  const controls = Array.from(designer.querySelectorAll('[data-layout-control]'));
  const dirtyBadge = designer.querySelector('[data-layout-dirty]');
  const canvas = designer.querySelector('[data-layout-canvas]');
  const status = designer.querySelector('[data-layout-status]');
  const undoButton = designer.querySelector('[data-layout-undo]');
  const redoButton = designer.querySelector('[data-layout-redo]');
  const zoomOutput = designer.querySelector('[data-layout-zoom]');
  const fontStacks = {
    arial: 'Arial, sans-serif',
    times: '"Times New Roman", Times, serif',
    calibri: 'Calibri, "Segoe UI", sans-serif'
  };
  const state = { ...initial };
  const undoStack = [];
  const redoStack = [];
  let savedSnapshot = '';
  let zoom = 1;
  let gestureStart = '';

  const variableMap = {
    margin_top_cm: ['--p16-margin-top', 'cm'], margin_right_cm: ['--p16-margin-right', 'cm'],
    margin_bottom_cm: ['--p16-margin-bottom', 'cm'], margin_left_cm: ['--p16-margin-left', 'cm'],
    font_size_pt: ['--p16-font-size', 'pt'], line_height: ['--p16-line-height', ''],
    letterhead_height_cm: ['--p16-letterhead-height', 'cm'], letterhead_gap_pt: ['--p16-letterhead-gap', 'pt'],
    logo_width_cm: ['--p16-logo-width', 'cm'], logo_height_cm: ['--p16-logo-height', 'cm'],
    logo_offset_x_cm: ['--p16-logo-offset-x', 'cm'], logo_offset_y_cm: ['--p16-logo-offset-y', 'cm'],
    header_offset_x_cm: ['--p16-header-offset-x', 'cm'], header_offset_y_cm: ['--p16-header-offset-y', 'cm'],
    header_font_size_pt: ['--p16-header-font-size', 'pt'], address_font_size_pt: ['--p16-address-font-size', 'pt'],
    clause_label_width_pt: ['--p16-clause-label-width', 'pt'], clause_colon_width_pt: ['--p16-clause-colon-width', 'pt'],
    body_indent_pt: ['--p16-body-indent', 'pt'], continuation_indent_pt: ['--p16-continuation-indent', 'pt'],
    suspect_indent_pt: ['--p16-suspect-indent', 'pt'], copies_top_pt: ['--p16-copies-top', 'pt'],
    signature_width_pct: ['--p16-signature-width', '%'], signature_top_pt: ['--p16-signature-top', 'pt'],
    signature_right_pt: ['--p16-signature-right', 'pt'], tte_height_pt: ['--p16-tte-height', 'pt'],
    barcode_width_pt: ['--p16-barcode-width', 'pt'], barcode_height_pt: ['--p16-barcode-height', 'pt'],
    barcode_offset_x_cm: ['--p16-barcode-offset-x', 'cm'], barcode_bottom_lift_mm: ['--p16-barcode-bottom-lift', 'mm']
  };

  function numericControl(key) {
    return controls.find((control) => control.dataset.layoutControl === key && control.type === 'number');
  }

  function clamp(key, value) {
    const input = numericControl(key);
    if (!input) return value;
    const minimum = Number(input.min);
    const maximum = Number(input.max);
    return Math.min(maximum, Math.max(minimum, value));
  }

  function precision(key) {
    const step = numericControl(key)?.step || '1';
    return step.includes('.') ? step.split('.')[1].length : 0;
  }

  function normalizedSnapshot(value = state) {
    const ordered = {};
    Object.keys(defaults).sort().forEach((key) => { ordered[key] = value[key]; });
    return JSON.stringify(ordered);
  }
  savedSnapshot = normalizedSnapshot(initial);

  function syncControl(key) {
    controls.filter((control) => control.dataset.layoutControl === key).forEach((control) => {
      if (control.value !== String(state[key])) control.value = state[key];
    });
    const output = designer.querySelector(`[data-layout-output="${key}"]`);
    const number = numericControl(key);
    if (output && number) output.textContent = `${state[key]} ${number.parentElement.querySelector('span')?.textContent || ''}`;
  }

  function applyState() {
    designer.style.setProperty('--p16-font-family', fontStacks[state.font_family] || fontStacks.arial);
    Object.entries(variableMap).forEach(([key, [name, unit]]) => designer.style.setProperty(name, `${state[key]}${unit}`));
    controls.forEach((control) => syncControl(control.dataset.layoutControl));
    const dirty = normalizedSnapshot() !== savedSnapshot;
    if (dirtyBadge) dirtyBadge.hidden = !dirty;
    if (status) status.textContent = dirty ? 'Ada perubahan yang belum disimpan' : 'Sesuai konfigurasi tersimpan';
    updateHistoryButtons();
  }

  function setValue(key, value) {
    if (key === 'font_family') state[key] = fontStacks[value] ? value : 'arial';
    else state[key] = Number(clamp(key, Number(value)).toFixed(precision(key)));
    syncControl(key);
    applyState();
  }

  function commitHistory(snapshot) {
    if (!snapshot || snapshot === normalizedSnapshot()) return;
    if (undoStack[undoStack.length - 1] !== snapshot) undoStack.push(snapshot);
    if (undoStack.length > 60) undoStack.shift();
    redoStack.length = 0;
    updateHistoryButtons();
  }

  function restore(snapshot) {
    const parsed = JSON.parse(snapshot);
    Object.keys(state).forEach((key) => { if (key in parsed) state[key] = parsed[key]; });
    applyState();
  }

  function updateHistoryButtons() {
    if (undoButton) undoButton.disabled = !undoStack.length;
    if (redoButton) redoButton.disabled = !redoStack.length;
  }

  controls.forEach((control) => {
    control.addEventListener('focus', () => { gestureStart = normalizedSnapshot(); });
    control.addEventListener('input', () => {
      if (!gestureStart) gestureStart = normalizedSnapshot();
      setValue(control.dataset.layoutControl, control.value);
    });
    control.addEventListener('change', () => {
      setValue(control.dataset.layoutControl, control.value);
      commitHistory(gestureStart || savedSnapshot);
      gestureStart = '';
    });
  });

  designer.querySelector('[data-layout-reset]')?.addEventListener('click', () => {
    const before = normalizedSnapshot();
    Object.assign(state, defaults);
    applyState();
    commitHistory(before);
  });
  undoButton?.addEventListener('click', () => {
    if (!undoStack.length) return;
    redoStack.push(normalizedSnapshot());
    restore(undoStack.pop());
  });
  redoButton?.addEventListener('click', () => {
    if (!redoStack.length) return;
    undoStack.push(normalizedSnapshot());
    restore(redoStack.pop());
  });
  designer.querySelector('[data-layout-grid]')?.addEventListener('click', (event) => {
    const active = paper.classList.toggle('show-grid');
    event.currentTarget.classList.toggle('active', active);
    event.currentTarget.setAttribute('aria-pressed', String(active));
  });

  function applyScale() {
    paper.style.transform = 'none';
    const available = Math.max(280, (canvas?.clientWidth || frame.parentElement.clientWidth) - 40);
    const baseScale = Math.min(1, available / paper.offsetWidth);
    const scale = baseScale * zoom;
    paper.style.transform = `scale(${scale})`;
    frame.style.width = `${Math.round(paper.offsetWidth * scale)}px`;
    frame.style.height = `${Math.round(paper.offsetHeight * scale)}px`;
    if (zoomOutput) zoomOutput.textContent = `${Math.round(zoom * 100)}%`;
  }
  designer.querySelector('[data-layout-zoom-in]')?.addEventListener('click', () => { zoom = Math.min(1.4, zoom + .1); applyScale(); });
  designer.querySelector('[data-layout-zoom-out]')?.addEventListener('click', () => { zoom = Math.max(.6, zoom - .1); applyScale(); });
  window.addEventListener('resize', applyScale);

  function selectElement(target) {
    designer.querySelectorAll('[data-layout-target].selected').forEach((element) => element.classList.remove('selected'));
    target?.classList.add('selected');
    const groupName = { logo: 'letterhead', header: 'letterhead', signature: 'signature', barcode: 'barcode' }[target?.dataset.layoutTarget];
    const group = groupName && designer.querySelector(`[data-layout-group="${groupName}"]`);
    if (group) group.open = true;
  }
  designer.querySelectorAll('[data-layout-target]').forEach((target) => target.addEventListener('click', () => selectElement(target)));

  function metrics() {
    const rect = paper.getBoundingClientRect();
    return { cm: rect.width / (8.5 * 2.54), mm: rect.width / (8.5 * 25.4), pt: rect.width / (8.5 * 72), width: rect.width, height: rect.height };
  }

  function moveTarget(target, dx, dy) {
    const unit = metrics();
    const type = target.dataset.layoutTarget;
    if (type === 'logo') {
      setValue('logo_offset_x_cm', state.logo_offset_x_cm + dx / unit.cm);
      setValue('logo_offset_y_cm', state.logo_offset_y_cm + dy / unit.cm);
    } else if (type === 'header') {
      setValue('header_offset_x_cm', state.header_offset_x_cm + dx / unit.cm);
      setValue('header_offset_y_cm', state.header_offset_y_cm + dy / unit.cm);
    } else if (type === 'signature') {
      setValue('signature_right_pt', state.signature_right_pt - dx / unit.pt);
      setValue('signature_top_pt', state.signature_top_pt + dy / unit.pt);
    } else if (type === 'barcode') {
      setValue('barcode_offset_x_cm', state.barcode_offset_x_cm + dx / unit.cm);
      setValue('barcode_bottom_lift_mm', state.barcode_bottom_lift_mm - dy / unit.mm);
    }
  }

  if (typeof window.interact === 'function') {
    window.interact('[data-layout-target]').draggable({
      inertia: false,
      listeners: {
        start(event) { gestureStart = normalizedSnapshot(); selectElement(event.target); },
        move(event) { moveTarget(event.target, event.dx, event.dy); },
        end() { commitHistory(gestureStart); gestureStart = ''; }
      }
    });
    window.interact('[data-margin-handle]').draggable({
      listeners: {
        start() { gestureStart = normalizedSnapshot(); },
        move(event) {
          const unit = metrics();
          const side = event.target.dataset.marginHandle;
          if (side === 'top') setValue('margin_top_cm', state.margin_top_cm + event.dy / unit.cm);
          if (side === 'right') setValue('margin_right_cm', state.margin_right_cm - event.dx / unit.cm);
          if (side === 'bottom') setValue('margin_bottom_cm', state.margin_bottom_cm - event.dy / unit.cm);
          if (side === 'left') setValue('margin_left_cm', state.margin_left_cm + event.dx / unit.cm);
        },
        end() { commitHistory(gestureStart); gestureStart = ''; }
      }
    });
    window.interact('[data-layout-resizable]').resizable({
      edges: { right: true, bottom: true, left: true, top: true },
      inertia: false,
      listeners: {
        start(event) { gestureStart = normalizedSnapshot(); selectElement(event.target); },
        move(event) {
          const unit = metrics();
          const type = event.target.dataset.layoutResizable;
          if (type === 'logo') {
            setValue('logo_width_cm', event.rect.width / unit.cm);
            setValue('logo_height_cm', event.rect.height / unit.cm);
          } else if (type === 'signature') {
            setValue('signature_width_pct', event.rect.width / unit.width * 100);
            setValue('tte_height_pt', Math.max(20, (event.rect.height - 75 * unit.pt) / unit.pt));
          } else if (type === 'barcode') {
            setValue('barcode_width_pt', event.rect.width / unit.pt);
            setValue('barcode_height_pt', event.rect.height / unit.pt);
          }
        },
        end() { commitHistory(gestureStart); gestureStart = ''; }
      }
    });
  }

  designer.addEventListener('submit', () => {
    controls.filter((control) => control.type === 'number' || control.tagName === 'SELECT').forEach((control) => {
      control.value = state[control.dataset.layoutControl];
    });
    savedSnapshot = normalizedSnapshot();
  });
  window.addEventListener('beforeunload', (event) => {
    if (normalizedSnapshot() === savedSnapshot) return;
    event.preventDefault();
    event.returnValue = '';
  });

  applyState();
  requestAnimationFrame(applyScale);
  if (document.fonts?.ready) document.fonts.ready.then(applyScale);
})();
