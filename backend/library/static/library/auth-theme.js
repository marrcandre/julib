(() => {
  let theme;
  try { theme = localStorage.getItem('julib-theme'); } catch {}
  if (theme !== 'light' && theme !== 'dark') {
    theme = window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }
  const apply = () => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    const button = document.querySelector('.theme-toggle');
    if (button) {
      button.textContent = theme === 'dark' ? '☀' : '☾';
      button.setAttribute('aria-label', theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro');
      button.title = button.getAttribute('aria-label');
    }
  };
  apply();
  document.addEventListener('DOMContentLoaded', () => {
    apply();
    document.querySelector('.theme-toggle')?.addEventListener('click', () => {
      theme = theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('julib-theme', theme); } catch {}
      apply();
    });
  });
})();
