# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.4.0"
app = marimo.App()


@app.cell
def __(css):
    import anywidget
    import marimo as mo


    class IGVWidget(anywidget.AnyWidget):
        _esm = """
        import igv from "https://cdn.jsdelivr.net/npm/igv@2.15.5/dist/igv.esm.min.js"

        function render({ model, el }) {
          var options = {
            genome: "hg38",
            locus: "chr8:127,736,588-127,739,371",
            tracks: [{
              "name": "HG00103",
              "url": "https://s3.amazonaws.com/1000genomes/data/HG00103/alignment/HG00103.alt_bwamem_GRCh38DH.20150718.GBR.low_coverage.cram",
              "indexURL": "https://s3.amazonaws.com/1000genomes/data/HG00103/alignment/HG00103.alt_bwamem_GRCh38DH.20150718.GBR.low_coverage.cram.crai",
              "format": "cram"
            }]};

            igv.createBrowser(el, options)
        }
        export default { render };
      """

        _css = ".igv-container {background-color: white};" + css


    IGVWidget()
    return IGVWidget, anywidget, mo


@app.cell
def __():
    css = """
    .igv-navbar {
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-between;
      align-items: center;
      box-sizing: border-box;
      width: 100%;
      color: #444;
      font-size: 12px;
      font-family: "Open Sans", sans-serif;
      font-weight: 400;
      line-height: 32px;
      padding-left: 8px;
      padding-right: 8px;
      margin-top: 2px;
      margin-bottom: 6px;
      height: 32px;
      border-style: solid;
      border-radius: 3px;
      border-width: thin;
      border-color: #bfbfbf;
      background-color: #f3f3f3;
    }
    .igv-navbar .igv-navbar-left-container {
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-between;
      align-items: center;
      height: 32px;
      line-height: 32px;
    }
    .igv-navbar .igv-navbar-left-container .igv-logo {
      width: 34px;
      height: 32px;
      margin-right: 8px;
    }
    .igv-navbar .igv-navbar-left-container .igv-current-genome {
      height: 32px;
      margin-left: 4px;
      margin-right: 4px;
      user-select: none;
      line-height: 32px;
      vertical-align: middle;
      text-align: center;
    }
    .igv-navbar .igv-navbar-left-container .igv-navbar-genomic-location {
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-between;
      align-items: center;
      height: 100%;
    }
    .igv-navbar .igv-navbar-left-container .igv-navbar-genomic-location .igv-chromosome-select-widget-container {
      display: flex;
      flex-flow: column;
      flex-wrap: nowrap;
      justify-content: space-around;
      align-items: center;
      height: 100%;
      width: 125px;
      margin-right: 4px;
    }
    .igv-navbar .igv-navbar-left-container .igv-navbar-genomic-location .igv-chromosome-select-widget-container select {
      display: block;
      cursor: pointer;
      width: 100px;
      height: 75%;
      outline: none;
      font-size: 12px;
      font-family: "Open Sans", sans-serif;
      font-weight: 400;
    }
    .igv-navbar .igv-navbar-left-container .igv-navbar-genomic-location .igv-locus-size-group {
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-between;
      align-items: center;
      margin-left: 8px;
      height: 22px;
    }
    .igv-navbar .igv-navbar-left-container .igv-navbar-genomic-location .igv-locus-size-group .igv-search-container {
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: center;
      width: 210px;
      height: 22px;
      line-height: 22px;
    }
    .igv-navbar .igv-navbar-left-container .igv-navbar-genomic-location .igv-locus-size-group .igv-search-container input.igv-search-input {
      cursor: text;
      width: 85%;
      height: 22px;
      line-height: 22px;
      font-size: 12px;
      font-family: "Open Sans", sans-serif;
      font-weight: 400;
      text-align: left;
      padding-left: 8px;
      margin-right: 8px;
      outline: none;
      border-style: solid;
      border-radius: 3px;
      border-width: thin;
      border-color: #bfbfbf;
      background-color: white;
    }
    .igv-navbar .igv-navbar-left-container .igv-navbar-genomic-location .igv-locus-size-group .igv-search-container .igv-search-icon-container {
      cursor: pointer;
      height: 16px;
      width: 16px;
    }
    .igv-navbar .igv-navbar-left-container .igv-navbar-genomic-location .igv-locus-size-group .igv-windowsize-panel-container {
      margin-left: 4px;
      user-select: none;
    }
    .igv-navbar .igv-navbar-right-container {
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-between;
      align-items: center;
      height: 32px;
      line-height: 32px;
    }
    .igv-navbar .igv-navbar-right-container .igv-navbar-toggle-button-container {
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-between;
      align-items: center;
      height: 100%;
    }
    .igv-navbar .igv-navbar-right-container .igv-navbar-toggle-button-container div {
      margin-left: 0;
      margin-right: 4px;
    }
    .igv-navbar .igv-navbar-right-container .igv-navbar-toggle-button-container div:last-child {
      margin-left: 0;
      margin-right: 0;
    }
    .igv-navbar .igv-navbar-right-container .igv-navbar-toggle-button-container-750 {
      display: none;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget {
      color: #737373;
      font-size: 18px;
      height: 32px;
      line-height: 32px;
      margin-left: 8px;
      user-select: none;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-end;
      align-items: center;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget div {
      cursor: pointer;
      margin-left: unset;
      margin-right: unset;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget div:first-child {
      height: 24px;
      width: 24px;
      margin-left: unset;
      margin-right: 8px;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget div:last-child {
      height: 24px;
      width: 24px;
      margin-left: 8px;
      margin-right: unset;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget div:nth-child(even) {
      display: block;
      height: fit-content;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget input {
      display: block;
      width: 125px;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget svg {
      display: block;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget-900 {
      color: #737373;
      font-size: 18px;
      height: 32px;
      line-height: 32px;
      margin-left: 8px;
      user-select: none;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-end;
      align-items: center;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget-900 div {
      cursor: pointer;
      margin-left: unset;
      margin-right: unset;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget-900 div:first-child {
      height: 24px;
      width: 24px;
      margin-left: unset;
      margin-right: 8px;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget-900 div:last-child {
      height: 24px;
      width: 24px;
      margin-left: 8px;
      margin-right: unset;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget-900 div:nth-child(even) {
      width: 0;
      height: 0;
      display: none;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget-900 input {
      width: 0;
      height: 0;
      display: none;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget-900 svg {
      display: block;
    }
    .igv-navbar .igv-navbar-right-container .igv-zoom-widget-hidden {
      display: none;
    }

    .igv-navbar-button {
      display: block;
      box-sizing: unset;
      padding-left: 6px;
      padding-right: 6px;
      height: 18px;
      text-transform: capitalize;
      user-select: none;
      line-height: 18px;
      text-align: center;
      vertical-align: middle;
      font-family: "Open Sans", sans-serif;
      font-size: 11px;
      font-weight: 200;
      color: #737373;
      background-color: #f3f3f3;
      border-color: #737373;
      border-style: solid;
      border-width: thin;
      border-radius: 6px;
    }

    .igv-navbar-button-clicked {
      color: white;
      background-color: #737373;
    }

    .igv-navbar-button:hover {
      cursor: pointer;
    }

    .igv-zoom-in-notice-container {
      z-index: 1024;
      position: absolute;
      top: 8px;
      left: 50%;
      transform: translate(-50%, 0%);
      display: flex;
      flex-direction: row;
      flex-wrap: nowrap;
      justify-content: center;
      align-items: center;
      background-color: white;
    }
    .igv-zoom-in-notice-container > div {
      padding-left: 4px;
      padding-right: 4px;
      padding-top: 2px;
      padding-bottom: 2px;
      width: 100%;
      height: 100%;
      font-family: "Open Sans", sans-serif;
      font-size: 14px;
      font-weight: 400;
      color: #3f3f3f;
    }

    .igv-zoom-in-notice {
      position: absolute;
      top: 10px;
      left: 50%;
    }
    .igv-zoom-in-notice div {
      position: relative;
      left: -50%;
      font-family: "Open Sans", sans-serif;
      font-size: medium;
      font-weight: 400;
      color: #3f3f3f;
      background-color: rgba(255, 255, 255, 0.51);
      z-index: 64;
    }

    .igv-container-spinner {
      position: absolute;
      top: 90%;
      left: 50%;
      transform: translate(-50%, -50%);
      z-index: 1024;
      width: 24px;
      height: 24px;
      pointer-events: none;
      color: #737373;
    }

    .igv-multi-locus-close-button {
      position: absolute;
      top: 2px;
      right: 0;
      padding-left: 2px;
      padding-right: 2px;
      width: 12px;
      height: 12px;
      color: #666666;
      background-color: white;
      z-index: 1000;
    }
    .igv-multi-locus-close-button > svg {
      vertical-align: top;
    }

    .igv-multi-locus-close-button:hover {
      cursor: pointer;
      color: #434343;
    }

    .igv-multi-locus-ruler-label {
      z-index: 64;
      position: absolute;
      top: 2px;
      left: 0;
      width: 100%;
      height: 12px;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: center;
      align-items: center;
    }
    .igv-multi-locus-ruler-label > div {
      font-family: "Open Sans", sans-serif;
      font-size: 12px;
      color: rgb(16, 16, 16);
      background-color: white;
    }
    .igv-multi-locus-ruler-label > div {
      cursor: pointer;
    }

    .igv-multi-locus-ruler-label-square-dot {
      z-index: 64;
      position: absolute;
      left: 50%;
      top: 5%;
      transform: translate(-50%, 0%);
      background-color: white;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: center;
    }
    .igv-multi-locus-ruler-label-square-dot > div:first-child {
      width: 14px;
      height: 14px;
    }
    .igv-multi-locus-ruler-label-square-dot > div:last-child {
      margin-left: 16px;
      font-family: "Open Sans", sans-serif;
      font-size: 14px;
      font-weight: 400;
      color: rgb(16, 16, 16);
    }

    .igv-ruler-sweeper {
      display: none;
      pointer-events: none;
      position: absolute;
      top: 26px;
      bottom: 0;
      left: 0;
      width: 0;
      z-index: 99999;
      background-color: rgba(68, 134, 247, 0.25);
    }

    .igv-ruler-tooltip {
      pointer-events: none;
      z-index: 128;
      position: absolute;
      top: 0;
      left: 0;
      width: 1px;
      height: 32px;
      background-color: transparent;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: center;
    }
    .igv-ruler-tooltip > div {
      pointer-events: none;
      width: 128px;
      height: auto;
      padding: 1px;
      color: #373737;
      font-size: 10px;
      font-family: "Open Sans", sans-serif;
      font-weight: 400;
      background-color: white;
      border-style: solid;
      border-width: thin;
      border-color: #373737;
    }

    .igv-track-label {
      position: absolute;
      left: 8px;
      top: 8px;
      width: auto;
      height: auto;
      max-width: 50%;
      padding-left: 4px;
      padding-right: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      font-family: "Open Sans", sans-serif;
      font-size: small;
      font-weight: 400;
      text-align: center;
      user-select: none;
      -moz-user-select: none;
      -webkit-user-select: none;
      border-color: #444;
      border-radius: 2px;
      border-style: solid;
      border-width: thin;
      background-color: white;
      z-index: 128;
      cursor: pointer;
    }

    .igv-track-label:hover,
    .igv-track-label:focus,
    .igv-track-label:active {
      background-color: #e8e8e8;
    }

    .igv-track-label-popup-shim {
      padding-left: 8px;
      padding-right: 8px;
      padding-top: 4px;
    }

    .igv-center-line {
      display: none;
      pointer-events: none;
      position: absolute;
      top: 0;
      bottom: 0;
      left: 50%;
      transform: translateX(-50%);
      z-index: 8;
      user-select: none;
      -moz-user-select: none;
      -webkit-user-select: none;
      border-left-style: dashed;
      border-left-width: thin;
      border-right-style: dashed;
      border-right-width: thin;
    }

    .igv-center-line-wide {
      background-color: rgba(0, 0, 0, 0);
      border-left-color: rgba(127, 127, 127, 0.51);
      border-right-color: rgba(127, 127, 127, 0.51);
    }

    .igv-center-line-thin {
      background-color: rgba(0, 0, 0, 0);
      border-left-color: rgba(127, 127, 127, 0.51);
      border-right-color: rgba(0, 0, 0, 0);
    }

    .igv-cursor-guide-horizontal {
      display: none;
      pointer-events: none;
      user-select: none;
      -moz-user-select: none;
      -webkit-user-select: none;
      position: absolute;
      left: 0;
      right: 0;
      top: 50%;
      height: 1px;
      z-index: 1;
      margin-left: 50px;
      margin-right: 54px;
      border-top-style: dotted;
      border-top-width: thin;
      border-top-color: rgba(127, 127, 127, 0.76);
    }

    .igv-cursor-guide-vertical {
      pointer-events: none;
      user-select: none;
      -moz-user-select: none;
      -webkit-user-select: none;
      position: absolute;
      top: 0;
      bottom: 0;
      left: 50%;
      width: 1px;
      z-index: 1;
      border-left-style: dotted;
      border-left-width: thin;
      border-left-color: rgba(127, 127, 127, 0.76);
      display: none;
    }

    .igv-user-feedback {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 512px;
      height: 360px;
      z-index: 2048;
      background-color: white;
      border-color: #a2a2a2;
      border-style: solid;
      border-width: thin;
      font-family: "Open Sans", sans-serif;
      font-size: medium;
      font-weight: 400;
      color: #444;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: center;
    }
    .igv-user-feedback div:first-child {
      position: relative;
      height: 24px;
      width: 100%;
      background-color: white;
      border-bottom-color: #a2a2a2;
      border-bottom-style: solid;
      border-bottom-width: thin;
    }
    .igv-user-feedback div:first-child div {
      position: absolute;
      top: 2px;
      width: 16px;
      height: 16px;
      background-color: transparent;
    }
    .igv-user-feedback div:first-child div:first-child {
      left: 8px;
    }
    .igv-user-feedback div:first-child div:last-child {
      cursor: pointer;
      right: 8px;
    }
    .igv-user-feedback div:last-child {
      width: 100%;
      height: calc(100% - 24px);
      border-width: 0;
    }
    .igv-user-feedback div:last-child div {
      width: auto;
      height: auto;
      margin: 8px;
    }

    .igv-generic-dialog-container {
      position: absolute;
      top: 0;
      left: 0;
      width: 300px;
      height: 200px;
      border-color: #7F7F7F;
      border-radius: 4px;
      border-style: solid;
      border-width: thin;
      font-family: "Open Sans", sans-serif;
      font-size: medium;
      font-weight: 400;
      z-index: 2048;
      background-color: white;
      display: flex;
      flex-flow: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: center;
    }
    .igv-generic-dialog-container .igv-generic-dialog-header {
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-end;
      align-items: center;
      width: 100%;
      height: 24px;
      cursor: move;
      border-top-left-radius: 4px;
      border-top-right-radius: 4px;
      border-bottom-color: #7F7F7F;
      border-bottom-style: solid;
      border-bottom-width: thin;
      background-color: #eee;
    }
    .igv-generic-dialog-container .igv-generic-dialog-header div {
      margin-right: 4px;
      margin-bottom: 2px;
      height: 12px;
      width: 12px;
      color: #7F7F7F;
    }
    .igv-generic-dialog-container .igv-generic-dialog-header div:hover {
      cursor: pointer;
      color: #444;
    }
    .igv-generic-dialog-container .igv-generic-dialog-one-liner {
      color: #373737;
      width: 95%;
      height: 24px;
      line-height: 24px;
      text-align: left;
      margin-top: 8px;
      padding-left: 8px;
      overflow-wrap: break-word;
      background-color: white;
    }
    .igv-generic-dialog-container .igv-generic-dialog-label-input {
      margin-top: 8px;
      width: 95%;
      height: 24px;
      color: #373737;
      line-height: 24px;
      padding-left: 8px;
      background-color: white;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: center;
    }
    .igv-generic-dialog-container .igv-generic-dialog-label-input div {
      width: 30%;
      height: 100%;
      font-size: 16px;
      text-align: right;
      padding-right: 8px;
      background-color: white;
    }
    .igv-generic-dialog-container .igv-generic-dialog-label-input input {
      display: block;
      height: 100%;
      width: 100%;
      padding-left: 4px;
      font-family: "Open Sans", sans-serif;
      font-weight: 400;
      color: #373737;
      text-align: left;
      outline: none;
      border-style: solid;
      border-width: thin;
      border-color: #7F7F7F;
      background-color: white;
    }
    .igv-generic-dialog-container .igv-generic-dialog-label-input input {
      width: 50%;
      font-size: 16px;
    }
    .igv-generic-dialog-container .igv-generic-dialog-input {
      margin-top: 8px;
      width: calc(100% - 16px);
      height: 24px;
      color: #373737;
      line-height: 24px;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-around;
      align-items: center;
    }
    .igv-generic-dialog-container .igv-generic-dialog-input input {
      display: block;
      height: 100%;
      width: 100%;
      padding-left: 4px;
      font-family: "Open Sans", sans-serif;
      font-weight: 400;
      color: #373737;
      text-align: left;
      outline: none;
      border-style: solid;
      border-width: thin;
      border-color: #7F7F7F;
      background-color: white;
    }
    .igv-generic-dialog-container .igv-generic-dialog-input input {
      font-size: 16px;
    }
    .igv-generic-dialog-container .igv-generic-dialog-ok-cancel {
      width: 100%;
      height: 28px;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-around;
      align-items: center;
    }
    .igv-generic-dialog-container .igv-generic-dialog-ok-cancel div {
      margin-top: 32px;
      color: white;
      font-family: "Open Sans", sans-serif;
      font-size: 14px;
      font-weight: 400;
      width: 75px;
      height: 28px;
      line-height: 28px;
      text-align: center;
      border-color: transparent;
      border-style: solid;
      border-width: thin;
      border-radius: 2px;
    }
    .igv-generic-dialog-container .igv-generic-dialog-ok-cancel div:first-child {
      margin-left: 32px;
      margin-right: 0;
      background-color: #5ea4e0;
    }
    .igv-generic-dialog-container .igv-generic-dialog-ok-cancel div:last-child {
      margin-left: 0;
      margin-right: 32px;
      background-color: #c4c4c4;
    }
    .igv-generic-dialog-container .igv-generic-dialog-ok-cancel div:first-child:hover {
      cursor: pointer;
      background-color: #3b5c7f;
    }
    .igv-generic-dialog-container .igv-generic-dialog-ok-cancel div:last-child:hover {
      cursor: pointer;
      background-color: #7f7f7f;
    }
    .igv-generic-dialog-container .igv-generic-dialog-ok {
      width: 100%;
      height: 36px;
      margin-top: 32px;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-around;
      align-items: center;
    }
    .igv-generic-dialog-container .igv-generic-dialog-ok div {
      width: 98px;
      height: 36px;
      line-height: 36px;
      text-align: center;
      color: white;
      font-family: "Open Sans", sans-serif;
      font-size: medium;
      font-weight: 400;
      border-color: white;
      border-style: solid;
      border-width: thin;
      border-radius: 4px;
      background-color: #2B81AF;
    }
    .igv-generic-dialog-container .igv-generic-dialog-ok div:hover {
      cursor: pointer;
      background-color: #25597f;
    }

    .igv-generic-container {
      position: absolute;
      top: 0;
      left: 0;
      z-index: 2048;
      background-color: white;
      cursor: pointer;
      display: flex;
      flex-direction: row;
      flex-wrap: wrap;
      justify-content: flex-start;
      align-items: center;
    }
    .igv-generic-container div:first-child {
      cursor: move;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-end;
      align-items: center;
      height: 24px;
      width: 100%;
      background-color: #dddddd;
    }
    .igv-generic-container div:first-child i {
      display: block;
      color: #5f5f5f;
      cursor: pointer;
      width: 14px;
      height: 14px;
      margin-right: 8px;
      margin-bottom: 4px;
    }

    .igv-menu-popup {
      position: absolute;
      top: 0;
      left: 0;
      width: max-content;
      z-index: 4096;
      cursor: pointer;
      font-family: "Open Sans", sans-serif;
      font-size: small;
      font-weight: 400;
      color: #4b4b4b;
      background: white;
      border-radius: 4px;
      border-color: #7F7F7F;
      border-style: solid;
      border-width: thin;
      display: flex;
      flex-flow: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: flex-end;
      text-align: left;
    }
    .igv-menu-popup > div:not(:first-child) {
      width: 100%;
    }
    .igv-menu-popup > div:not(:first-child) > div {
      background: white;
    }
    .igv-menu-popup > div:not(:first-child) > div.context-menu {
      padding-left: 4px;
      padding-right: 4px;
    }
    .igv-menu-popup > div:not(:first-child) > div:last-child {
      border-bottom-left-radius: 4px;
      border-bottom-right-radius: 4px;
      border-bottom-color: transparent;
      border-bottom-style: solid;
      border-bottom-width: thin;
    }
    .igv-menu-popup > div:not(:first-child) > div:hover {
      background: #efefef;
    }

    .igv-menu-popup-shim {
      padding-left: 8px;
      padding-right: 8px;
      padding-bottom: 1px;
      padding-top: 1px;
    }

    .igv-menu-popup-header {
      position: relative;
      width: 100%;
      height: 24px;
      cursor: move;
      border-top-color: transparent;
      border-top-left-radius: 4px;
      border-top-right-radius: 4px;
      border-bottom-color: #7F7F7F;
      border-bottom-style: solid;
      border-bottom-width: thin;
      background-color: #eee;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-end;
      align-items: center;
    }
    .igv-menu-popup-header div {
      margin-right: 4px;
      height: 12px;
      width: 12px;
      color: #7F7F7F;
    }
    .igv-menu-popup-header div:hover {
      cursor: pointer;
      color: #444;
    }

    .igv-menu-popup-check-container {
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: center;
      width: 100%;
      height: 20px;
      margin-right: 4px;
      background-color: transparent;
    }
    .igv-menu-popup-check-container div {
      padding-top: 2px;
      padding-left: 8px;
    }
    .igv-menu-popup-check-container div:first-child {
      position: relative;
      width: 12px;
      height: 12px;
    }
    .igv-menu-popup-check-container div:first-child svg {
      position: absolute;
      width: 12px;
      height: 12px;
    }

    .igv-user-feedback {
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 512px;
      height: 360px;
      z-index: 2048;
      background-color: white;
      border-color: #a2a2a2;
      border-style: solid;
      border-width: thin;
      font-family: "Open Sans", sans-serif;
      font-size: medium;
      font-weight: 400;
      color: #444;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: center;
    }
    .igv-user-feedback div:first-child {
      position: relative;
      height: 24px;
      width: 100%;
      background-color: white;
      border-bottom-color: #a2a2a2;
      border-bottom-style: solid;
      border-bottom-width: thin;
    }
    .igv-user-feedback div:first-child div {
      position: absolute;
      top: 2px;
      width: 16px;
      height: 16px;
      background-color: transparent;
    }
    .igv-user-feedback div:first-child div:first-child {
      left: 8px;
    }
    .igv-user-feedback div:first-child div:last-child {
      cursor: pointer;
      right: 8px;
    }
    .igv-user-feedback div:last-child {
      width: 100%;
      height: calc(100% - 24px);
      border-width: 0;
    }
    .igv-user-feedback div:last-child div {
      width: auto;
      height: auto;
      margin: 8px;
    }

    .igv-loading-spinner-container {
      z-index: 1024;
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 32px;
      height: 32px;
      display: flex;
      flex-direction: row;
      flex-wrap: nowrap;
      justify-content: center;
      align-items: center;
    }
    .igv-loading-spinner-container > div {
      box-sizing: border-box;
      width: 100%;
      height: 100%;
      border-radius: 50%;
      border: 4px solid rgba(128, 128, 128, 0.5);
      border-top-color: rgb(255, 255, 255);
      animation: spin 1s ease-in-out infinite;
      -webkit-animation: spin 1s ease-in-out infinite;
    }

    @keyframes spin {
      to {
        -webkit-transform: rotate(360deg);
        transform: rotate(360deg);
      }
    }
    @-webkit-keyframes spin {
      to {
        -webkit-transform: rotate(360deg);
        transform: rotate(360deg);
      }
    }
    .igv-roi-menu-next-gen {
      position: absolute;
      z-index: 512;
      font-family: "Open Sans", sans-serif;
      font-size: small;
      font-weight: 400;
      color: #4b4b4b;
      background-color: white;
      width: 192px;
      border-radius: 4px;
      border-color: #7F7F7F;
      border-style: solid;
      border-width: thin;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: stretch;
    }
    .igv-roi-menu-next-gen > div:first-child {
      height: 24px;
      border-top-color: transparent;
      border-top-left-radius: 4px;
      border-top-right-radius: 4px;
      border-bottom-color: #7F7F7F;
      border-bottom-style: solid;
      border-bottom-width: thin;
      background-color: #eee;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: flex-end;
      align-items: center;
    }
    .igv-roi-menu-next-gen > div:first-child > div {
      margin-right: 4px;
      height: 12px;
      width: 12px;
      color: #7F7F7F;
    }
    .igv-roi-menu-next-gen > div:first-child > div:hover {
      cursor: pointer;
      color: #444;
    }
    .igv-roi-menu-next-gen > div:last-child {
      background-color: white;
      border-bottom-left-radius: 4px;
      border-bottom-right-radius: 4px;
      border-bottom-color: transparent;
      border-bottom-style: solid;
      border-bottom-width: 0;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: stretch;
      text-align: start;
      vertical-align: middle;
    }
    .igv-roi-menu-next-gen > div:last-child > div {
      height: 24px;
      padding-left: 4px;
      border-bottom-style: solid;
      border-bottom-width: thin;
      border-bottom-color: #7f7f7f;
    }
    .igv-roi-menu-next-gen > div:last-child > div:not(:first-child):hover {
      background-color: rgba(127, 127, 127, 0.1);
    }
    .igv-roi-menu-next-gen > div:last-child div:first-child {
      font-style: italic;
      text-align: center;
      padding-right: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .igv-roi-menu-next-gen > div:last-child > div:last-child {
      border-bottom-width: 0;
      border-bottom-color: transparent;
    }

    .igv-roi-placeholder {
      font-style: normal;
      color: rgba(75, 75, 75, 0.6);
    }

    .igv-roi-table {
      position: absolute;
      z-index: 1024;
      width: min-content;
      max-width: 1600px;
      border-color: #7f7f7f;
      border-radius: 4px;
      border-style: solid;
      border-width: thin;
      font-family: "Open Sans", sans-serif;
      font-size: 12px;
      font-weight: 400;
      background-color: white;
      display: flex;
      flex-flow: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: stretch;
      cursor: default;
    }
    .igv-roi-table > div {
      height: 24px;
      font-size: 14px;
      text-align: start;
      vertical-align: middle;
      line-height: 24px;
    }
    .igv-roi-table > div:first-child {
      border-color: transparent;
      border-top-left-radius: 4px;
      border-top-right-radius: 4px;
      border-top-width: 0;
      border-bottom-color: #7f7f7f;
      border-bottom-style: solid;
      border-bottom-width: thin;
      background-color: #eee;
      cursor: move;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-between;
      align-items: center;
    }
    .igv-roi-table > div:first-child > div:first-child {
      text-align: center;
      white-space: nowrap;
      text-overflow: ellipsis;
      overflow: hidden;
      margin-left: 4px;
      margin-right: 4px;
      width: calc(100% - 4px - 12px);
    }
    .igv-roi-table > div:first-child > div:last-child {
      margin-right: 4px;
      margin-bottom: 2px;
      height: 12px;
      width: 12px;
      color: #7f7f7f;
    }
    .igv-roi-table > div:first-child > div:last-child > svg {
      display: block;
    }
    .igv-roi-table > div:first-child > div:last-child:hover {
      cursor: pointer;
      color: #444;
    }
    .igv-roi-table > .igv-roi-table-description {
      padding: 4px;
      margin-left: 4px;
      word-break: break-all;
      overflow-y: auto;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      background-color: transparent;
    }
    .igv-roi-table > .igv-roi-table-goto-explainer {
      margin-top: 5px;
      margin-left: 4px;
      color: #7F7F7F;
      font-style: italic;
      height: 24px;
      border-top: solid lightgray;
      background-color: transparent;
    }
    .igv-roi-table > .igv-roi-table-column-titles {
      height: 24px;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: stretch;
      align-items: stretch;
      padding-right: 16px;
      background-color: white;
      border-top-color: #7f7f7f;
      border-top-style: solid;
      border-top-width: thin;
      border-bottom-color: #7f7f7f;
      border-bottom-style: solid;
      border-bottom-width: thin;
    }
    .igv-roi-table > .igv-roi-table-column-titles > div {
      font-size: 14px;
      vertical-align: middle;
      line-height: 24px;
      text-align: left;
      margin-left: 4px;
      height: 24px;
      overflow: hidden;
      text-overflow: ellipsis;
      border-right-color: #7f7f7f;
      border-right-style: solid;
      border-right-width: thin;
    }
    .igv-roi-table > .igv-roi-table-column-titles > div:last-child {
      border-right: unset;
    }
    .igv-roi-table > .igv-roi-table-row-container {
      overflow: auto;
      resize: both;
      max-width: 1600px;
      height: 360px;
      background-color: transparent;
      display: flex;
      flex-flow: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: stretch;
    }
    .igv-roi-table > .igv-roi-table-row-container > .igv-roi-table-row {
      height: 24px;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: stretch;
      align-items: stretch;
    }
    .igv-roi-table > .igv-roi-table-row-container > .igv-roi-table-row > div {
      font-size: 14px;
      vertical-align: middle;
      line-height: 24px;
      text-align: left;
      margin-left: 4px;
      height: 24px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      border-right-color: transparent;
      border-right-style: solid;
      border-right-width: thin;
    }
    .igv-roi-table > .igv-roi-table-row-container > .igv-roi-table-row > div:last-child {
      border-right: unset;
    }
    .igv-roi-table > .igv-roi-table-row-container > .igv-roi-table-row-hover {
      background-color: rgba(0, 0, 0, 0.04);
    }
    .igv-roi-table > div:last-child {
      height: 32px;
      line-height: 32px;
      border-top-color: #7f7f7f;
      border-top-style: solid;
      border-top-width: thin;
      border-bottom-color: transparent;
      border-bottom-left-radius: 4px;
      border-bottom-right-radius: 4px;
      border-bottom-width: 0;
      background-color: #eee;
      display: flex;
      flex-flow: row;
      flex-wrap: nowrap;
      justify-content: space-around;
      align-items: center;
    }

    .igv-roi-table-row-selected {
      background-color: rgba(0, 0, 0, 0.125);
    }

    .igv-roi-table-button {
      cursor: pointer;
      height: 20px;
      user-select: none;
      line-height: 20px;
      text-align: center;
      vertical-align: middle;
      font-family: "Open Sans", sans-serif;
      font-size: 13px;
      font-weight: 400;
      color: black;
      padding-left: 6px;
      padding-right: 6px;
      background-color: rgb(239, 239, 239);
      border-color: black;
      border-style: solid;
      border-width: thin;
      border-radius: 3px;
    }

    .igv-roi-table-button:hover {
      font-weight: 400;
      background-color: rgba(0, 0, 0, 0.13);
    }

    .igv-roi-region {
      z-index: 64;
      position: absolute;
      top: 0;
      bottom: 0;
      pointer-events: none;
      overflow: visible;
      margin-top: 44px;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: stretch;
    }
    .igv-roi-region > div {
      position: relative;
      width: 100%;
      height: 8px;
      pointer-events: auto;
    }

    .igv-roi-menu {
      position: absolute;
      z-index: 1024;
      width: 144px;
      border-color: #7f7f7f;
      border-radius: 4px;
      border-style: solid;
      border-width: thin;
      font-family: "Open Sans", sans-serif;
      background-color: white;
      display: flex;
      flex-flow: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: stretch;
    }
    .igv-roi-menu > div:not(:last-child) {
      border-bottom-color: rgba(128, 128, 128, 0.5);
      border-bottom-style: solid;
      border-bottom-width: thin;
    }
    .igv-roi-menu > div:first-child {
      border-top-left-radius: 4px;
      border-top-right-radius: 4px;
      border-top-color: transparent;
      border-top-style: solid;
      border-top-width: 0;
    }
    .igv-roi-menu > div:last-child {
      border-bottom-left-radius: 4px;
      border-bottom-right-radius: 4px;
      border-bottom-color: transparent;
      border-bottom-style: solid;
      border-bottom-width: 0;
    }

    .igv-roi-menu-row {
      height: 24px;
      padding-left: 8px;
      font-size: small;
      text-align: start;
      vertical-align: middle;
      line-height: 24px;
      background-color: white;
    }

    .igv-roi-menu-row-edit-description {
      width: -webkit-fill-available;
      font-size: small;
      text-align: start;
      vertical-align: middle;
      background-color: white;
      padding-left: 4px;
      padding-right: 4px;
      padding-bottom: 4px;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: stretch;
      align-items: stretch;
    }
    .igv-roi-menu-row-edit-description > label {
      margin-left: 2px;
      margin-bottom: 0;
      display: block;
      width: -webkit-fill-available;
    }
    .igv-roi-menu-row-edit-description > input {
      display: block;
      margin-left: 2px;
      margin-right: 2px;
      margin-bottom: 1px;
      width: -webkit-fill-available;
    }

    .igv-container {
      position: relative;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: flex-start;
      padding-top: 4px;
      user-select: none;
      -webkit-user-select: none;
      -ms-user-select: none;
    }

    .igv-viewport {
      position: relative;
      margin-top: 5px;
      line-height: 1;
      overflow-x: hidden;
      overflow-y: hidden;
    }

    .igv-viewport-content {
      position: relative;
      width: 100%;
    }
    .igv-viewport-content > canvas {
      position: relative;
      display: block;
    }

    .igv-column-container {
      position: relative;
      display: flex;
      flex-direction: row;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: stretch;
      width: 100%;
    }

    .igv-column-shim {
      width: 1px;
      margin-left: 2px;
      margin-right: 2px;
      background-color: #545453;
    }

    .igv-column {
      position: relative;
      position: relative;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: flex-start;
      box-sizing: border-box;
      height: 100%;
    }

    .igv-axis-column {
      position: relative;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: flex-start;
      box-sizing: border-box;
      height: 100%;
      width: 50px;
    }
    .igv-axis-column > div {
      margin-top: 5px;
      width: 100%;
    }

    .igv-sample-name-column {
      position: relative;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: flex-start;
      box-sizing: border-box;
      height: 100%;
    }

    .igv-scrollbar-column {
      position: relative;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: flex-start;
      box-sizing: border-box;
      height: 100%;
      width: 14px;
    }
    .igv-scrollbar-column > div {
      position: relative;
      margin-top: 5px;
      width: 14px;
    }
    .igv-scrollbar-column > div > div {
      cursor: pointer;
      position: absolute;
      top: 0;
      left: 2px;
      width: 8px;
      border-width: 1px;
      border-style: solid;
      border-color: #c4c4c4;
      border-top-left-radius: 4px;
      border-top-right-radius: 4px;
      border-bottom-left-radius: 4px;
      border-bottom-right-radius: 4px;
    }
    .igv-scrollbar-column > div > div:hover {
      background-color: #c4c4c4;
    }

    .igv-track-drag-column {
      position: relative;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: flex-start;
      box-sizing: border-box;
      height: 100%;
      width: 12px;
      background-color: white;
    }
    .igv-track-drag-column > .igv-track-drag-handle {
      z-index: 512;
      position: relative;
      cursor: pointer;
      margin-top: 5px;
      width: 100%;
      border-style: solid;
      border-width: 0;
      border-top-right-radius: 6px;
      border-bottom-right-radius: 6px;
      background-color: #c4c4c4;
    }
    .igv-track-drag-column .igv-track-drag-handle-hover {
      background-color: #787878;
    }
    .igv-track-drag-column > .igv-track-drag-shim {
      position: relative;
      margin-top: 5px;
      width: 100%;
      border-style: solid;
      border-width: 0;
    }

    .igv-gear-menu-column {
      position: relative;
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: flex-start;
      box-sizing: border-box;
      height: 100%;
      width: 28px;
    }
    .igv-gear-menu-column > div {
      display: flex;
      flex-direction: column;
      flex-wrap: nowrap;
      justify-content: flex-start;
      align-items: center;
      margin-top: 5px;
      width: 100%;
      background: white;
    }
    .igv-gear-menu-column > div > div {
      position: relative;
      margin-top: 4px;
      width: 16px;
      height: 16px;
      color: #7F7F7F;
    }
    .igv-gear-menu-column > div > div:hover {
      cursor: pointer;
      color: #444;
    }
    """
    return css,


if __name__ == "__main__":
    app.run()
