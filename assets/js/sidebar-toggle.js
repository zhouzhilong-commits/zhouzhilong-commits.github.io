/*
  Collapsible left sidebar toggle (works with Minimal Mistakes / academicpages layout).
  - Adds an in-sidebar toggle button (more convenient than bottom-left).
  - Adds a small floating button to reopen after collapsing.
  - Persists state in localStorage.
*/

(function () {
  var STORAGE_KEY = "sidebarCollapsed";
  var COLLAPSED_CLASS = "sidebar--collapsed";

  function hasSidebar() {
    return !!document.querySelector(".sidebar");
  }

  function getSidebarEl() {
    return document.querySelector(".sidebar");
  }

  function isToggleDisabled(sidebarEl) {
    if (!sidebarEl) return false;
    return sidebarEl.getAttribute("data-sidebar-toggle") === "false";
  }

  function isCollapsed() {
    return document.documentElement.classList.contains(COLLAPSED_CLASS);
  }

  function applyCollapsedState(collapsed) {
    if (collapsed) {
      document.documentElement.classList.add(COLLAPSED_CLASS);
      try { localStorage.setItem(STORAGE_KEY, "1"); } catch (e) {}
    } else {
      document.documentElement.classList.remove(COLLAPSED_CLASS);
      try { localStorage.setItem(STORAGE_KEY, "0"); } catch (e) {}
    }
    updateButton();
  }

  function iconHtml(direction) {
    // direction: "left" | "right"
    var cls = direction === "left" ? "fa-angle-left" : "fa-angle-right";
    return '<i class="fa ' + cls + '" aria-hidden="true"></i>';
  }

  function updateButton() {
    var collapsed = isCollapsed();

    var sidebarBtn = document.getElementById("sidebar-toggle");
    if (sidebarBtn) {
      sidebarBtn.setAttribute("aria-pressed", collapsed ? "true" : "false");
      sidebarBtn.setAttribute("aria-label", collapsed ? "展开目录" : "收起目录");
      sidebarBtn.setAttribute("title", collapsed ? "展开目录" : "收起目录");
      sidebarBtn.innerHTML = iconHtml(collapsed ? "right" : "left");
    }

    var floatBtn = document.getElementById("sidebar-toggle-float");
    if (floatBtn) {
      floatBtn.setAttribute("aria-pressed", collapsed ? "true" : "false");
      floatBtn.style.display = collapsed ? "inline-flex" : "none";
      floatBtn.setAttribute("aria-label", "展开目录");
      floatBtn.setAttribute("title", "展开目录");
      floatBtn.innerHTML = iconHtml("right");
    }
  }

  function createSidebarButton(sidebarEl) {
    if (!sidebarEl || document.getElementById("sidebar-toggle")) return;

    var btn = document.createElement("button");
    btn.id = "sidebar-toggle";
    btn.className = "sidebar__toggle-btn";
    btn.type = "button";
    btn.setAttribute("aria-pressed", "false");
    btn.addEventListener("click", function () {
      applyCollapsedState(!isCollapsed());
    });

    // Put at the top of sidebar for easy access
    sidebarEl.insertBefore(btn, sidebarEl.firstChild);
  }

  function createFloatingButton() {
    if (document.getElementById("sidebar-toggle-float")) return;

    var btn = document.createElement("button");
    btn.id = "sidebar-toggle-float";
    btn.className = "sidebar__toggle-float";
    btn.type = "button";
    btn.setAttribute("aria-pressed", "false");
    btn.addEventListener("click", function () {
      applyCollapsedState(false);
    });
    document.body.appendChild(btn);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!hasSidebar()) return;

    var sidebarEl = getSidebarEl();
    if (isToggleDisabled(sidebarEl)) {
      // Never collapse on pages that disable the toggle (e.g. homepage)
      document.documentElement.classList.remove(COLLAPSED_CLASS);
      return;
    }

    createFloatingButton();
    createSidebarButton(sidebarEl);

    // Restore state
    var stored = null;
    try { stored = localStorage.getItem(STORAGE_KEY); } catch (e) {}
    if (stored === "1") applyCollapsedState(true);
    updateButton();
  });
})();

