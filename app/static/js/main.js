// Auto-dismiss flash messages after a few seconds.
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });

  // Confirm before destructive actions (delete buttons/forms).
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // Mobile nav toggle.
  const navToggle = document.getElementById("navToggle");
  const navLinks = document.getElementById("navLinks");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
      const isOpen = navLinks.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }

  // Show a block only while the checkbox it names is ticked.
  document.querySelectorAll("[data-show-if-checked]").forEach((block) => {
    const checkbox = document.getElementById(block.dataset.showIfChecked);
    if (!checkbox) return;
    const sync = () => { block.hidden = !checkbox.checked; };
    checkbox.addEventListener("change", sync);
    sync();
  });

  // Toggle "view as table" disclosures next to charts.
  document.querySelectorAll(".table-view-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      target.classList.toggle("open");
      btn.textContent = target.classList.contains("open") ? "Hide table view" : "View as table";
    });
  });
});
