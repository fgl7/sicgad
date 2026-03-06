(function () {
  var isTransitioning = false;
  var QUERY_NAV_CLASS = "is-route-transitioning-query";
  var PANE_ONLY_NAV_CLASS = "is-route-transitioning-pane-only";
  var BASE_NAV_CLASS = "is-route-transitioning";
  var SIDEBAR_SCROLL_STORAGE_KEY = "sicgad_sidebar_scroll_v1";

  function hasHtmxBehavior(el) {
    if (!el || !el.getAttributeNames) return false;
    var attrs = el.getAttributeNames();
    for (var i = 0; i < attrs.length; i++) {
      var name = attrs[i];
      if (name.indexOf("hx-") === 0 || name.indexOf("data-hx-") === 0) return true;
    }
    return false;
  }

  function shouldSkipLink(link, event) {
    if (!link) return true;
    if (event.defaultPrevented) return true;
    if (event.button !== 0) return true;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return true;
    if (link.target && link.target !== "_self") return true;
    if (link.hasAttribute("download")) return true;
    if (link.hasAttribute("data-no-route-transition")) return true;
    if (link.hasAttribute("onclick")) return true;
    if (link.hasAttribute("@click") || link.hasAttribute("x-on:click")) return true;
    if (link.getAttribute("role") === "button") return true;
    if (link.hasAttribute("aria-controls") || link.hasAttribute("data-bs-toggle")) return true;

    var hrefAttr = link.getAttribute("href");
    if (!hrefAttr) return true;
    if (hrefAttr.charAt(0) === "#") return true;
    if (hrefAttr.indexOf("javascript:") === 0) return true;
    if (hrefAttr.indexOf("mailto:") === 0 || hrefAttr.indexOf("tel:") === 0) return true;

    if (hasHtmxBehavior(link)) return true;
    if (link.closest("[hx-boost],[data-hx-boost]")) return true;
    if (
      link.closest(
        "[hx-get],[data-hx-get],[hx-post],[data-hx-post],[hx-put],[data-hx-put],[hx-patch],[data-hx-patch],[hx-delete],[data-hx-delete]"
      )
    ) {
      return true;
    }

    var url;
    try {
      url = new URL(link.href, window.location.href);
    } catch (_err) {
      return true;
    }

    if (url.origin !== window.location.origin) return true;
    if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) return true;
    if (url.href === window.location.href) return true;
    return false;
  }

  function isSamePathQueryNavigation(link) {
    if (!link || !link.href) return false;
    var nextUrl;
    try {
      nextUrl = new URL(link.href, window.location.href);
    } catch (_err) {
      return false;
    }
    var currentUrl;
    try {
      currentUrl = new URL(window.location.href);
    } catch (_err2) {
      return false;
    }

    if (nextUrl.origin !== currentUrl.origin) return false;
    if (nextUrl.pathname !== currentUrl.pathname) return false;
    if (nextUrl.search === currentUrl.search) return false;
    return true;
  }

  function isSidebarNavigation(link) {
    return Boolean(link && link.closest && link.closest(".sidebar"));
  }

  function safeSetSessionStorage(key, value) {
    try {
      window.sessionStorage.setItem(key, value);
    } catch (_err) {
      // ignore storage restrictions
    }
  }

  function safeGetSessionStorage(key) {
    try {
      return window.sessionStorage.getItem(key);
    } catch (_err) {
      return null;
    }
  }

  function saveSidebarScrollForLink(link) {
    if (!isSidebarNavigation(link)) return;
    var sidebar = link.closest(".sidebar");
    if (!sidebar) return;
    var nav = sidebar.querySelector("nav");
    if (!nav) return;
    safeSetSessionStorage(SIDEBAR_SCROLL_STORAGE_KEY, String(nav.scrollTop || 0));
  }

  function restoreSidebarScroll() {
    var raw = safeGetSessionStorage(SIDEBAR_SCROLL_STORAGE_KEY);
    if (raw == null) return;
    var value = Number(raw);
    if (!Number.isFinite(value) || value < 0) return;
    var navs = document.querySelectorAll(".sidebar nav");
    if (!navs || !navs.length) return;
    for (var i = 0; i < navs.length; i++) {
      navs[i].scrollTop = value;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", restoreSidebarScroll, { once: true });
  } else {
    restoreSidebarScroll();
  }

  document.addEventListener(
    "click",
    function (event) {
      var link = event.target.closest("a");
      if (shouldSkipLink(link, event)) return;

      if (isTransitioning) {
        event.preventDefault();
        return;
      }

      isTransitioning = true;
      var isQueryNavigation = isSamePathQueryNavigation(link);
      var isSidebarNav = isSidebarNavigation(link);
      var usePaneOnlyTransition = isSidebarNav || isQueryNavigation;
      if (isSidebarNav) {
        saveSidebarScrollForLink(link);
      }
      document.body.classList.add(BASE_NAV_CLASS);
      if (isQueryNavigation) {
        document.body.classList.add(QUERY_NAV_CLASS);
      } else {
        document.body.classList.remove(QUERY_NAV_CLASS);
      }
      if (usePaneOnlyTransition) {
        document.body.classList.add(PANE_ONLY_NAV_CLASS);
      } else {
        document.body.classList.remove(PANE_ONLY_NAV_CLASS);
      }
      event.preventDefault();

      window.setTimeout(function () {
        window.location.href = link.href;
      }, usePaneOnlyTransition ? 120 : 85);
    },
    true
  );

  window.addEventListener("pageshow", function () {
    isTransitioning = false;
    document.body.classList.remove(BASE_NAV_CLASS);
    document.body.classList.remove(QUERY_NAV_CLASS);
    document.body.classList.remove(PANE_ONLY_NAV_CLASS);
    restoreSidebarScroll();
  });
})();
