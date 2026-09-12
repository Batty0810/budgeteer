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
