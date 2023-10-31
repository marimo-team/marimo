/* Copyright 2023 Marimo. All rights reserved. */

import { once } from "@/utils/once";

// Adapted from plotly.js/build/plotcss.js
const rules = {
  "X,X div":
    'direction:ltr;font-family:"Open Sans",verdana,arial,sans-serif;margin:0;padding:0;',
  "X input,X button": 'font-family:"Open Sans",verdana,arial,sans-serif;',
  "X input:focus,X button:focus": "outline:none;",
  "X a": "text-decoration:none;",
  "X a:hover": "text-decoration:none;",
  "X .crisp": "shape-rendering:crispEdges;",
  "X .user-select-none":
    "-webkit-user-select:none;-moz-user-select:none;-ms-user-select:none;-o-user-select:none;user-select:none;",
  "X svg": "overflow:hidden;",
  "X svg a": "fill:#447adb;",
  "X svg a:hover": "fill:#3c6dc5;",
  "X .main-svg": "position:absolute;top:0;left:0;pointer-events:none;",
  "X .main-svg .draglayer": "pointer-events:all;",
  "X .cursor-default": "cursor:default;",
  "X .cursor-pointer": "cursor:pointer;",
  "X .cursor-crosshair": "cursor:crosshair;",
  "X .cursor-move": "cursor:move;",
  "X .cursor-col-resize": "cursor:col-resize;",
  "X .cursor-row-resize": "cursor:row-resize;",
  "X .cursor-ns-resize": "cursor:ns-resize;",
  "X .cursor-ew-resize": "cursor:ew-resize;",
  "X .cursor-sw-resize": "cursor:sw-resize;",
  "X .cursor-s-resize": "cursor:s-resize;",
  "X .cursor-se-resize": "cursor:se-resize;",
  "X .cursor-w-resize": "cursor:w-resize;",
  "X .cursor-e-resize": "cursor:e-resize;",
  "X .cursor-nw-resize": "cursor:nw-resize;",
  "X .cursor-n-resize": "cursor:n-resize;",
  "X .cursor-ne-resize": "cursor:ne-resize;",
  "X .cursor-grab": "cursor:-webkit-grab;cursor:grab;",
  "X .modebar": "position:absolute;top:2px;right:2px;",
  "X .ease-bg":
    "-webkit-transition:background-color .3s ease 0s;-moz-transition:background-color .3s ease 0s;-ms-transition:background-color .3s ease 0s;-o-transition:background-color .3s ease 0s;transition:background-color .3s ease 0s;",
  "X .modebar--hover>:not(.watermark)":
    "opacity:0;-webkit-transition:opacity .3s ease 0s;-moz-transition:opacity .3s ease 0s;-ms-transition:opacity .3s ease 0s;-o-transition:opacity .3s ease 0s;transition:opacity .3s ease 0s;",
  "X:hover .modebar--hover .modebar-group": "opacity:1;",
  // changed - display:inline-block changed to display:flex
  "X .modebar-group":
    "float:left;display:flex;box-sizing:border-box;padding-left:8px;position:relative;vertical-align:middle;white-space:nowrap;",
  "X .modebar-btn":
    "position:relative;font-size:16px;padding:3px 4px;height:22px;cursor:pointer;line-height:normal;box-sizing:border-box;",
  "X .modebar-btn svg": "position:relative;top:2px;",
  // added
  "X .modebar-btn .icon path": "fill:rgba(68, 68, 68, 0.3);",
  // added
  "X .modebar-btn.active .icon path": "fill:rgba(68, 68, 68, 0.7);",
  // added
  "X .modebar-btn:hover .icon path": "fill:rgba(68, 68, 68, 0.7);",
  "X .modebar.vertical":
    "display:flex;flex-direction:column;flex-wrap:wrap;align-content:flex-end;max-height:100%;",
  "X .modebar.vertical svg": "top:-1px;",
  "X .modebar.vertical .modebar-group":
    "display:block;float:none;padding-left:0px;padding-bottom:8px;",
  "X .modebar.vertical .modebar-group .modebar-btn":
    "display:block;text-align:center;",
  "X [data-title]:before,X [data-title]:after":
    "position:absolute;-webkit-transform:translate3d(0, 0, 0);-moz-transform:translate3d(0, 0, 0);-ms-transform:translate3d(0, 0, 0);-o-transform:translate3d(0, 0, 0);transform:translate3d(0, 0, 0);display:none;opacity:0;z-index:1001;pointer-events:none;top:110%;right:50%;",
  "X [data-title]:hover:before,X [data-title]:hover:after":
    "display:block;opacity:1;",
  "X [data-title]:before":
    'content:"";position:absolute;background:rgba(0,0,0,0);border:6px solid rgba(0,0,0,0);z-index:1002;margin-top:-12px;border-bottom-color:#69738a;margin-right:-6px;',
  "X [data-title]:after":
    "content:attr(data-title);background:#69738a;color:#fff;padding:8px 10px;font-size:12px;line-height:12px;white-space:nowrap;margin-right:-18px;border-radius:2px;",
  "X .vertical [data-title]:before,X .vertical [data-title]:after":
    "top:0%;right:200%;",
  "X .vertical [data-title]:before":
    "border:6px solid rgba(0,0,0,0);border-left-color:#69738a;margin-top:8px;margin-right:-30px;",
  Y: 'font-family:"Open Sans",verdana,arial,sans-serif;position:fixed;top:50px;right:20px;z-index:10000;font-size:10pt;max-width:180px;',
  "Y p": "margin:0;",
  "Y .notifier-note":
    "min-width:180px;max-width:250px;border:1px solid #fff;z-index:3000;margin:0;background-color:#8c97af;background-color:rgba(140,151,175,.9);color:#fff;padding:10px;overflow-wrap:break-word;word-wrap:break-word;-ms-hyphens:auto;-webkit-hyphens:auto;hyphens:auto;",
  "Y .notifier-close":
    "color:#fff;opacity:.8;float:right;padding:0 5px;background:none;border:none;font-size:20px;font-weight:bold;line-height:20px;",
  "Y .notifier-close:hover": "color:#444;text-decoration:none;cursor:pointer;",
};

const getCSSStyleSheet = once(() => {
  const sheet = new CSSStyleSheet();
  for (const [selector, rule] of Object.entries(rules)) {
    const fullSelector = selector
      .replace(/^,/, " ,")
      .replaceAll("X", ".js-plotly-plot .plotly")
      .replaceAll("Y", ".plotly-notifier");
    sheet.insertRule(`${fullSelector} { ${rule} }`);
  }
  return sheet;
});

export function addPlotlyCSS(shadowRoot: ShadowRoot) {
  const sheet = getCSSStyleSheet();
  shadowRoot.adoptedStyleSheets = [...shadowRoot.adoptedStyleSheets, sheet];
  return;
}
