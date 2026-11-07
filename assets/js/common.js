function extractPlainText(value) {
  if (!value) return '';
  if (typeof value === 'string') return value.trim();
  if (Array.isArray(value)) return value.map(item => (item && item.type === 'text' ? item.text : (item.name || ''))).join('').trim();
  if (value && value.text) return value.text.trim();
  return String(value).trim();
}
function escapeHTML(str) { if (!str) return ''; return str.replace(/[&<>'"]/g, tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag])); }
function formatTimeRange(startTs, endTs, fallbackTs) {
  const fmt = (ts) => { if (!ts) return ''; const d = new Date(ts); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const s = fmt(startTs), e = fmt(endTs); 
  if (s && e && s !== e) return `${s} 至 ${e}`; 
  return s || e || fmt(fallbackTs);
}
function generateReportLink(uid) { 
  const email = '1077401836@qq.com'; 
  const subject = encodeURIComponent(`[清湾校史档案举报] 发现违规内容 - UID: ${uid}`); 
  const body = encodeURIComponent(`您好，\n\n我认为该档案（UID: ${uid}）存在侵权或违规问题，请核实处理。\n\n补充说明：`); 
  return `mailto:${email}?subject=${subject}&body=${body}`; 
}
function initThemeToggle() {
  const toggleBtn = document.getElementById('themeToggle'), sunIcon = document.getElementById('icon-sun'), moonIcon = document.getElementById('icon-moon');
  if (!toggleBtn) return;
  if (localStorage.getItem('theme') === 'dark' || (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)) { document.documentElement.setAttribute('data-theme', 'dark'); sunIcon.style.display = 'none'; moonIcon.style.display = 'block'; }
  toggleBtn.addEventListener('click', () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) { document.documentElement.removeAttribute('data-theme'); localStorage.setItem('theme', 'light'); sunIcon.style.display = 'block'; moonIcon.style.display = 'none'; } 
    else { document.documentElement.setAttribute('data-theme', 'dark'); localStorage.setItem('theme', 'dark'); sunIcon.style.display = 'none'; moonIcon.style.display = 'block'; }
  });
}
