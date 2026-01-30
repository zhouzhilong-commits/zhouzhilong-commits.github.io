(function () {
  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function $all(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  var root = $("#home-archive");
  if (!root) return;

  var baseurl = root.getAttribute("data-baseurl") || "";
  var currentPage = parseInt(root.getAttribute("data-current-page") || "1", 10);
  // Enhance paginated index pages too (/, /page2/, /page3/ ...), respecting baseurl.
  var homePath = (baseurl + "/").replace(/\/+$/, "/");
  var pagedRe = new RegExp("^" + (baseurl || "") + "/page\\d+/?$");
  if (window.location.pathname !== homePath && !pagedRe.test(window.location.pathname)) return;

  var content = $("#home-archive-content", root);
  // controls live outside #home-archive (bottom bar), so query globally.
  var controls = document.getElementById("home-archive-controls");
  if (!content || !controls) return;

  var basePageSize = parseInt(root.getAttribute("data-base-page-size") || "10", 10);
  var totalPages = parseInt(root.getAttribute("data-total-pages") || "1", 10);

  var STORAGE_KEY = "homePageSize";
  var DEFAULT_SIZE = basePageSize;
  var allowedSizes = [basePageSize, basePageSize * 2, basePageSize * 5].filter(function (n, idx, arr) {
    return n > 0 && arr.indexOf(n) === idx;
  });

  function getSavedSize() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      var n = parseInt(raw || "", 10);
      if (allowedSizes.indexOf(n) >= 0) return n;
    } catch (e) {}
    return DEFAULT_SIZE;
  }

  function saveSize(n) {
    try {
      window.localStorage.setItem(STORAGE_KEY, String(n));
    } catch (e) {}
  }

  var nextPageToFetch = isNaN(currentPage) ? 2 : Math.max(2, currentPage + 1);
  var fetching = false;

  function ensureLoaded(targetCount) {
    return new Promise(function (resolve) {
      var loadedItems = $all(".list__item", content).length;
      if (loadedItems >= targetCount) return resolve();

      function appendFromDoc(doc) {
        var incomingYears = $all("#home-archive-content .archive__year", doc);
        if (incomingYears.length === 0) return;

        incomingYears.forEach(function (section) {
          // Merge year sections if needed.
          var year = section.getAttribute("data-year");
          var last = content.lastElementChild;
          if (last && last.classList && last.classList.contains("archive__year") && last.getAttribute("data-year") === year) {
            $all(".list__item", section).forEach(function (item) {
              last.appendChild(item);
            });
            return;
          }
          content.appendChild(section);
        });
      }

      function fetchNext() {
        if (fetching) return;
        if (nextPageToFetch > totalPages) return resolve();

        fetching = true;
        fetch((baseurl || "") + "/page" + nextPageToFetch + "/")
          .then(function (r) { return r.text(); })
          .then(function (html) {
            var doc = new DOMParser().parseFromString(html, "text/html");
            appendFromDoc(doc);
          })
          .catch(function () {
            // Stop trying on any failure; keep the site usable.
            nextPageToFetch = totalPages + 1;
          })
          .finally(function () {
            fetching = false;
            nextPageToFetch += 1;

            loadedItems = $all(".list__item", content).length;
            if (loadedItems >= targetCount || nextPageToFetch > totalPages) return resolve();
            fetchNext();
          });
      }

      fetchNext();
    });
  }

  function applySize(targetCount) {
    var items = $all(".list__item", content);
    items.forEach(function (el, idx) {
      el.hidden = idx >= targetCount;
    });

    $all(".archive__year", content).forEach(function (section) {
      var visible = $all(".list__item", section).some(function (el) { return !el.hidden; });
      section.hidden = !visible;
    });
  }

  function ensureSelectOptions(select) {
    // If options were already rendered server-side, keep them.
    if (select.options && select.options.length > 0) return;
    allowedSizes.forEach(function (n) {
      var opt = document.createElement("option");
      opt.value = String(n);
      opt.textContent = String(n);
      select.appendChild(opt);
    });
  }

  var selectEl = document.getElementById("homePageSizeSelect");
  if (!selectEl) return;
  ensureSelectOptions(selectEl);
  var initial = getSavedSize();
  selectEl.value = String(initial);

  ensureLoaded(initial).then(function () {
    applySize(initial);
  });

  selectEl.addEventListener("change", function () {
    var n = parseInt(selectEl.value || "", 10);
    if (!n || allowedSizes.indexOf(n) < 0) return;
    saveSize(n);
    ensureLoaded(n).then(function () {
      applySize(n);
    });
  });
})();

