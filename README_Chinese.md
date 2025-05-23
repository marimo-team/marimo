<p align="center">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  <em>这是一款响应式的Python笔记本，具有优秀的可复现性，原生支持Git，并可作为脚本或应用程序部署。</em>

<p align="center">
  <a href="https://docs.marimo.io" target="_blank"><strong>用户手册</strong></a> ·
  <a href="https://marimo.io/discord?ref=readme" target="_blank"><strong>Discord 社区</strong></a> ·
  <a href="https://github.com/marimo-team/marimo/tree/main/examples" target="_blank"><strong>示例</strong></a> ·
  <a href="https://marimo.io/gallery/" target="_blank"><strong>展示廊</strong></a> ·
  <a href="https://www.youtube.com/@marimo-team/" target="_blank"><strong>YouTube</strong></a>
</p>

<p align="center">
  <a href= "https://github.com/marimo-team/marimo/blob/main/README.md" target="_blank"><b>English</b></a>
  <b> | 简体中文 | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Japanese.md" target="_blank"><b>日本語</b></a>
  <b> | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Spanish.md" target="_blank"><b>Español</b></a>
</p>

<p align="center">
<a href="https://pypi.org/project/marimo/"><img src="https://img.shields.io/pypi/v/marimo?color=%2334D058&label=pypi"/></a>
<a href="https://anaconda.org/conda-forge/marimo"><img src="https://img.shields.io/conda/vn/conda-forge/marimo.svg"/></a>
<a href="https://marimo.io/discord?ref=readme"><img src="https://shields.io/discord/1059888774789730424" alt="discord" /></a>
<img alt="Pepy Total Downloads" src="https://img.shields.io/pepy/dt/marimo?label=pypi%20%7C%20downloads"/>
<img alt="Conda Downloads" src="https://img.shields.io/conda/d/conda-forge/marimo" />
<a href="https://github.com/marimo-team/marimo/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo" /></a>
</p>

**Marimo** 是一款响应式 Python 笔记本：运行单元格可与 UI 元素交互，marimo 会自动更新依赖于它的单元格（或将其<a href="#expensive-notebooks">标记为过时单元格</a>），从而保持代码和输出的一致性。**marimo** 笔记本以纯 Python 格式存储，可作为脚本执行，也可作为应用程序部署。

**为什么选择 marimo**

