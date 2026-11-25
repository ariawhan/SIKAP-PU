document.querySelector('[data-password-toggle]')?.addEventListener('click',function(){const input=document.querySelector('#password');input.type=input.type==='password'?'text':'password'});

const sidebar=document.querySelector('#sidebar');
const menuToggle=document.querySelector('[data-menu-toggle]');
const sidebarClose=document.querySelector('[data-sidebar-close]');

function isDesktop(){return window.matchMedia('(min-width:1024px)').matches}
function syncSidebarState(){
  if(!menuToggle)return;
  const open=isDesktop()? !document.documentElement.classList.contains('sidebar-collapsed') : sidebar?.classList.contains('open');
  menuToggle.setAttribute('aria-expanded',String(Boolean(open)));
}
function toggleSidebar(){
  if(isDesktop()){
    const closed=document.documentElement.classList.toggle('sidebar-collapsed');
    try{localStorage.setItem('sikap-pu-sidebar',closed?'closed':'open')}catch(e){}
  }else{
    sidebar?.classList.toggle('open');
  }
  syncSidebarState();
}
function closeSidebar(){
  if(isDesktop()){
    document.documentElement.classList.add('sidebar-collapsed');
    try{localStorage.setItem('sikap-pu-sidebar','closed')}catch(e){}
  }else sidebar?.classList.remove('open');
  syncSidebarState();
}
menuToggle?.addEventListener('click',toggleSidebar);
sidebarClose?.addEventListener('click',closeSidebar);
document.addEventListener('click',e=>{if(sidebar?.classList.contains('open')&&!sidebar.contains(e.target)&&!e.target.closest('[data-menu-toggle]')){sidebar.classList.remove('open');syncSidebarState()}});
window.addEventListener('resize',()=>{if(isDesktop())sidebar?.classList.remove('open');syncSidebarState()});
syncSidebarState();

document.querySelectorAll('[data-sidebar-dropdown]').forEach(dropdown=>{
  const toggle=dropdown.querySelector('[data-sidebar-dropdown-toggle]');
  if(!toggle)return;
  dropdown.classList.remove('open');
  toggle.setAttribute('aria-expanded','false');
  toggle.addEventListener('click',()=>{
    const open=dropdown.classList.toggle('open');
    toggle.setAttribute('aria-expanded',String(open));
  });
});

const themeToggle=document.querySelector('[data-theme-toggle]');
function syncThemeButton(){
  if(!themeToggle)return;
  const dark=document.documentElement.classList.contains('dark');
  themeToggle.setAttribute('aria-label',dark?'Aktifkan mode terang':'Aktifkan mode gelap');
  themeToggle.setAttribute('aria-pressed',String(dark));
}
themeToggle?.addEventListener('click',()=>{
  const dark=document.documentElement.classList.toggle('dark');
  try{localStorage.setItem('sikap-pu-theme',dark?'dark':'light')}catch(e){}
  syncThemeButton();
});
syncThemeButton();

const webNotification=document.querySelector('[data-web-notification]');
const webNotificationToggle=document.querySelector('[data-web-notification-toggle]');
const webNotificationPanel=document.querySelector('[data-web-notification-panel]');
const webNotificationRead=document.querySelector('[data-web-notification-read]');
const webNotificationCount=document.querySelector('[data-web-notification-count]');
const webNotificationEmpty=webNotification?.querySelector('.web-notification-empty');
const webNotificationList=webNotification?.querySelector('.web-notification-list');

function syncWebNotificationState(){
  if(!webNotification)return;
  const items=webNotification.querySelectorAll('.web-notification-item');
  const unread=webNotification.querySelectorAll('.web-notification-item.unread');
  if(webNotificationEmpty)webNotificationEmpty.hidden=items.length>0;
  if(webNotificationCount){
    webNotificationCount.textContent=String(unread.length);
    webNotificationCount.hidden=unread.length===0;
  }
  if(webNotificationRead)webNotificationRead.disabled=unread.length===0;
}

function setWebNotificationOpen(open){
  if(!webNotificationToggle||!webNotificationPanel)return;
  webNotificationToggle.setAttribute('aria-expanded',String(open));
  webNotificationPanel.hidden=!open;
}

webNotificationToggle?.addEventListener('click',event=>{
  event.stopPropagation();
  setHeaderProfileOpen(false);
  setWebNotificationOpen(webNotificationPanel?.hidden ?? true);
});

webNotificationPanel?.addEventListener('click',event=>event.stopPropagation());

document.addEventListener('click',event=>{
  if(webNotification&&!webNotification.contains(event.target))setWebNotificationOpen(false);
});

document.addEventListener('keydown',event=>{
  if(event.key==='Escape')setWebNotificationOpen(false);
});

webNotificationRead?.addEventListener('click',async()=>{
  const readUrl=webNotification?.dataset.readUrl;
  if(!readUrl)return;
  const csrf=document.querySelector('[name=csrfmiddlewaretoken]')?.value||'';
  webNotificationRead.disabled=true;
  try{
    const response=await fetch(readUrl,{method:'POST',headers:{'X-CSRFToken':csrf,'Accept':'application/json'}});
    if(!response.ok)throw new Error('Gagal menandai notifikasi');
    webNotification?.querySelectorAll('.web-notification-item.unread').forEach(item=>item.classList.remove('unread'));
  }catch(error){
    webNotificationRead.disabled=false;
  }
  syncWebNotificationState();
});

syncWebNotificationState();

const headerProfile=document.querySelector('[data-header-profile]');
const headerProfileToggle=document.querySelector('[data-header-profile-toggle]');
const headerProfileMenu=document.querySelector('[data-header-profile-menu]');

function setHeaderProfileOpen(open){
  if(!headerProfileToggle||!headerProfileMenu)return;
  headerProfileToggle.setAttribute('aria-expanded',String(open));
  headerProfileMenu.hidden=!open;
}

headerProfileToggle?.addEventListener('click',event=>{
  event.stopPropagation();
  setWebNotificationOpen(false);
  setHeaderProfileOpen(headerProfileMenu?.hidden ?? true);
});

headerProfileMenu?.addEventListener('click',event=>event.stopPropagation());

document.addEventListener('click',event=>{
  if(headerProfile&&!headerProfile.contains(event.target))setHeaderProfileOpen(false);
});

document.addEventListener('keydown',event=>{
  if(event.key==='Escape'){
    const wasOpen=Boolean(headerProfileMenu&&!headerProfileMenu.hidden);
    setHeaderProfileOpen(false);
    if(wasOpen)headerProfileToggle?.focus();
  }
});
