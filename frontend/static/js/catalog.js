// Progressive enhancement: the GET form still works when JavaScript is disabled.
// This controller owns URL/form state and request lifecycle; card markup is separate.
import {
  makeCompanyCard,
  makeCourseCard,
  makeMessageCard
} from './catalog-cards.js';

const SEARCH_DELAY_MS = 300;
const LANGUAGE_PREFERENCE_KEY = 'onlyMyLanguage';
const form = document.querySelector('[data-search-form]');
if (form) initializeCatalog(form);

function initializeCatalog(form) {
  // Read stable DOM references once rather than looking them up on every keystroke.
  const input = form.querySelector('[data-search-input]');
  const language = form.querySelector('[data-only-my-language]');
  const languageBox = form.querySelector('[data-only-my-language-box]');
  const languageLabel = form.querySelector('[data-language-filter-label]');
  const topic = form.querySelector('[data-topic-filter]'); // Optional in an empty catalog.
  const results = document.querySelector('[data-search-results]');
  const status = document.querySelector('[data-search-status]');
  const heading = document.querySelector('.catalog-results-heading h2');
  let typingTimer;
  let activeRequest;
  let requestNumber = 0;

  function readForm() {
    const parameters = new URLSearchParams(new FormData(form));
    if (parameters.get('by') === 'company') {
      parameters.delete('lang');
      parameters.delete('topic');
    }
    for (const [key, value] of Array.from(parameters)) {
      if (!value.trim()) parameters.delete(key);
    }
    return parameters;
  }

  function updateFilterAvailability() {
    const companyMode = form.elements.by.value === 'company';
    languageBox.hidden = companyMode;
    language.disabled = companyMode;
    languageLabel.textContent = language.value === 'ru' ?
      t('Only courses in Russian') : t('Only courses in English');
    if (topic) topic.disabled = companyMode;
    heading.textContent = companyMode ? t('Companies') : t('Courses');
  }

  function writeURL(parameters, mode) {
    if (!mode) return; // Browser Back already changed the URL.
    const url = new URL(location.href);
    url.search = parameters.toString();
    history[mode === 'push' ? 'pushState' : 'replaceState'](null, '', url);
  }

  function restoreFormFromURL() {
    const parameters = new URLSearchParams(location.search);
    input.value = parameters.get('q') || '';
    const mode = parameters.get('by');
    form.elements.by.value = ['company', 'profession', 'result'].includes(mode) ? mode : 'topic';
    language.checked = ['ru', 'en'].includes(parameters.get('lang'));
    language.value = parameters.get('lang') || document.documentElement.lang;
    if (topic) topic.value = parameters.get('topic') || '';
  }

  function cancelPendingSearch() {
    clearTimeout(typingTimer);
    // Advance immediately: an old response must not win during the typing delay.
    requestNumber += 1;
    if (activeRequest) activeRequest.abort();
  }

  function resetFilters() {
    form.reset();
    input.value = '';
    form.elements.by.value = 'topic';
    language.checked = false;
    language.value = document.documentElement.lang;
    if (topic) topic.value = '';
    saveLanguagePreference(null);
    runSearch('push');
  }

  function showEmptyState(companyMode) {
    results.append(makeMessageCard(
      companyMode ? t('No matching companies') : t('No matching courses'),
      t('Try a different search or clear the filters.'),
      t('Reset filters'),
      resetFilters,
    ));
  }

  function showErrorState() {
    results.replaceChildren(makeMessageCard(
      t('Could not load results'),
      t('Check your connection and try again.'),
      t('Try again'),
      () => runSearch(null),
    ));
    status.textContent = t('Search is unavailable');
  }

  function renderResults(items, companyMode) {
    results.replaceChildren();
    if (!items.length) {
      showEmptyState(companyMode);
    } else {
      const fragment = document.createDocumentFragment();
      for (const item of items) {
        fragment.append(item.type === 'company' ? makeCompanyCard(item) : makeCourseCard(item));
      }
      results.append(fragment);
    }
    status.textContent = companyMode ?
      tn(items.length, '{count} company found', '{count} companies found') :
      tn(items.length, '{count} course found', '{count} courses found');
  }

  async function runSearch(historyMode = 'replace') {
    cancelPendingSearch();
    const thisRequest = requestNumber;
    const controller = new AbortController();
    activeRequest = controller;
    updateFilterAvailability();
    const parameters = readForm();
    writeURL(parameters, historyMode);
    results.setAttribute('aria-busy', 'true');
    status.textContent = t('Searching…');

    try {
      const response = await fetch('/api/search?' + parameters, {
        signal: controller.signal
      });
      if (!response.ok) throw new Error('Search request failed');
      const items = await response.json();
      if (!Array.isArray(items)) throw new Error('Unexpected search response');
      if (thisRequest !== requestNumber) return;
      renderResults(items, parameters.get('by') === 'company');
    } catch (error) {
      if (error.name === 'AbortError' || thisRequest !== requestNumber) return;
      showErrorState();
    } finally {
      if (thisRequest === requestNumber) results.setAttribute('aria-busy', 'false');
    }
  }

  // Event wiring is kept together so the reader can see every search trigger.
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    runSearch('push');
  });
  form.addEventListener('change', (event) => {
    // Text uses input + submit. Its blur/change would duplicate the submit history entry.
    if (event.target === input) return;
    if (event.target === language) saveLanguagePreference(language.checked ? 'yes' : 'no');
    runSearch('push');
  });
  input.addEventListener('input', () => {
    cancelPendingSearch();
    typingTimer = setTimeout(() => runSearch(), SEARCH_DELAY_MS);
  });
  window.addEventListener('popstate', () => {
    restoreFormFromURL();
    runSearch(null);
  });

  updateFilterAvailability();
  // Keep server HTML intact. Only an explicit saved preference needs an initial request.
  if (!location.search && readLanguagePreference() === 'yes') {
    language.checked = true;
    runSearch();
  }
}

function readLanguagePreference() {
  try {
    return localStorage.getItem(LANGUAGE_PREFERENCE_KEY);
  } catch {
    return null;
  } // Storage can be blocked; search must still work.
}

function saveLanguagePreference(value) {
  try {
    if (value === null) localStorage.removeItem(LANGUAGE_PREFERENCE_KEY);
    else localStorage.setItem(LANGUAGE_PREFERENCE_KEY, value);
  } catch {
    // Optional preference: never block the catalog.
  }
}
