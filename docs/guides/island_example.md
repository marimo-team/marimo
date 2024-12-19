# marimo islands 🏝️

<!-- marimo js/ccs -->
<script
  type="module"
  src="https://cdn.jsdelivr.net/npm/@marimo-team/islands@0.5.0/dist/main.js"
></script>
<link
  href="https://cdn.jsdelivr.net/npm/@marimo-team/islands@0.5.0/dist/style.css"
  rel="stylesheet"
  crossorigin="anonymous"
/>
<!-- fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Fira+Mono:wght@400;500;700&amp;family=Lora&amp;family=PT+Sans:wght@400;700&amp;display=swap"
  rel="stylesheet"
/>
<link
  rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css"
  integrity="sha384-wcIxkf4k558AjM3Yz3BBFQUbk/zgIYC2R0QpeeYb+TwlBVMrlgLqwRjRtGZiK7ww"
  crossorigin="anonymous"
/>

!!! note "Preview"

    Islands are an early feature. While the API likely won't change, there are some improvements we'd like to make before we consider them stable.
    Please let us know on [GitHub](https://github.com/marimo-team/marimo/issues) if you run into any issues or have any feedback!

> This content below is powered by marimo's reactive runtime. It will become interactive after initializing the marimo runtime.

<hr/>

<marimo-island data-app-id="main" data-cell-id="Hbol" data-reactive="true">
  <marimo-cell-output></marimo-cell-output>
  <marimo-cell-code hidden>import%20marimo%20as%20mo</marimo-cell-code>
</marimo-island>
<marimo-island data-app-id="main" data-cell-id="MJUe" data-reactive="true">
  <marimo-cell-output>
    <marimo-ui-element object-id="MJUe-0" random-id="0a0beb44-f946-450d-a690-678a45aeb110">
      <marimo-slider
        data-initial-value="2"
        data-label="null"
        data-start="0"
        data-stop="10"
        data-steps="[]"
        data-debounce="false"
        data-orientation='"horizontal"'
        data-show-value="false"
        data-full-width="false"
      ></marimo-slider>
    </marimo-ui-element>
  </marimo-cell-output>
  <marimo-cell-code hidden>slider%20%3D%20mo.ui.slider(0%2C%2010,value=2)%3B%20slider</marimo-cell-code>
</marimo-island>
<marimo-island data-app-id="main" data-cell-id="vblA" data-reactive="true">
  <marimo-cell-output>
    <span class="markdown"><span class="paragraph">Hello, islands! 🏝️🏝️</span></span>
  </marimo-cell-output>
  <marimo-ui-element object-id="9c045fc3-f483-4024-ad01-cbf8f06cd7b7" random-id="9c045fc3-f483-4024-ad01-cbf8f06cd7b7">
    <marimo-code-editor
      data-initial-value='"mo.md(f&#x27;Hello, islands! {&#92;"&#92;ud83c&#92;udfdd&#92;ufe0f&#92;" * slider.value}&#x27;)"'
      data-label="null"
      data-language='"python"'
      data-placeholder='""'
      data-disabled="false"
    ></marimo-code-editor>
  </marimo-ui-element>
</marimo-island>

<hr style="margin: 20px 0;" />

??? example "See the HTML"

    ```html
    <marimo-island data-app-id="main" data-cell-id="Hbol" data-reactive="true">
      <marimo-cell-output></marimo-cell-output>
      <marimo-cell-code hidden>import%20marimo%20as%20mo</marimo-cell-code>
    </marimo-island>
    <marimo-island data-app-id="main" data-cell-id="MJUe" data-reactive="true">
      <marimo-cell-output>
        <marimo-ui-element object-id="MJUe-0" random-id="0a0beb44-f946-450d-a690-678a45aeb110">
          <marimo-slider
            data-initial-value="2"
            data-label="null"
            data-start="0"
            data-stop="10"
            data-steps="[]"
            data-debounce="false"
            data-orientation='"horizontal"'
            data-show-value="false"
            data-full-width="false"
          ></marimo-slider>
        </marimo-ui-element>
      </marimo-cell-output>
      <marimo-cell-code hidden>slider%20%3D%20mo.ui.slider(0%2C%2010,value=2)%3B%20slider</marimo-cell-code>
    </marimo-island>
    <marimo-island data-app-id="main" data-cell-id="vblA" data-reactive="true">
      <marimo-cell-output>
        <span class="markdown"><span class="paragraph">Hello, islands! 🏝️🏝️</span></span>
      </marimo-cell-output>
      <marimo-ui-element object-id="9c045fc3-f483-4024-ad01-cbf8f06cd7b7" random-id="9c045fc3-f483-4024-ad01-cbf8f06cd7b7">
        <marimo-code-editor
          data-initial-value='"mo.md(f&#x27;Hello, islands! {&#92;"&#92;ud83c&#92;udfdd&#92;ufe0f&#92;" * slider.value}&#x27;)"'
          data-label="null"
          data-language='"python"'
          data-placeholder='""'
          data-disabled="false"
        ></marimo-code-editor>
      </marimo-ui-element>
    </marimo-island>
    ```
