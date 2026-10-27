// Apply the theme before styles paint, so a saved dark theme does not flash white.
(function () {
  const root = document.documentElement;
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
  let preference = null;
  try { preference = localStorage.getItem('bitwise-theme'); } catch (error) { /* Storage can be blocked. */ }
  if (preference !== 'light' && preference !== 'dark') preference = null;
  root.classList.add('js');

  function applyTheme(theme) {
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    const meta = document.querySelector('[data-theme-color]');
    if (meta) meta.content = theme === 'dark' ? '#18151d' : '#faf9fc';
    const button = document.querySelector('[data-theme-toggle]');
    if (button) button.setAttribute('aria-pressed', String(theme === 'dark'));
  }

  applyTheme(preference || (systemTheme.matches ? 'dark' : 'light'));
  systemTheme.addEventListener('change', function (event) {
    if (!preference) applyTheme(event.matches ? 'dark' : 'light');
  });
  document.addEventListener('DOMContentLoaded', function () {
    const button = document.querySelector('[data-theme-toggle]');
    if (!button) return;
    button.hidden = false;
    button.setAttribute('aria-pressed', String(root.dataset.theme === 'dark'));
    button.addEventListener('click', function () {
      preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('bitwise-theme', preference); } catch (error) { /* Still works in this tab. */ }
      applyTheme(preference);
    });
  });
})();
