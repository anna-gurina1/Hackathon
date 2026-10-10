// main.js — runs on every page: translations, login window and the account menu.

// ---------- Translations (EN / RU) ----------
// base.html puts the texts of translations/<lang>/scripts.json into window.TRANSLATIONS.
// t('Copied ✓')                                  -> 'Скопировано ✓'
// t('Lesson {number}', { number: 2 })            -> 'Урок 2'
// tn(5, '{count} course', '{count} courses')     -> '5 курсов'
// A text without a translation stays in English.
const translations = window.TRANSLATIONS || {};

function fillIn(text, values) {
  return text.replace(/\{(\w+)\}/g, function (placeholder, name) {
    return values && name in values ? values[name] : placeholder;
  });
}

function t(text, values) {
  let translated = translations[text];
  if (Array.isArray(translated)) translated = translated[0];
  return fillIn(translated || text, values);
}

// Russian has 3 forms: 1 курс, 2 курса, 5 курсов
function russianPluralForm(count) {
  const lastDigit = count % 10;
  const lastTwoDigits = count % 100;
  if (lastDigit === 1 && lastTwoDigits !== 11) return 0;
  if (lastDigit >= 2 && lastDigit <= 4 && (lastTwoDigits < 12 || lastTwoDigits > 14)) return 1;
  return 2;
}

function tn(count, singular, plural, values) {
  const allValues = Object.assign({ count: count }, values);
  const forms = translations[singular];
  if (Array.isArray(forms) && forms.length === 3) {
    return fillIn(forms[russianPluralForm(Math.abs(count))], allValues);
  }
  return fillIn(count === 1 ? singular : plural, allValues);
}

// ---------- Login / sign up window ----------
const authModal = document.querySelector('[data-auth-modal]');

if (authModal) {
  // Any button with data-open-auth opens the window
  document.querySelectorAll('[data-open-auth]').forEach(function (button) {
    button.addEventListener('click', function () {
      authModal.showModal();
    });
  });

  authModal.querySelector('[data-close-auth]').addEventListener('click', function () {
    authModal.close();
  });

  // Click on the dark background closes the window
  authModal.addEventListener('click', function (event) {
    if (event.target === authModal) authModal.close();
  });

  // Tabs: "Log in" / "Sign up"
  const authTabs = authModal.querySelectorAll('[data-auth-tab]');
  authTabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      authTabs.forEach(function (otherTab) {
        otherTab.classList.toggle('is-active', otherTab === tab);
      });
      authModal.querySelectorAll('[data-auth-panel]').forEach(function (panel) {
        panel.hidden = panel.dataset.authPanel !== tab.dataset.authTab;
      });
    });
  });

  // Sign up: show name fields for a person, company name for a company
  const personFields = authModal.querySelector('[data-person-fields]');
  const companyFields = authModal.querySelector('[data-company-fields]');
  const companyNameInput = companyFields.querySelector('input');

  authModal.querySelectorAll('[data-account-type]').forEach(function (typeOption) {
    typeOption.addEventListener('change', function () {
      const isCompany = typeOption.value === 'company' && typeOption.checked;
      personFields.hidden = isCompany;
      companyFields.hidden = !isCompany;
      companyNameInput.required = isCompany;
    });
  });
}

// ---------- Account menu under the avatar ----------
const userMenuButton = document.querySelector('[data-user-menu-button]');
const userMenu = document.querySelector('[data-user-menu]');

if (userMenuButton) {
  userMenuButton.addEventListener('click', function (event) {
    event.stopPropagation();
    userMenu.hidden = !userMenu.hidden;
  });

  // Click anywhere else closes the menu
  document.addEventListener('click', function () {
    userMenu.hidden = true;
  });
}

// ---------- Flash messages disappear after 6 seconds ----------
document.querySelectorAll('.flash').forEach(function (message) {
  setTimeout(function () { message.remove(); }, 6000);
});

// ---------- EN / RU switch: a short slide, then the page opens in the other language ----------
// Without JavaScript the switch is a normal link, so it works anyway.
const languageSwitch = document.querySelector('[data-lang-switch]');

