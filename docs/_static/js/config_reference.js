(function () {
  let cleanup = () => {};

  function init() {
    cleanup();
    const categories = [...document.querySelectorAll(".configuration-category")];
    if (!categories.length) return;

    const controller = new AbortController();
    const options = { signal: controller.signal };
    const menus = [...document.querySelectorAll(".md-nav--secondary")];
    const groups = menus.flatMap((menu) => {
      menu.classList.add("configuration-toc");
      return [...menu.querySelectorAll(":scope > ul > li")];
    });

    function select(id) {
      for (const group of groups) {
        const link = group.querySelector("a");
        group.classList.toggle(
          "configuration-active",
          link && new URL(link.href).hash === `#${id}`,
        );
      }
    }

    function update() {
      const header = document.querySelector(".md-header");
      const readingLine = Math.max(
        header?.getBoundingClientRect().bottom ?? 0,
        window.innerHeight * 0.4,
      );
      const current = categories.findLast(
        (heading) => heading.getBoundingClientRect().top <= readingLine,
      );
      select(current?.id);
    }

    let frame;
    window.addEventListener("scroll", () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = undefined;
        update();
      });
    }, { ...options, passive: true });
    window.addEventListener("resize", update, options);
    for (const menu of menus) {
      menu.addEventListener("click", (event) => {
        const link = event.target.closest("a");
        const category = link && categories.find(
          (heading) => new URL(link.href).hash === `#${heading.id}`,
        );
        if (category) select(category.id);
      }, options);
    }
    update();
    cleanup = () => {
      controller.abort();
      cancelAnimationFrame(frame);
    };
  }

  if (typeof document$ !== "undefined") {
    document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
