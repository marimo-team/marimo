/**
 * Page Actions Dropdown
 *
 * Adds an "Actions" dropdown to each docs page with options to:
 * - Copy page content as markdown
 * - Open in Claude / ChatGPT
 * - Connect to Cursor / VS Code (via MCP deep links)
 */
(function () {
  const MCP_CONFIG = { name: "marimo", url: "https://mcp.marimo.app/mcp" };
  const CURSOR_DEEP_LINK =
    "cursor://anysphere.cursor-deeplink/mcp/install?name=" +
    encodeURIComponent(MCP_CONFIG.name) +
    "&config=" +
    encodeURIComponent(btoa(JSON.stringify(MCP_CONFIG)));
  const VSCODE_DEEP_LINK =
    "vscode:mcp/install?" +
    encodeURIComponent(JSON.stringify(MCP_CONFIG));

  // --- Icons (inline SVGs) ---

  var ARROW = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="pa-arrow" aria-hidden="true" focusable="false"><path d="M7 7h10v10"></path><path d="M7 17 17 7"></path></svg>';

  var CHEVRON = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="pa-chevron" aria-hidden="true" focusable="false"><path d="m18 15-6-6-6 6"></path></svg>';

  var CHECK = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="pa-check" aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5"></path></svg>';

  var ICONS = {
    copy: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18" fill="none" width="18" height="18" aria-hidden="true" focusable="false"><path d="M14.25 5.25H7.25C6.14543 5.25 5.25 6.14543 5.25 7.25V14.25C5.25 15.3546 6.14543 16.25 7.25 16.25H14.25C15.3546 16.25 16.25 15.3546 16.25 14.25V7.25C16.25 6.14543 15.3546 5.25 14.25 5.25Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M2.80103 11.998L1.77203 5.07397C1.61003 3.98097 2.36403 2.96397 3.45603 2.80197L10.38 1.77297C11.313 1.63397 12.19 2.16297 12.528 3.00097" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    chatgpt: '<svg fill="currentColor" fill-rule="evenodd" viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><path d="M21.55 10.004a5.416 5.416 0 00-.478-4.501c-1.217-2.09-3.662-3.166-6.05-2.66A5.59 5.59 0 0010.831 1C8.39.995 6.224 2.546 5.473 4.838A5.553 5.553 0 001.76 7.496a5.487 5.487 0 00.691 6.5 5.416 5.416 0 00.477 4.502c1.217 2.09 3.662 3.165 6.05 2.66A5.586 5.586 0 0013.168 23c2.443.006 4.61-1.546 5.361-3.84a5.553 5.553 0 003.715-2.66 5.488 5.488 0 00-.693-6.497v.001zm-8.381 11.558a4.199 4.199 0 01-2.675-.954c.034-.018.093-.05.132-.074l4.44-2.53a.71.71 0 00.364-.623v-6.176l1.877 1.069c.02.01.033.029.036.05v5.115c-.003 2.274-1.87 4.118-4.174 4.123zM4.192 17.78a4.059 4.059 0 01-.498-2.763c.032.02.09.055.131.078l4.44 2.53c.225.13.504.13.73 0l5.42-3.088v2.138a.068.068 0 01-.027.057L9.9 19.288c-1.999 1.136-4.552.46-5.707-1.51h-.001zM3.023 8.216A4.15 4.15 0 015.198 6.41l-.002.151v5.06a.711.711 0 00.364.624l5.42 3.087-1.876 1.07a.067.067 0 01-.063.005l-4.489-2.559c-1.995-1.14-2.679-3.658-1.53-5.63h.001zm15.417 3.54l-5.42-3.088L14.896 7.6a.067.067 0 01.063-.006l4.489 2.557c1.998 1.14 2.683 3.662 1.529 5.633a4.163 4.163 0 01-2.174 1.807V12.38a.71.71 0 00-.363-.623zm1.867-2.773a6.04 6.04 0 00-.132-.078l-4.44-2.53a.731.731 0 00-.729 0l-5.42 3.088V7.325a.068.068 0 01.027-.057L14.1 4.713c2-1.137 4.555-.46 5.707 1.513.487.833.664 1.809.499 2.757h.001zm-11.741 3.81l-1.877-1.068a.065.065 0 01-.036-.051V6.559c.001-2.277 1.873-4.122 4.181-4.12.976 0 1.92.338 2.671.954-.034.018-.092.05-.131.073l-4.44 2.53a.71.71 0 00-.365.623l-.003 6.173v.002zm1.02-2.168L12 9.25l2.414 1.375v2.75L12 14.75l-2.415-1.375v-2.75z"></path></svg>',
    claude: '<svg fill="currentColor" fill-rule="evenodd" viewBox="0 0 256 257" width="18" height="18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><path d="m50.228 170.321 50.357-28.257.843-2.463-.843-1.361h-2.462l-8.426-.518-28.775-.778-24.952-1.037-24.175-1.296-6.092-1.297L0 125.796l.583-3.759 5.12-3.434 7.324.648 16.202 1.101 24.304 1.685 17.629 1.037 26.118 2.722h4.148l.583-1.685-1.426-1.037-1.101-1.037-25.147-17.045-27.22-18.017-14.258-10.37-7.713-5.25-3.888-4.925-1.685-10.758 7-7.713 9.397.649 2.398.648 9.527 7.323 20.35 15.75L94.817 91.9l3.889 3.24 1.555-1.102.195-.777-1.75-2.917-14.453-26.118-15.425-26.572-6.87-11.018-1.814-6.61c-.648-2.723-1.102-4.991-1.102-7.778l7.972-10.823L71.42 0 82.05 1.426l4.472 3.888 6.61 15.101 10.694 23.786 16.591 32.34 4.861 9.592 2.592 8.879.973 2.722h1.685v-1.556l1.36-18.211 2.528-22.36 2.463-28.776.843-8.1 4.018-9.722 7.971-5.25 6.222 2.981 5.12 7.324-.713 4.73-3.046 19.768-5.962 30.98-3.889 20.739h2.268l2.593-2.593 10.499-13.934 17.628-22.036 7.778-8.749 9.073-9.657 5.833-4.601h11.018l8.1 12.055-3.628 12.443-11.342 14.388-9.398 12.184-13.48 18.147-8.426 14.518.778 1.166 2.01-.194 30.46-6.481 16.462-2.982 19.637-3.37 8.88 4.148.971 4.213-3.5 8.62-20.998 5.184-24.628 4.926-36.682 8.685-.454.324.519.648 16.526 1.555 7.065.389h17.304l32.21 2.398 8.426 5.574 5.055 6.805-.843 5.184-12.962 6.611-17.498-4.148-40.83-9.721-14-3.5h-1.944v1.167l11.666 11.406 21.387 19.314 26.767 24.887 1.36 6.157-3.434 4.86-3.63-.518-23.526-17.693-9.073-7.972-20.545-17.304h-1.36v1.814l4.73 6.935 25.017 37.59 1.296 11.536-1.814 3.76-6.481 2.268-7.13-1.297-14.647-20.544-15.1-23.138-12.185-20.739-1.49.843-7.194 77.448-3.37 3.953-7.778 2.981-6.48-4.925-3.436-7.972 3.435-15.749 4.148-20.544 3.37-16.333 3.046-20.285 1.815-6.74-.13-.454-1.49.194-15.295 20.999-23.267 31.433-18.406 19.702-4.407 1.75-7.648-3.954.713-7.064 4.277-6.286 25.47-32.405 15.36-20.092 9.917-11.6-.065-1.686h-.583L44.07 198.125l-12.055 1.555-5.185-4.86.648-7.972 2.463-2.593 20.35-13.999-.064.065Z"></path></svg>',
    cursor: '<svg viewBox="0 0 16 16" width="18" height="18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><path d="M14.4734 3.9527L8.31773 0.398522C8.22052 0.342485 8.11029 0.312988 7.99809 0.312988C7.88589 0.312988 7.77566 0.342485 7.67846 0.398522L1.52355 3.9527C1.44182 3.99989 1.37394 4.06773 1.32671 4.14942C1.27948 4.23112 1.25457 4.32379 1.25446 4.41816V11.584C1.25457 11.6783 1.27948 11.771 1.32671 11.8527C1.37394 11.9344 1.44182 12.0022 1.52355 12.0494L7.67918 15.6036C7.77636 15.6597 7.8866 15.6893 7.99882 15.6893C8.11103 15.6893 8.22127 15.6597 8.31846 15.6036L14.4741 12.0502C14.5558 12.003 14.6237 11.9351 14.6709 11.8534C14.7182 11.7717 14.7431 11.6791 14.7432 11.5847V4.41743C14.7431 4.32307 14.7182 4.23039 14.6709 4.14869C14.6237 4.067 14.5558 3.99916 14.4741 3.95198L14.4734 3.9527ZM14.0872 4.70543L8.14464 14.9978C8.10464 15.0669 7.99846 15.0385 7.99846 14.9578V8.21889C7.99841 8.15254 7.98092 8.08738 7.94773 8.02993C7.91454 7.97249 7.86682 7.92478 7.80936 7.89161L1.97373 4.52361C1.90391 4.48289 1.93227 4.3767 2.013 4.3767H13.8966C14.0661 4.3767 14.1715 4.55925 14.0872 4.70543Z" fill="currentColor"></path></svg>',
    vscode: '<svg viewBox="0 0 100 100" fill="currentColor" width="18" height="18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false"><path fill-rule="evenodd" clip-rule="evenodd" d="M70.9119 99.3171C72.4869 99.9307 74.2828 99.8914 75.8725 99.1264L96.4608 89.2197C98.6242 88.1787 100 85.9892 100 83.5872V16.4133C100 14.0113 98.6243 11.8218 96.4609 10.7808L75.8725 0.873756C73.7862 -0.130129 71.3446 0.11576 69.5135 1.44695C69.252 1.63711 69.0028 1.84943 68.769 2.08341L29.3551 38.0415L12.1872 25.0096C10.589 23.7965 8.35363 23.8959 6.86933 25.2461L1.36303 30.2549C-0.452552 31.9064 -0.454633 34.7627 1.35853 36.417L16.2471 50.0001L1.35853 63.5832C-0.454633 65.2374 -0.452552 68.0938 1.36303 69.7453L6.86933 74.7541C8.35363 76.1043 10.589 76.2037 12.1872 74.9905L29.3551 61.9587L68.769 97.9167C69.3925 98.5406 70.1246 99.0104 70.9119 99.3171ZM75.0152 27.2989L45.1091 50.0001L75.0152 72.7012V27.2989Z"></path></svg>',
  };

  // --- Markdown fetching ---

  async function getMarkdownContent() {
    try {
      var pathname = window.location.pathname;
      var mdUrl =
        pathname === "/" ? "/index.md" : pathname.replace(/\/$/, "") + ".md";
      var response = await fetch(mdUrl);
      if (response.ok) {
        var contentType = response.headers.get("content-type") || "";
        if (contentType.includes("text/markdown")) {
          return await response.text();
        }
      }
    } catch (_) {
      // Fetch failed (local dev, CORS, etc.) — fall through to fallback
    }
    // Fallback: extract rendered text, excluding the dropdown itself
    var article = document.querySelector("article.md-content__inner");
    if (!article) return document.title;
    var clone = article.cloneNode(true);
    clone.querySelectorAll(".pa-dropdown").forEach(function (el) {
      el.remove();
    });
    return clone.innerText;
  }

  // --- Copy with fallback ---

  function fallbackCopyText(text) {
    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    var copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (_) {
      copied = false;
    }
    document.body.removeChild(textarea);
    return copied;
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) {
      // Fall through to execCommand fallback
    }
    return fallbackCopyText(text);
  }

  // --- Action handlers ---

  async function handleCopy(item) {
    var markdown = await getMarkdownContent();
    var ok = await copyText(markdown);
    if (ok) {
      showCopied(item);
    } else {
      showCopyError(item);
    }
  }

  function handleOpenInClaude() {
    var pageUrl = window.location.href;
    var q = "Read from " + pageUrl + " so I can ask questions about it.";
    window.open(
      "https://claude.ai/new?q=" + encodeURIComponent(q),
      "_blank",
      "noopener,noreferrer"
    );
  }

  function handleOpenInChatGPT() {
    var pageUrl = window.location.href;
    var q = "Read from " + pageUrl + " so I can ask questions about it.";
    window.open(
      "https://chatgpt.com/?q=" + encodeURIComponent(q),
      "_blank",
      "noopener,noreferrer"
    );
  }

  function handleConnectToCursor() {
    window.open(CURSOR_DEEP_LINK);
  }

  function handleConnectToVSCode() {
    window.open(VSCODE_DEEP_LINK);
  }

  // --- Feedback animations ---

  function showCopied(item) {
    var check = item.querySelector(".pa-check");
    var label = item.querySelector(".pa-item-label");
    var desc = item.querySelector(".pa-item-desc");
    var origLabel = label ? label.innerHTML : "";
    var origDesc = desc ? desc.textContent : "";
    if (check) check.style.opacity = "1";
    if (label) label.textContent = "Copied!";
    if (desc) desc.textContent = "Copy as Markdown";
    setTimeout(function () {
      if (check) check.style.opacity = "0";
      if (label) label.innerHTML = origLabel;
      if (desc) desc.textContent = origDesc;
    }, 1500);
  }

  function showCopyError(item) {
    var label = item.querySelector(".pa-item-label");
    var desc = item.querySelector(".pa-item-desc");
    var origLabel = label ? label.innerHTML : "";
    var origDesc = desc ? desc.textContent : "";
    if (label) label.textContent = "Copy failed";
    if (desc) desc.textContent = "Try again or use Ctrl+C";
    setTimeout(function () {
      if (label) label.innerHTML = origLabel;
      if (desc) desc.textContent = origDesc;
    }, 2000);
  }

  // --- Singleton outside-click handler ---

  var activeDropdown = null;

  document.addEventListener("click", function (e) {
    if (activeDropdown && !activeDropdown.contains(e.target)) {
      var menu = activeDropdown.querySelector(".pa-menu");
      var toggle = activeDropdown.querySelector(".pa-toggle");
      if (menu && !menu.hidden) {
        menu.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        activeDropdown.classList.remove("pa-open");
        activeDropdown = null;
      }
    }
  });

  // --- Dropdown creation ---

  function createDropdown() {
    var container = document.createElement("div");
    container.className = "pa-dropdown";

    // Toggle button
    var menuId = "pa-menu-" + Math.random().toString(36).slice(2, 9);
    var toggle = document.createElement("button");
    toggle.className = "pa-toggle";
    toggle.setAttribute("aria-haspopup", "menu");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", menuId);
    toggle.setAttribute("aria-label", "Page actions");
    toggle.title = "Page actions";
    toggle.innerHTML =
      '<span class="pa-toggle-icon">' + ICONS.copy + "</span>" +
      '<span class="pa-toggle-label">Copy page</span>' +
      CHEVRON;
    container.appendChild(toggle);

    // Menu
    var menu = document.createElement("div");
    menu.className = "pa-menu";
    menu.id = menuId;
    menu.setAttribute("role", "menu");
    menu.hidden = true;
    container.appendChild(menu);

    var actions = [
      {
        id: "copy",
        label: "Copy page",
        desc: "Copy as Markdown",
        icon: ICONS.copy,
        external: false,
      },
      {
        id: "chatgpt",
        label: "Open in ChatGPT",
        desc: "Ask about this page",
        icon: ICONS.chatgpt,
        external: true,
      },
      {
        id: "claude",
        label: "Open in Claude",
        desc: "Ask about this page",
        icon: ICONS.claude,
        external: true,
      },
      {
        id: "cursor",
        label: "Connect to Cursor",
        desc: "Add marimo MCP server",
        icon: ICONS.cursor,
        external: true,
      },
      {
        id: "vscode",
        label: "Connect to VS Code",
        desc: "Add marimo MCP server",
        icon: ICONS.vscode,
        external: true,
      },
    ];

    var items = [];
    actions.forEach(function (action) {
      var btn = document.createElement("button");
      btn.className = "pa-item";
      btn.setAttribute("role", "menuitem");
      btn.setAttribute("tabindex", "-1");
      btn.setAttribute("data-action", action.id);
      btn.innerHTML =
        '<span class="pa-item-icon">' + action.icon + "</span>" +
        '<span class="pa-item-text">' +
          '<span class="pa-item-label">' + action.label +
            (action.external ? ARROW : "") +
          "</span>" +
          '<span class="pa-item-desc">' + action.desc + "</span>" +
        "</span>" +
        CHECK;
      menu.appendChild(btn);
      items.push(btn);
    });

    // --- Event handling ---

    function openMenu() {
      menu.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
      container.classList.add("pa-open");
      activeDropdown = container;
      if (items.length) items[0].focus();
    }

    function closeMenu(restoreFocus) {
      menu.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
      container.classList.remove("pa-open");
      activeDropdown = null;
      if (restoreFocus) toggle.focus();
    }

    function isOpen() {
      return !menu.hidden;
    }

    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      if (isOpen()) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    // Action dispatch
    menu.addEventListener("click", function (e) {
      var item = e.target.closest("[data-action]");
      if (!item) return;
      var action = item.getAttribute("data-action");
      switch (action) {
        case "copy":
          handleCopy(item);
          return; // don't close — show check
        case "claude":
          handleOpenInClaude();
          break;
        case "chatgpt":
          handleOpenInChatGPT();
          break;
        case "cursor":
          handleConnectToCursor();
          break;
        case "vscode":
          handleConnectToVSCode();
          break;
      }
      closeMenu();
    });

    // Keyboard navigation
    container.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        closeMenu(true);
        return;
      }
      if (e.key === "Tab" && isOpen()) {
        closeMenu(false);
        return;
      }
      if (!isOpen()) return;

      var currentIndex = items.indexOf(document.activeElement);
      if (e.key === "ArrowDown") {
        e.preventDefault();
        var next = (currentIndex + 1) % items.length;
        items[next].focus();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        var prev = (currentIndex - 1 + items.length) % items.length;
        items[prev].focus();
      }
    });

    return container;
  }

  // --- Injection ---

  function injectDropdown() {
    var article = document.querySelector("article.md-content__inner");
    if (!article || article.querySelector(".pa-dropdown")) return;
    article.insertBefore(createDropdown(), article.firstChild);
  }

  // --- Lifecycle ---

  function init() {
    injectDropdown();

    // Re-inject after instant navigation replaces content
    var observer = new MutationObserver(function () {
      if (!document.querySelector(".pa-dropdown")) {
        injectDropdown();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