if (languageSwitch) {
  const slideTime = 260;   // ms, the same as the transition in style.css
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const startPosition = languageSwitch.style.getPropertyValue('--position');

  languageSwitch.addEventListener('click', function (event) {
    // Ctrl/Cmd+click opens a new tab as usual; people who turned animations off go at once
    if (event.ctrlKey || event.metaKey || event.shiftKey || reduceMotion) return;
    event.preventDefault();
    if (languageSwitch.classList.contains('is-switching')) return;   // double tap

    const options = languageSwitch.querySelectorAll('.lang-option');
    const nextPosition = Number(languageSwitch.dataset.nextPosition);
    languageSwitch.classList.add('is-switching');
    languageSwitch.style.setProperty('--position', nextPosition);
    options.forEach(function (option, index) {
      option.classList.toggle('is-current', index === nextPosition);
    });

    setTimeout(function () { window.location.href = languageSwitch.href; }, slideTime);
  });

  // "Back" in the browser can show this page from memory: put the switch back as it was
  window.addEventListener('pageshow', function (event) {
    if (!event.persisted) return;
    languageSwitch.classList.remove('is-switching');
    languageSwitch.style.setProperty('--position', startPosition);
    languageSwitch.querySelectorAll('.lang-option').forEach(function (option, index) {
      option.classList.toggle('is-current', String(index) === startPosition);
    });
  });
}

// ---------- "Translate" button next to texts written by users ----------
// The server adds the button only when the text is not in the language of the site
// (backend/translator.py). The pressed button is translated first; right after that all the
// other buttons of the page are translated in the background in ONE request, so when the
// person presses the next one, the translation opens at once. Later taps only hide/show.
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const translationRequests = new Map();   // button -> its request that is still running

function showTranslation(button, translations) {
  const box = document.getElementById(button.getAttribute('aria-controls'));
  const labels = JSON.parse(button.dataset.labels || '[]');
  const textBox = box.querySelector('[data-translation-text]');
  textBox.textContent = '';
  translations.forEach(function (translated, index) {
    if (!translated) return;
    const line = document.createElement('p');
    if (labels[index]) {
      const label = document.createElement('span');
      label.className = 'translation-label';
      label.textContent = labels[index] + ' ';
      line.appendChild(label);
    }
    line.appendChild(document.createTextNode(translated));   // text, never HTML
    textBox.appendChild(line);
  });
  box.dataset.loaded = 'yes';
}

function setTranslationOpen(button, isOpen) {
  const box = document.getElementById(button.getAttribute('aria-controls'));
  box.classList.toggle('is-open', isOpen);
  button.setAttribute('aria-expanded', String(isOpen));
  button.textContent = isOpen ? t('Hide translation') : t('Show translation');
}

function isTranslated(button) {
  return Boolean(document.getElementById(button.getAttribute('aria-controls')).dataset.loaded);
}

// One request for several buttons; every button gets its own promise (true = translated)
function requestTranslations(buttons) {
  const request = fetch('/api/translate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
    body: JSON.stringify({ sources: buttons.map(function (button) { return button.dataset.translate; }) }),
  })
    .then(function (response) {
      if (!response.ok) throw new Error('translate: ' + response.status);
      return response.json();
    })
    .then(function (data) {
      buttons.forEach(function (button, index) { showTranslation(button, data.translations[index]); });
      return true;
    })
    .catch(function () { return false; })
    .finally(function () {
      buttons.forEach(function (button) { translationRequests.delete(button); });
    });
  buttons.forEach(function (button) { translationRequests.set(button, request); });
  return request;
}

function translateRestOfPageInBackground() {
  const waiting = Array.from(document.querySelectorAll('[data-translate]')).filter(function (button) {
    return !isTranslated(button) && !translationRequests.has(button);
  });
  if (waiting.length) requestTranslations(waiting);   // an error here is quiet: a tap will try again
}

document.addEventListener('click', async function (event) {
  const button = event.target.closest('[data-translate]');
  if (!button) return;
  event.preventDefault();

  if (isTranslated(button)) {
    const box = document.getElementById(button.getAttribute('aria-controls'));
    setTranslationOpen(button, !box.classList.contains('is-open'));
    return;
  }
  if (button.disabled) return;

  const normalLabel = button.textContent;
  button.disabled = true;
  button.textContent = t('Translating…');

  // already on its way in the background? then just wait for it
  const backgroundRequest = translationRequests.get(button);
  let translated = await (backgroundRequest || requestTranslations([button]));
  if (backgroundRequest && !translated) {
    translated = await requestTranslations([button]);   // the background request failed: ask for this one
  }

  if (translated || isTranslated(button)) {
    button.disabled = false;
    setTranslationOpen(button, true);
    translateRestOfPageInBackground();
  } else {
    button.textContent = t('Could not translate, try later');
    setTimeout(function () {
      button.textContent = normalLabel;
      button.disabled = false;
    }, 3000);
  }
});
