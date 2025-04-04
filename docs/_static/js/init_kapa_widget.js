document.addEventListener("DOMContentLoaded", () => {
  const script = document.createElement("script");
  script.src = "https://widget.kapa.ai/kapa-widget.bundle.js";
  script.setAttribute(
    "data-website-id",
    "d5df1a3e-916b-44ad-a725-e80e490570b2",
  );
  script.setAttribute("data-modal-title", "Ask marimo");
  script.setAttribute("data-project-name", "marimo");
  script.setAttribute("data-project-color", "rgba(28, 115, 98, 0.2)");

  // Alternative logo
  // "https://marimo.io/favicon-32x32.png",
  script.setAttribute("data-project-logo", "https://marimo.io/logo.png");
  script.setAttribute(
    "data-modal-disclaimer",
    "This is a custom LLM for marimo with access to all [documentation](https://docs.marimo.io) and the [API reference](https://docs.marimo.io/api/).",
  );

  // TODO: Add example questions
  // Currently this makes the styling weird
  // script.setAttribute(
  //   "data-modal-example-questions",
  //   "How is marimo different from Jupyter?,How can I run my marimo notebook as a script?",
  // );
  script.setAttribute("data-user-analytics-fingerprint-enabled", "true");

  // Font size parameters
  script.setAttribute("data-font-size-xs", "0.6rem");
  script.setAttribute("data-font-size-sm", "0.7rem");
  script.setAttribute("data-font-size-md", "0.8rem");
  script.setAttribute("data-font-size-lg", "0.9rem");
  script.setAttribute("data-font-size-xl", "1rem");

  // Style parameters
  script.setAttribute(
    "data-modal-title-font-family",
    "var(--md-text-font-family)",
  );

  // Button size
  script.setAttribute("data-button-text", "Ask");
  script.setAttribute("data-button-height", "4rem");
  script.setAttribute("data-button-width", "4rem");
  script.setAttribute("data-button-image-height", "24");
  script.setAttribute("data-button-image-width", "24");

  // Modal size
  script.setAttribute("data-modal-title-font-size", "1rem");
  script.setAttribute("data-modal-header-padding", "12px");
  script.setAttribute("data-modal-body-padding-top", "8px");
  script.setAttribute("data-modal-body-padding-right", "12px");
  script.setAttribute("data-modal-body-padding-left", "12px");
  script.setAttribute("data-modal-body-padding-bottom", "12px");

  // Remove hover animations
  script.setAttribute("data-button-hover-animation-enabled", "false");
  script.setAttribute("data-button-animation-enabled", "false");

  script.async = true;
  document.head.appendChild(script);
});
