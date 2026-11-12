(() => {
  let theme;
  try { theme = localStorage.getItem('julib-theme'); } catch {}
  if (theme !== 'light' && theme !== 'dark') {
    theme = window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  document.documentElement.classList.toggle('dark', theme === 'dark');
})();
