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
