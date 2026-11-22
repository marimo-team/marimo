(function () {
  function select(toc, hash) {
    toc.closest(".md-nav--secondary").classList.add("configuration-toc");
    for (const group of toc.children) {
      group.classList.toggle(
        "configuration-active",
        group.querySelector("a").hash === hash,
      );
    }
  }

  // Material supplies the active heading's path and handles scroll/resize tracking.
  component$.subscribe(({ ref, prev }) => {
    if (!ref.matches('[data-md-component="toc"]')) return;
    if (!document.querySelector(".configuration-category")) return;
    select(ref, prev.at(-1)?.at(-1)?.hash);
  });

  target$.subscribe((target) => {
    if (!target.matches(".configuration-category, .configuration-option")) return;
    let category = target;
    while (category && !category.matches(".configuration-category")) {
      category = category.previousElementSibling;
    }
    if (!category) return;
    requestAnimationFrame(() => {
      if (!category.isConnected) return;
      for (const toc of document.querySelectorAll('[data-md-component="toc"]')) {
        select(toc, `#${category.id}`);
      }
    });
  });
})();
