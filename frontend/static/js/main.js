// main.js — runs on every page: login window and the account menu.

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
