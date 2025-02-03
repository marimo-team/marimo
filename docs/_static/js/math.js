(() => {
  const renderMath = (element) => {
    const tex = element.textContent || element.innerHTML;
    if (tex.startsWith("\\(") && tex.endsWith("\\)")) {
      katex.render(tex.slice(2, -2), element, { displayMode: false });
    } else if (tex.startsWith("\\[") && tex.endsWith("\\]")) {
      katex.render(tex.slice(2, -2), element, { displayMode: true });
    }
  };

  const renderAllMath = () => {
    const maths = document.querySelectorAll(
      ".arithmatex:not([data-processed])",
    );
    maths.forEach((element) => {
      try {
        renderMath(element);
        element.setAttribute("data-processed", "true");
      } catch (error) {
        console.warn("Failed to render math:", error);
      }
    });
  };

  // Watch for new content
  const observer = new MutationObserver((mutations) => {
    const shouldRender = mutations.some((mutation) => {
      return mutation.addedNodes.length > 0;
    });
    if (shouldRender) {
      renderAllMath();
    }
  });

  const init = () => {
    if (typeof katex === "undefined") {
      console.warn("KaTeX not loaded");
      return;
    }

    renderAllMath();
    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
