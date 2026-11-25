(() => {
  const menus = () => document.querySelectorAll('.action-menu');

  function closeMenus(except = null) {
    menus().forEach(menu => {
      if (menu !== except) menu.removeAttribute('open');
    });
  }

  function clearPosition(menu) {
    menu.querySelector('.action-menu-list')?.removeAttribute('style');
  }

  function positionMenu(menu) {
    const list = menu.querySelector('.action-menu-list');
    const trigger = menu.querySelector('summary')?.getBoundingClientRect();
    if (!list || !trigger) return;

    const viewportGap = 10;
    const menuGap = 7;
    const width = Math.min(250, window.innerWidth - (viewportGap * 2));
    list.style.setProperty('--menu-width', `${width}px`);
    list.style.position = 'fixed';
    list.style.zIndex = '10000';
    list.style.right = 'auto';
    list.style.left = `${Math.max(
      viewportGap,
      Math.min(window.innerWidth - width - viewportGap, trigger.right - width),
    )}px`;

    const height = list.getBoundingClientRect().height;
    const spaceBelow = window.innerHeight - trigger.bottom - viewportGap;
    const spaceAbove = trigger.top - viewportGap;
    const openAbove = height > spaceBelow && spaceAbove > spaceBelow;
    const top = openAbove
      ? Math.max(viewportGap, trigger.top - height - menuGap)
      : Math.min(window.innerHeight - height - viewportGap, trigger.bottom + menuGap);
    list.style.top = `${Math.max(viewportGap, top)}px`;
  }

  menus().forEach(menu => {
    menu.addEventListener('toggle', () => {
      if (!menu.open) {
        clearPosition(menu);
        return;
      }
      closeMenus(menu);
      window.requestAnimationFrame(() => positionMenu(menu));
    });
  });

  document.addEventListener('click', event => {
    if (!event.target.closest('.action-menu')) closeMenus();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeMenus();
  });
  window.addEventListener('resize', () => closeMenus());
  window.addEventListener('scroll', () => closeMenus(), true);
})();
