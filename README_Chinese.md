<p align="center">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  <em>这是一款响应式的Python笔记本，具有优秀的可复现性，原生支持Git，并可作为脚本或应用程序部署。</em>

<p align="center">
  <a href="https://docs.marimo.io" target="_blank"><strong>用户手册</strong></a> ·
  <a href="https://marimo.io/discord?ref=readme" target="_blank"><strong>Discord 社区</strong></a> ·
  <a href="https://github.com/marimo-team/marimo/tree/main/examples" target="_blank"><strong>示例</strong></a>
</p>

<p align="center">
  <a href= "https://github.com/marimo-team/marimo/blob/main/README.md" target="_blank"><b>English</b></a>
  <b> | 简体中文</b>
</p>

<p align="center">
<a href="https://pypi.org/project/marimo/"><img src="https://img.shields.io/pypi/v/marimo?color=%2334D058&label=pypi" /></a>
<a href="https://anaconda.org/conda-forge/marimo"><img src="https://img.shields.io/conda/vn/conda-forge/marimo.svg"/></a>
<a href="https://github.com/marimo-team/marimo/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo" /></a>
</p>

**Marimo** 是一款响应式 Python 笔记本：运行单元格可与 UI 元素交互，marimo 会自动更新依赖于它的单元格（或将其<a href="#expensive-notebooks">标记为过时单元格</a>），从而保持代码和输出的一致性。**marimo** 笔记本以纯 Python 格式存储，可作为脚本执行，也可作为应用程序部署。

**为什么选择 marimo**

- 🚀 **功能齐全:** 替代 `jupyter`、`streamlit`、`jupytext`、`ipywidgets`、`papermill` 等更多工具
- ⚡️ **响应式**: 运行一个单元格，marimo 会响应式地[运行所有依赖单元格](https://docs.marimo.io/guides/reactivity.html) 或 <a href="#expensive-notebooks">将它们标记为陈旧</a>
- 🖐️ **交互性:** [绑定滑块、表格、图表等 UI 元素](https://docs.marimo.io/guides/interactivity.html) 到 Python——无需回调
- 🔬 **可复现:** [无隐藏状态](https://docs.marimo.io/guides/reactivity.html#no-hidden-state)，确定性执行
- 🏃‍♂️ **可执行:** [作为 Python 脚本执行](https://docs.marimo.io/guides/scripts.html)，通过命令行调整参数
- 🛜 **可分享**: [部署为交互式 Web 应用](https://docs.marimo.io/guides/apps.html) 或 [幻灯片](https://docs.marimo.io/guides/apps.html#slides-layout)，[通过 WASM 在浏览器中运行](https://docs.marimo.io/guides/wasm.html)
- 🛢️ **为数据设计**: 使用 [SQL](https://docs.marimo.io/guides/working_with_data/sql.html) 查询数据框和数据库，过滤和搜索 [数据框](https://docs.marimo.io/guides/working_with_data/dataframes.html)
- 🐍 **支持 Git:** 笔记本以 `.py` 文件格式存储
- ⌨️ **现代编辑器**: GitHub Copilot、AI 助手、vim 快捷键、变量浏览器，和 [更多功能](https://docs.marimo.io/guides/editor_features/index.html)

```python
pip install marimo && marimo tutorial intro
```

_在浏览器中运行[在线体验平台](https://marimo.app/l/c7h6pz)！_

_跳转到[快速起步](#快速起步)，了解命令行工具。_

## 响应式编程环境

Marimo 确保了您的代码、输出和程序的状态始的一致性，解决了与 Jupyter 等传统笔记本相关的许多[问题](https://docs.marimo.io/faq.html#faq-problems)。

**独有的响应式设计**
运行一个单元格，marimo 就会自动运行引用其变量的单元格，从而避免了手动重新运行单元格这一容易出错的工作。删除单元格，marimo 会从程序内存中删除其变量，消除隐藏状态。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/reactive.gif" width="700px" />

<a name="expensive-notebooks"></a>

**与计算成本高昂的笔记兼容** marimo 允许你将运行时配置为 “懒惰”模式，将受影响的单元标记为过时单元，而不是自动运行它们。这样既能保证程序状态，又能防止意外执行昂贵的单元。

**同步的 UI 元素** 与滑块、下拉菜单和数据框转换器等 UI 元素交互，使用这些元素的单元格会自动以最新值重新运行。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" width="700px" />

**高效运行** 通过静态分析代码，marimo 只运行需要运行的单元。

**动态的 Markdown 与 SQL** 使用 Markdown 编写 Python 代码的输出动态进行更新的文档。同时，使用内置 [SQL](https://docs.marimo.io/guides/working_with_data/sql.html) 引擎，可创建依赖于 Python 值的 SQL 查询，并针对数据框、数据库、CSV、Google Sheets 或其他任何内容执行查询，SQL 引擎会将结果返回为 Python 数据框。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

即使笔记本（notebook）使用了 markdown 或 SQL，它仍然是纯 Python 程序。

**确定性的执行顺序** 笔记本的执行顺序是确定的，基于变量引用，而不是单元格在页面上的位置。根据你顺序逻辑来组织笔记本。

**易用且强大** Marimo 集成了包括 GitHub Copilot、Ruff 代码格式化、HTML 导出、快速代码补全、[VSCode 扩展](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo)、交互式数据框查看器等非常有用的功能。

## 快速起步

**安装** 在终端运行以下代码：

```bash
pip install marimo  # or conda install -c conda-forge marimo
marimo tutorial intro
```

**或者在 Gitpod 运行**

单击此链接以在 Gitpod 工作区中打开存储库：

[https://gitpod.io/#https://github.com/marimo-team/marimo](https://gitpod.io/#https://github.com/marimo-team/marimo)

**创建新的笔记本**

使用以下命令创建或编辑笔记本

```bash
marimo edit
```

**运行应用** 将笔记本作为网络应用程序运行，隐藏 Python 代码，且不可编辑：

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

参阅我们的 [用户手册](https://docs.marimo.io),
在 `examples/` 文件夹下, 以及我们的[精选示例](https://marimo.io/@public)。

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
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html"> 自定义输入 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/working_with_data/plotting.html"> 自定义绘图 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/layouts/index.html"> 自定义布局 </a>
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

> 看到这里，如果你有任何的想法或者问题，欢迎加入我们的 [Discord](https://marimo.io/discord?ref=readme)！

## 社区

我们也正在建设 marimo 社区，来和我们一起玩吧！

- 🌟 [给我们的项目点一颗星星](https://github.com/marimo-team/marimo)
- 💬 [在 Discord 上与我们交流](https://marimo.io/discord?ref=readme)
- 📧 [订阅我们的最新动态](https://marimo.io/newsletter)
- ☁️ [加入我们的云服务器候补名单](https://marimo.io/cloud)
- ✏️ [在 github 上开始一个讨论话题](https://github.com/marimo-team/marimo/discussions)
- 🐦 [在推特上关注我们](https://twitter.com/marimo_io)
- 🎥 [在 YouTube 上关注我们](https://www.youtube.com/@marimo-team)
- 🕴️ [在领英上关注我们](https://www.linkedin.com/company/marimo-io)

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
