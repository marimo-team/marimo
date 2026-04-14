<p align="center">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  <em>一個響應式的 Python 筆記本，可重現、支援 Git 版本控制，並可部署為腳本或應用程式。</em>
</p>

<p align="center">
  <a href="https://docs.marimo.io" target="_blank"><strong>文件</strong></a> ·
  <a href="https://marimo.io/discord?ref=readme" target="_blank"><strong>Discord</strong></a> ·
  <a href="https://docs.marimo.io/examples/" target="_blank"><strong>範例</strong></a> ·
  <a href="https://marimo.io/gallery/" target="_blank"><strong>展示廊</strong></a> ·
  <a href="https://www.youtube.com/@marimo-team/" target="_blank"><strong>YouTube</strong></a>
</p>

<p align="center">
  <a href="https://github.com/marimo-team/marimo/blob/main/README.md" target="_blank"><b>English</b></a>
  <b> | </b>
  <b>繁體中文</b>
  <b> | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Chinese.md" target="_blank"><b>简体中文</b></a>
  <b> | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Japanese.md" target="_blank"><b>日本語</b></a>
  <b> | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Spanish.md" target="_blank"><b>Español</b></a>
</p>

<p align="center">
  <a href="https://pypi.org/project/marimo/"><img src="https://img.shields.io/pypi/v/marimo?color=%2334D058&label=pypi"/></a>
  <a href="https://anaconda.org/conda-forge/marimo"><img src="https://img.shields.io/conda/vn/conda-forge/marimo.svg"/></a>
  <a href="https://marimo.io/discord?ref=readme"><img src="https://shields.io/discord/1059888774789730424" alt="discord"/></a>
  <img alt="Pepy Total Downloads" src="https://img.shields.io/pepy/dt/marimo?label=pypi%20%7C%20downloads"/>
  <img alt="Conda Downloads" src="https://img.shields.io/conda/d/conda-forge/marimo"/>
  <a href="https://github.com/marimo-team/marimo/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo"/></a>
</p>

**marimo** 是一個響應式的 Python 筆記本：執行單元格或與 UI 元素互動時，marimo 會自動執行相依的單元格（或<a href="#expensive-notebooks">將其標記為過時</a>），保持程式碼和輸出的一致性。marimo 筆記本以純 Python 格式儲存（具有一流的 SQL 支援），可作為腳本執行，並可部署為應用程式。

**亮點**

