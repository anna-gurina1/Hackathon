document.addEventListener("DOMContentLoaded", () => {
  // Avatar dropdown
  const avatarBtn = document.getElementById("avatar-btn");
  const dropdown = document.getElementById("avatar-dropdown");
  if (avatarBtn && dropdown) {
    const setOpen = (open) => {
      dropdown.hidden = !open;
      avatarBtn.setAttribute("aria-expanded", String(open));
    };
    avatarBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      setOpen(dropdown.hidden);
    });
    document.addEventListener("click", (e) => {
      if (!dropdown.contains(e.target)) setOpen(false);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") setOpen(false);
    });
  }

  // Auth modal (guests)
  const modal = document.getElementById("auth-modal");
  if (modal) {
    document
      .querySelectorAll("#auth-open, [data-open-auth]")
      .forEach((btn) => btn.addEventListener("click", () => modal.showModal()));
    const closeBtn = document.getElementById("auth-close");
    if (closeBtn) closeBtn.addEventListener("click", () => modal.close());
    modal.addEventListener("click", (e) => {
      if (e.target === modal) modal.close();
    });

    // Tabs: "Log in" / "Sign up"
    const tabs = modal.querySelectorAll("[data-auth-tab]");
    const showTab = (name) => {
      tabs.forEach((tab) => {
        const active = tab.dataset.authTab === name;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", String(active));
        document.getElementById(tab.getAttribute("aria-controls")).hidden = !active;
      });
    };
    tabs.forEach((tab) =>
      tab.addEventListener("click", () => showTab(tab.dataset.authTab))
    );

    // Sign up: switch fields between "person" and "company" without reload.
    // Hidden fields are disabled so the browser does not validate or send them.
    const typeRadios = modal.querySelectorAll('input[name="type"]');
    const applyType = () => {
      const type = modal.querySelector('input[name="type"]:checked').value;
      modal.querySelectorAll("[data-for-type]").forEach((block) => {
        const on = block.dataset.forType === type;
        block.hidden = !on;
        block.querySelectorAll("input, textarea").forEach((field) => {
          field.disabled = !on;
          if (field.name === "first_name" || field.name === "last_name" ||
              field.name === "company_name") {
            field.required = on;
          }
        });
      });
    };
    typeRadios.forEach((radio) => radio.addEventListener("change", applyType));
    if (typeRadios.length) applyType();

    // After a server error the page opens with ?auth=login or ?auth=signup
    const wanted = new URLSearchParams(window.location.search).get("auth");
    if (wanted === "login" || wanted === "signup") {
      showTab(wanted);
      modal.showModal();
      history.replaceState(null, "", window.location.pathname);
    }
  }

  // Dismissible flash messages
  document.querySelectorAll(".flash-close").forEach((btn) => {
    if (btn.closest(".flash")) {
      btn.addEventListener("click", () => btn.closest(".flash").remove());
    }
  });
});
