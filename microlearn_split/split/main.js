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
  }

  // Dismissible flash messages
  document.querySelectorAll(".flash-close").forEach((btn) => {
    if (btn.closest(".flash")) {
      btn.addEventListener("click", () => btn.closest(".flash").remove());
    }
  });
});
