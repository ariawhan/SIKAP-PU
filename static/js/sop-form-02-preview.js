(function () {
  const form = document.querySelector('[data-sop-form]');
  const frame = form?.querySelector('[data-sop-paper-frame]');
  const paper = frame?.querySelector('[data-sop-paper]');
  if (!form || !frame || !paper) return;

  let frameWidth = 0;
  const resizePreview = () => {
    const naturalWidth = paper.offsetWidth;
    const naturalHeight = paper.offsetHeight;
    const availableWidth = frame.clientWidth;
    if (!naturalWidth || !naturalHeight || !availableWidth) return;

    const scale = Math.min(1, availableWidth / naturalWidth);
    paper.style.transform = scale < 1 ? `scale(${scale})` : 'none';
    frame.style.height = `${Math.ceil(naturalHeight * scale)}px`;
    frameWidth = availableWidth;
  };

  const observer = new ResizeObserver(() => {
    if (frame.clientWidth !== frameWidth) resizePreview();
  });
  observer.observe(frame);
  new MutationObserver(resizePreview).observe(paper, { childList: true, subtree: true });
  resizePreview();
})();