- 🚀 **功能齊全：** 可取代 `jupyter`、`streamlit`、`jupytext`、`ipywidgets`、`papermill` 等工具
- ⚡️ **響應式：** 執行一個單元格，marimo 會響應式地[執行所有相依單元格](https://docs.marimo.io/guides/reactivity.html)或<a href="#expensive-notebooks">將其標記為過時</a>
- 🖐️ **互動性：** [綁定滑桿、表格、圖表等](https://docs.marimo.io/guides/interactivity.html)至 Python — 無需回呼函式
- 🐍 **支援 Git 版本控制：** 以 `.py` 檔案格式儲存
- 🛢️ **為資料設計：** 使用 SQL 查詢[資料框和資料庫](https://docs.marimo.io/guides/working_with_data/sql.html)，過濾和搜尋[資料框](https://docs.marimo.io/guides/working_with_data/dataframes.html)
- 🤖 **AI 原生：** [連結 agent CLIs](https://docs.marimo.io/guides/generate_with_ai/marimo_pair/)（如 Claude Code）至筆記本，或使用編輯器的[內建 AI 功能](https://docs.marimo.io/guides/editor_features/ai_completion/)
- 🔬 **可重現：** [無隱藏狀態](https://docs.marimo.io/guides/reactivity.html#no-hidden-state)、確定性執行、[內建套件管理](https://docs.marimo.io/guides/editor_features/package_management.html)
- 🏃 **可執行：** [作為 Python 腳本執行](https://docs.marimo.io/guides/scripts.html)，透過 CLI 參數化
- 🛜 **可分享：** [部署為互動式網頁應用程式](https://docs.marimo.io/guides/apps.html)或[簡報](https://docs.marimo.io/guides/apps.html#slides-layout)，[透過 WASM 在瀏覽器中執行](https://docs.marimo.io/guides/wasm.html)
- 🧩 **可重用：** [匯入函式和類別](https://docs.marimo.io/guides/reusing_functions/)從一個筆記本到另一個筆記本
- 🧪 **可測試：** 在筆記本上[執行 pytest](https://docs.marimo.io/guides/testing/)
- ⌨️ **現代化編輯器：** [GitHub Copilot](https://docs.marimo.io/guides/editor_features/ai_completion.html#github-copilot)、[AI 助手](https://docs.marimo.io/guides/editor_features/ai_completion.html)、vim 鍵盤綁定、變數瀏覽器，以及[更多功能](https://docs.marimo.io/guides/editor_features/index.html)
- 🧑‍💻 **使用您喜愛的編輯器**：在 [VS Code 或 Cursor](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo) 中執行，或在 neovim、Zed [或任何其他文字編輯器](https://docs.marimo.io/guides/editor_features/watching/)中編輯

```python
pip install marimo && marimo tutorial intro
```

_立即使用 [**mo**lab，我們的免費線上 notebook](https://molab.marimo.io/notebooks) 開始體驗。或跳至[快速開始](#快速開始)了解 CLI 使用方式。_

## 響應式程式設計環境

marimo 保證您的筆記本程式碼、輸出和程式狀態保持一致。這[解決了許多問題](https://docs.marimo.io/faq.html#faq-problems)，這些問題與傳統筆記本（如 Jupyter）相關。

**響應式程式設計環境。**
執行一個單元格，marimo 會_響應式地_自動執行所有引用其變數的單元格，省去手動重新執行單元格這種容易出錯的步驟。刪除一個單元格，marimo 會從程式記憶體中清除其變數，消除隱藏狀態。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/reactive.gif" width="700px" />

<a name="expensive-notebooks"></a>

**與高成本筆記本相容。** marimo 讓您[設定執行環境為惰性模式](https://docs.marimo.io/guides/configuration/runtime_configuration.html)，將受影響的單元格標記為過時，而不是自動執行它們。這為您提供了程式狀態的保證，同時防止意外執行高成本的單元格。

**同步的 UI 元素。** 與 [UI 元素](https://docs.marimo.io/guides/interactivity.html)互動，如[滑桿](https://docs.marimo.io/api/inputs/slider.html#slider)、[下拉選單](https://docs.marimo.io/api/inputs/dropdown.html)、[資料框轉換器](https://docs.marimo.io/api/inputs/dataframe.html)和[聊天介面](https://docs.marimo.io/api/inputs/chat.html)，使用它們的單元格會自動以最新值重新執行。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" width="700px" />

**互動式資料框。** [翻頁瀏覽、搜尋、篩選和排序](https://docs.marimo.io/guides/working_with_data/dataframes.html)數百萬行資料，速度極快，無需編寫程式碼。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-df.gif" width="700px" />

**使用資料感知 AI 生成單元格。** 使用您最喜愛 agent（如 Claude Code、Codex 或 OpenCode），透過 [marimo pair](https://docs.marimo.io/guides/generate_with_ai/marimo_pair/) 協作編輯 marimo 筆記本。或者，透過 [marimo 編輯器的 AI 助手](https://docs.marimo.io/guides/editor_features/ai_completion/)生成程式碼，該助手專門為資料處理而設計，具有記憶體中變數的上下文。自訂系統提示，使用您自己的 API 金鑰，或使用本地模型。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-generate-with-ai.gif" width="700px" />

**使用 SQL 查詢資料。** 建構依賴於 Python 值的 [SQL](https://docs.marimo.io/guides/working_with_data/sql.html) 查詢，並使用我們內建的 SQL 引擎對資料框、資料庫、資料湖、CSV、Google 試算表或任何其他資料來源執行查詢，結果會以 Python 資料框返回。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

您的筆記本仍然是純 Python，即使使用了 SQL。

**動態 Markdown。** 使用由 Python 變數參數化的 Markdown，講述依賴於 Python 資料的動態故事。

**內建套件管理。** marimo 內建支援所有主要的套件管理器，讓您[在匯入時安裝套件](https://docs.marimo.io/guides/editor_features/package_management.html)。marimo 甚至可以在筆記本檔案中[序列化套件需求](https://docs.marimo.io/guides/package_management/inlining_dependencies/)，並在隔離的 venv 沙盒中自動安裝它們。

**確定性執行順序。** 筆記本以確定性順序執行，基於變數引用而不是單元格在頁面上的位置。組織您的筆記本以最佳方式講述您想要的故事。

**高效能執行環境。** marimo 透過靜態分析您的程式碼，只執行需要執行的單元格。

**功能齊全。** marimo 附帶 GitHub Copilot、AI 助手、Ruff 程式碼格式化、HTML 匯出、快速程式碼自動完成、[VS Code 擴充套件](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo)、互動式資料框檢視器，以及[更多](https://docs.marimo.io/guides/editor_features/index.html)便利功能。

## 快速開始

_我們 [YouTube 頻道](https://www.youtube.com/@marimo-team)上的 [marimo 概念播放清單](https://www.youtube.com/watch?v=3N6lInzq5MI&list=PLNJXGo8e1XT9jP7gPbRdm1XwloZVFvLEq)提供了許多功能的概覽。_

**安裝**

在終端機中執行

```bash
pip install marimo  # 或 conda install -c conda-forge marimo
marimo tutorial intro
```

若要安裝包含額外相依套件以解鎖 SQL 單元格、AI 自動完成等功能，請執行

```bash
pip install "marimo[recommended]"
```

**建立新筆記本**

使用以下指令建立或編輯筆記本

```bash
marimo edit
```

**作為應用程式執行**

將您的筆記本作為網頁應用程式執行，Python 程式碼將被隱藏且不可編輯：

```bash
marimo run your_notebook.py
```

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

**作為腳本執行**

在終端機中將 notebook 作為腳本執行

```bash
python your_notebook.py
```

**自動轉換 Jupyter 筆記本**

使用 CLI 自動將 Jupyter 筆記本轉換為 marimo 筆記本

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

或使用我們的[網頁介面](https://marimo.io/convert)。

**教學**

列出所有教學：

```bash
marimo tutorial --help
```

**分享雲端筆記本。**

使用 [molab](https://molab.marimo.io/notebooks)，一個類似於 Google Colab 的雲端 marimo 筆記本服務，
來建立和分享 notebook 連結。

## 有問題嗎？

請參閱我們文件中的[常見問題](https://docs.marimo.io/faq.html)。

## 了解更多

marimo 容易上手，並為進階使用者提供了許多強大功能。
例如，這是一個使用 marimo 製作的嵌入視覺化工具
（[在 molab 上即時試用 notebook！](https://molab.marimo.io/notebooks/nb_jJiFFtznAy4BxkrrZA1o9b/app?show-code=true)）：

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/embedding.gif" width="700px" />

查看我們的[文件](https://docs.marimo.io)、
[使用範例](https://docs.marimo.io/examples/)，以及我們的[展示廊](https://marimo.io/gallery)以了解更多。

<table border="0">
  <tr>
    <td>
      <a target="_blank" href="https://docs.marimo.io/getting_started/key_concepts.html">
        <img src="https://docs.marimo.io/_static/reactive.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html">
        <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/working_with_data/plotting.html">
        <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-intro.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/layouts/index.html">
        <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/outputs.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
  </tr>
  <tr>
    <td>
      <a target="_blank" href="https://docs.marimo.io/getting_started/key_concepts.html"> 教學 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html"> 輸入 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/working_with_data/plotting.html"> 繪圖 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/layouts/index.html"> 佈局 </a>
    </td>
  </tr>
  <tr>
    <td>
      <a target="_blank" href="https://molab.marimo.io/notebooks/nb_TWVGCgZZK4L8zj5ziUBNVL">
        <img src="https://marimo.io/molab-shield.svg"/>
      </a>
    </td>
    <td>
      <a target="_blank" href="https://molab.marimo.io/notebooks/nb_WuoXgs7mjg5yqrMxJXjRpF">
        <img src="https://marimo.io/molab-shield.svg"/>
      </a>
    </td>
    <td>
      <a target="_blank" href="https://molab.marimo.io/notebooks/nb_vXxD13t2RoMTLjC89qdn6c">
        <img src="https://marimo.io/molab-shield.svg"/>
      </a>
    </td>
    <td>
      <a target="_blank" href="https://molab.marimo.io/notebooks/nb_XpXx8MX99dWAjn4k1b3xiU">
        <img src="https://marimo.io/molab-shield.svg"/>
      </a>
    </td>
  </tr>
</table>

## 貢獻

我們感謝所有的貢獻！您不需要是專家即可提供協助。
請參閱 [CONTRIBUTING.md](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md) 以獲取更多關於如何開始的詳細資訊。

> 有問題嗎？請在 [Discord](https://marimo.io/discord?ref=readme) 上與我們聯繫。

## 社群

我們正在建立一個社群。歡迎來與我們交流！

- 🌟 [在 GitHub 上為我們加星](https://github.com/marimo-team/marimo)
- 💬 [在 Discord 上與我們聊天](https://marimo.io/discord?ref=readme)
- 📧 [訂閱我們的電子報](https://marimo.io/newsletter)
- ☁️ [加入我們的雲端服務候補名單](https://marimo.io/cloud)
- ✏️ [在 GitHub 上發起討論](https://github.com/marimo-team/marimo/discussions)
- 🦋 [在 Bluesky 上追蹤我們](https://bsky.app/profile/marimo.io)
- 🐦 [在 Twitter 上追蹤我們](https://twitter.com/marimo_io)
- 🎥 [在 YouTube 上訂閱](https://www.youtube.com/@marimo-team)
- 🤖 [在 Reddit 上追蹤我們](https://www.reddit.com/r/marimo_notebook)
- 🕴️ [在 LinkedIn 上追蹤我們](https://www.linkedin.com/company/marimo-io)

**NumFOCUS 附屬專案。** marimo 是更廣泛 Python 生態系統的核心部分，也是 NumFOCUS 社群的成員，該社群包括 NumPy、SciPy 和 Matplotlib 等專案。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/numfocus_affiliated_project.png" height="40px" />


## 靈感 ✨

marimo 是 Python 筆記本的**重新發明**，作為一個可重現、互動且可分享的 Python 程式，而非容易出錯的 JSON 草稿本。

我們相信工具會影響我們的思考方式——更好的工具，造就更好的思維。透過 marimo，我們希望為 Python 社群提供一個更好的程式設計環境，用以進行研究並傳達成果；實驗程式碼並分享它；學習計算科學並教授它。

我們的靈感來自許多地方和專案，特別是 [Pluto.jl](https://github.com/fonsp/Pluto.jl)、[ObservableHQ](https://observablehq.com/tutorials) 和 [Bret Victor 的文章](http://worrydream.com/)。marimo 是朝向響應式資料流程式設計更大運動的一部分。從 [IPyflow](https://github.com/ipyflow/ipyflow)、[streamlit](https://github.com/streamlit/streamlit)、[TensorFlow](https://github.com/tensorflow/tensorflow)、[PyTorch](https://github.com/pytorch/pytorch/tree/main)、[JAX](https://github.com/google/jax) 到 [React](https://github.com/facebook/react)，函數式、聲明式和響應式程式設計的理念正在改善廣泛的工具。

<p align="right">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-horizontal.png" height="200px">
</p>

---

> **Note**: This is a community-contributed translation. The [English README](README.md) is the authoritative and most up-to-date version.

> **注意**：這是社群貢獻的翻譯。[英文 README](README.md) 是最權威且最新的版本。
