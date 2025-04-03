document.addEventListener("DOMContentLoaded", () => {
  const script = document.createElement("script");
  script.src = "https://widget.kapa.ai/kapa-widget.bundle.js";
  script.setAttribute(
    "data-website-id",
    "d5df1a3e-916b-44ad-a725-e80e490570b2",
  );
  script.setAttribute("data-modal-title", "Ask marimo");
  script.setAttribute("data-project-name", "marimo");
  script.setAttribute("data-project-color", "rgba(28, 115, 98, 0.6)");
  script.setAttribute(
    "data-project-logo",
    "https://marimo.io/favicon-32x32.png",
  );
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
  script.async = true;
  document.head.appendChild(script);
});
