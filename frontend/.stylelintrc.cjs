module.exports = {
  extends: ["stylelint-config-standard"],
  ignoreFiles: ["**/*.tsx", "**/*.ts", "dist/**"],
  fix: true,
  reportNeedlessDisables: true,
  rules: {
    // We ideally want these rules to be enabled, but we need to fix a lot
    "selector-class-pattern": null,
    "selector-id-pattern": null,
    "no-descending-specificity": null,
    // Turn off rules from the standard config
    "at-rule-no-unknown": [
      true,
      { ignoreAtRules: ["tailwind", "reference", "config", "theme"] },
    ],
    "font-family-no-missing-generic-family-keyword": null,
    "number-max-precision": null,
    // Force font-size to be in rem
    "unit-allowed-list": [
      [
        // fonts
        "rem",
        // spacing
        "%",
        "vw",
        "vh",
        // time
        "ms",
        "s",
        // grid
        "fr",
        // angle
        "turn",
        "deg",
      ],
      {
        ignoreProperties: {
          px: [
            /border/,
            /radius/,
            /width/,
            /height/,
            /padding/,
            /margin/,
            /gap/,
            /top/,
            /bottom/,
            /left/,
            /right/,
            /shadow/,
            /outline/,
            /clip/,
          ],
        },
      },
    ],
  },
};