- 🚀 **功能齐全**：替代 `jupyter`、`streamlit`、`jupytext`、`ipywidgets`、`papermill` 等更多工具
- ⚡️ **响应式**：运行一个单元格，marimo会响应式地[运行所有依赖单元格](https://docs.marimo.io/guides/reactivity.html)或<a href="#expensive-notebooks">将它们标记为过时</a>
- 🖐️ **交互性**：[绑定滑块、表格、图表等UI元素](https://docs.marimo.io/guides/interactivity.html)到Python代码——无需回调函数
- 🐍 **支持Git版本控制**：笔记本以`.py`文件格式存储
- 🛢️ **为数据设计**：使用[SQL](https://docs.marimo.io/guides/working_with_data/sql.html)查询数据框和数据库，过滤和搜索[数据框](https://docs.marimo.io/guides/working_with_data/dataframes.html)
- 🔬 **可复现**：[无隐藏状态](https://docs.marimo.io/guides/reactivity.html#no-hidden-state)，确定性执行，[内置包管理](https://docs.marimo.io/guides/editor_features/package_management.html)
- 🏃 **可执行**：[作为Python脚本执行](https://docs.marimo.io/guides/scripts.html)，通过命令行参数进行配置
- 🛜 **可分享**：[部署为交互式Web应用](https://docs.marimo.io/guides/apps.html)或[幻灯片](https://docs.marimo.io/guides/apps.html#slides-layout)，[通过WASM在浏览器中运行](https://docs.marimo.io/guides/wasm.html)
- 🧩 **可复用：** 可从一个笔记本[导入函数和类](https://docs.marimo.io/guides/reusing_functions/)到另一个笔记本
- 🧪 **便于测试：** 可在笔记本上运行 [pytest](https://docs.marimo.io/guides/testing/)
- ⌨️ **现代编辑器**：[GitHub Copilot](https://docs.marimo.io/guides/editor_features/ai_completion.html#github-copilot)、[AI助手](https://docs.marimo.io/guides/editor_features/ai_completion.html#using-ollama)、vim快捷键、变量浏览器和[更多功能](https://docs.marimo.io/guides/editor_features/index.html)

```python
pip install marimo && marimo tutorial intro
```

_在我们的[在线体验平台](https://marimo.app/l/c7h6pz)试用marimo，完全在浏览器中运行！_

_跳转到[快速入门](#快速入门)了解我们的命令行工具。_

## 响应式编程环境

Marimo 确保了您的代码、输出和程序的状态始的一致性，解决了与 Jupyter 等传统笔记本相关的许多[问题](https://docs.marimo.io/faq.html#faq-problems)。

**独有的响应式设计**
运行一个单元格，marimo 就会自动运行引用其变量的单元格，从而避免了手动重新运行单元格这一容易出错的工作。删除单元格，marimo 会从程序内存中删除其变量，消除隐藏状态。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/reactive.gif" width="700px" />

<a name="expensive-notebooks"></a>

**兼容计算密集型笔记本**。marimo允许您[将运行时配置为延迟模式](https://docs.marimo.io/guides/configuration/runtime_configuration.html)，将受影响的单元格标记为过时而不是自动运行它们。这既能保证程序状态的完整性，又能防止意外执行计算密集型单元格。

**同步的UI元素**。与[UI元素](https://docs.marimo.io/guides/interactivity.html)如[滑块](https://docs.marimo.io/api/inputs/slider.html#slider)、[下拉菜单](https://docs.marimo.io/api/inputs/dropdown.html)、[数据框转换器](https://docs.marimo.io/api/inputs/dataframe.html)和[聊天界面](https://docs.marimo.io/api/inputs/chat.html)交互时，使用它们的单元格会自动以最新值重新运行。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" width="700px" />

**交互式数据框**。[分页浏览、搜索、过滤和排序](https://docs.marimo.io/guides/working_with_data/dataframes.html)数百万行数据，极速运行，无需编写代码。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-df.gif" width="700px" />

**高效运行时**。marimo通过静态分析代码，只运行需要运行的单元格。

**动态Markdown和SQL**。使用Markdown创建依赖Python数据的动态文档。或者构建依赖Python值的[SQL](https://docs.marimo.io/guides/working_with_data/sql.html)查询，并针对数据框、数据库、CSV、Google Sheets或其他数据源执行，使用我们内置的SQL引擎将结果作为Python数据框返回。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

即使使用了Markdown或SQL，您的笔记本仍然是纯Python代码。

**确定性执行顺序**。笔记本按照基于变量引用而非单元格页面位置的确定性顺序执行。您可以根据想要讲述的故事组织笔记本。

**内置包管理**。marimo内置支持所有主要的包管理器，允许您[在导入时安装包](https://docs.marimo.io/guides/editor_features/package_management.html)。marimo甚至可以[序列化包依赖](https://docs.marimo.io/guides/package_reproducibility.html)到笔记本文件中，并在隔离的venv沙箱中自动安装它们。

**功能齐全**。marimo集成了GitHub Copilot、AI助手、Ruff代码格式化、HTML导出、快速代码补全、[VS Code扩展](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo)、交互式数据框查看器和[更多](https://docs.marimo.io/guides/editor_features/index.html)便捷功能。

## 快速起步

**安装** 在终端运行以下代码：

```bash
pip install marimo  # or conda install -c conda-forge marimo
marimo tutorial intro
```

要安装包含额外依赖项的版本（启用SQL单元格、AI补全等功能），运行：

```bash
pip install marimo[recommended]
```

**创建新的笔记本**

使用以下命令创建或编辑笔记本

```bash
marimo edit
```

**运行应用** 将笔记本作为Web应用运行，隐藏并锁定Python代码：

```bash
marimo run your_notebook.py
```

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

**作为脚本执行** 在命令行中将笔记本作为脚本执行：

```bash
python your_notebook.py
```

**自动转换已有的 Jupyter 笔记本** 通过命令行将 Jupyter 笔记本自动转换为 marimo 格式的笔记本

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

对此，我们也有[在线工具](https://marimo.io/convert)可供使用。

**教程**
列出所有的可用教程:

```bash
marimo tutorial --help
```

## 如果你有一些问题？

请参阅我们文档中的[FAQ](https://docs.marimo.io/faq.html)部分。

## 更多信息

Marimo 很容易上手，为高级用户提供了很大的空间。 例如，这是一个用 marimo 制作的 embedding 可视化工具
([示例视频](https://marimo.io/videos/landing/full.mp4)):

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/embedding.gif" width="700px" />

查看我们的[文档](https://docs.marimo.io)、
[使用示例](https://docs.marimo.io/examples/)和[展示廊](https://marimo.io/gallery)了解更多。

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
      <a target="_blank" href="https://docs.marimo.io/getting_started/key_concepts.html"> 教程 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html"> 输入控件 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/working_with_data/plotting.html"> 绘图 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/layouts/index.html"> 布局 </a>
    </td>
  </tr>
  <tr>
    <td>
      <a target="_blank" href="https://marimo.app/l/c7h6pz">
        <img src="https://marimo.io/shield.svg"/>
      </a>
    </td>
    <td>
      <a target="_blank" href="https://marimo.app/l/0ue871">
        <img src="https://marimo.io/shield.svg"/>
      </a>
    </td>
    <td>
      <a target="_blank" href="https://marimo.app/l/lxp1jk">
        <img src="https://marimo.io/shield.svg"/>
      </a>
    </td>
    <td>
      <a target="_blank" href="https://marimo.app/l/14ovyr">
        <img src="https://marimo.io/shield.svg"/>
      </a>
    </td>
  </tr>
</table>

## 贡献

我们感谢所有人的贡献! 这是为所有人设计的工具，我们真挚的欢迎任何人的任何意见！
请参阅[CONTRIBUTING.md](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md) 获取更多信息，了解如何参与到这个项目中来。

> 有问题？请[在Discord上联系我们](https://marimo.io/discord?ref=readme)。

## 社区

我们也正在建设 marimo 社区，来和我们一起玩吧！

- 🌟 [在GitHub上为我们点赞](https://github.com/marimo-team/marimo)
- 💬 [在Discord上与我们交流](https://marimo.io/discord?ref=readme)
- 📧 [订阅我们的通讯](https://marimo.io/newsletter)
- ☁️ [加入我们的云服务候补名单](https://marimo.io/cloud)
- ✏️ [在GitHub上开始讨论](https://github.com/marimo-team/marimo/discussions)
- 🦋 [在Bluesky上关注我们](https://bsky.app/profile/marimo.io)
- 🐦 [在Twitter上关注我们](https://twitter.com/marimo_io)
- 🎥 [在YouTube上订阅](https://www.youtube.com/@marimo-team)
- 🕴️ [在LinkedIn上关注我们](https://www.linkedin.com/company/marimo-io)

## 愿景 ✨

marimo 是对 Python 笔记本的**重塑**，它是一个可复制、可交互、可共享的 Python 程序，而不是容易出错的 JSON 便笺。

我们相信，我们使用的工具会影响我们的思维方式--更好的工具，造就更好的思维。我们希望通过 marimo 为 Python 社区提供一个更好的编程环境，以便进行研究和交流；进行代码实验和分享；学习计算科学和教授计算科学。

我们的灵感来自于很多已有的项目, 特别是
[Pluto.jl](https://github.com/fonsp/Pluto.jl)，
[ObservableHQ](https://observablehq.com/tutorials)，和
[Bret Victor's essays](http://worrydream.com/)。
marimo 是向响应式数据流编程迈进的一大步。从
[IPyflow](https://github.com/ipyflow/ipyflow)，[streamlit](https://github.com/streamlit/streamlit)，
[TensorFlow](https://github.com/tensorflow/tensorflow)，
[PyTorch](https://github.com/pytorch/pytorch/tree/main)，
[JAX](https://github.com/google/jax)，到
[React](https://github.com/facebook/react)，函数式、声明式和响应式编程的理念正在改善一系列工具。

<p align="right">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-horizontal.png" height="200px">
</p>
