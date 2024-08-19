<p align="center">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  <em>这是一个所见即所得的Python笔记本，具有良好的可复现性，原生支持Git，并且可以保存为独立运行的文件。</em>

<p align="center">
  <a href="https://docs.marimo.io" target="_blank"><strong>用户手册</strong></a> ·
  <a href="https://discord.gg/JE7nhX6mD8" target="_blank"><strong>讨论区</strong></a> ·
  <a href="https://github.com/marimo-team/marimo/tree/main/examples" target="_blank"><strong>示例</strong></a>
</p>

<p align="center">
<a href="https://pypi.org/project/marimo/"><img src="https://img.shields.io/pypi/v/marimo?color=%2334D058&label=pypi" /></a>
<a href="https://anaconda.org/conda-forge/marimo"><img src="https://img.shields.io/conda/vn/conda-forge/marimo.svg"/></a>
<a href="https://github.com/marimo-team/marimo/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo" /></a>
</p>

**Marimo** 具有特别的设计，你只需要考虑你想运行哪一段代码,
其它的事情都交给它就好。(或者 <a href="#expensive-notebooks"> 会帮你标记出哪些代码暂时不需要运行</a>)。这样，当你对代码做出修改的时候，不需要花费额外的时间和精力去考虑你刚刚的修改是否会产生意料之外的影响。
更重要的是，**marimo** 可以把你的文件保存为纯粹的可执行的python脚本或是应用程序。

**为什么选择marimo？**.

- **所点即所得**: marimo会自动处理你点击运行的代码的依赖项。
- **丝滑的交互体验**: 还在反复运行出图的代码来调整图像？选择marimo，你可以随意使用任何交互式的组件来调整你的图像。
- **任意复现**: 你一定有过同样的代码输出不同的结果的体验，现在，没有了。
- **可以到处复用**: 可以作为Python脚本执行，并且可以通过命令行参数进行参数化。
- **简单共享**: marimo可以部署为交互式 Web 应用程序，或通过 WASM 在浏览器中运行。
- **数据驱动的**: 原生支持数据库工具SQL和数据源面板，你甚至可以想象靠它实现数据治理？
- **git-friendly**: 保存为 `.py` 文件

## 如何开始？

```python
pip install marimo && marimo tutorial intro
```

_当然！你可以从这里[这里](https://marimo.app/l/c7h6pz)开始， 这是一个在线的体验marimo页面，你不需要离开你的浏览器！_

_想要直接开始？快进到[这里](#quickstart) 快速上手我们的CLI工具。_

## 反应式编程环境

Marimo确保了您的代码、输出和程序的状态始终处在您的预期之中。这解决了许多像用户在使用像Jupyter这样的工具时面临的典型[问题](https://docs.marimo.io/faq.html#faq-problems) 。

**独有的反应式设计**
Marimo会在你运行任意的notebook单元格的时候处理所有被当前单元格引用的变量，就像下面的动图中展示的那样。这样的设计避免了手动操作时可能出现的错误，比如你可能会忘记了其中的某些变量已经不是之前的状态。
同时，marimo会在你删除一个单元格的时候从内存中删除本单元格独有的变量，这使得所有的变量都是显式存在的，这样自动化的回收机制会在你长时间工作的时候显示出其优越性。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/reactive.gif" width="700px" />

<a name="expensive-notebooks"></a>

**控制计算成本💰** 有些时候，你会遇到需要大量计算资源或时间的情况，Marimo能够很好的适应这种情况，它提供了一种控制这些昂贵计算的方法。
首先，Marimo 允许用户配置运行时的行为为“惰性”，即在代码单元格发生变化时，不会立即自动执行相关的依赖单元格。
其次，Marimo将受影响的单元格标记为失效：当某个单元格的输入改变时，相关的依赖单元格不会立即运行，而是被标记为“失效”（stale），提示用户这些单元格需要重新运行。
最后，Marimo会保持程序状态并防止意外执行：这种机制可以确保在用户明确决定之前，程序状态不会发生意外的改变，尤其是避免了那些需要大量计算资源的单元格在不合适的时候被意外执行。

**UI和代码同步🔄** Marimo 支持一些可交互的用户界面元素，如滑块、下拉菜单以及数据框转换器。
当用户与这些界面元素交互时，相关的代码单元格会自动重新运行，并且使用用户在界面元素中选择或调整的最新值。这种同步机制确保了界面和代码执行之间的一致性和实时更新。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" width="700px" />

**良好的性能表现🚀** Marimo 会分析代码的依赖关系，确定哪些单元格受到了更改，哪些单元格需要重新运行。通过这种静态分析，Marimo 可以避免不必要的计算，只执行必要的代码单元格，从而提升运行效率。这使得 Marimo 特别适合于处理大型项目或复杂的工作流，因为它能够有效减少不必要的资源消耗和执行时间。

**令人惊叹的Markdown和SQL的有机结合🗄** 用户可以在Marimo中使用Markdown编写文档，而这些文档内容可以被Python代码的输出动态的进行更新。
同时，用户也可以在Marimo中编写[SQL](https://docs.marimo.io/guides/sql.html)查询语句，而这些查询语句可以动态地使用 Python 变量或数据。这种结合使得用户可以更灵活地查询数据，无论数据来源是数据框、数据库、CSV 文件，还是 Google Sheets。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

即使拥有如此多的特性，Marimo还可以保持你的python文件干爽整洁！Marimo不会为你的python代码中添加任何不必要的元素。

**严格的代码块执行顺序🧘** Marimo按照确定的顺序执行笔记本中的代码单元格，这个顺序是基于变量引用关系，而不是单元格在页面上的位置。
用户可以自由地根据内容的逻辑性或展示需求来安排单元格的顺序，而Marimo会自动处理好代码的执行顺序，确保一切按预期进行。
这使得笔记本既可以是一个技术文档，又可以是一个有逻辑、有叙事性的展示工具。

**易用且强大🏆** Marimo集成了包括GitHub Copilot、Ruff代码格式化、HTML导出、快速代码补全、VSCode扩展、交互式数据框查看器等等非常有用的功能。
除此之外，marimo还包含了许多其他小工具和功能，也欢迎👏你的加入为marimo带来更多特性！

## 快速起步！

**安装** 在终端中，输入下面的代码：

```bash
pip install marimo  # or conda install -c conda-forge marimo
marimo tutorial intro
```

**或者在Gitpod运行**

单击此链接以在 Gitpod 工作区中打开存储库：

[https://gitpod.io/#https://github.com/marimo-team/marimo](https://gitpod.io/#https://github.com/marimo-team/marimo)

**创建新的笔记本**

使用以下命令创建或编辑笔记本

```bash
marimo edit
```

**开始运行！** 使用 Python 将笔记本作为 Web 应用运行, 同时将代码隐藏且设置为不可编辑模式:

```bash
marimo run your_notebook.py
```

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

**作为脚本执行**  在终端命令行输入：

```bash
python your_notebook.py
```

这和一般的python脚本的执行几乎完全一致。

**自动转换已有的Jupyter笔记本**  将jupyter笔记本自动转换为marimo格式的笔记本

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

请参阅我们文档中的[FAQ](https://docs.marimo.io/faq.html) 的部分。

## 更多信息

Marimo 很容易上手，为高级用户提供了很大的空间。 例如，这里有一个用 marimo 制作的嵌入可视化工具
([示例视频](https://marimo.io/videos/landing/full.mp4)):

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/embedding.gif" width="700px" />

参阅我们的 [用户手册](https://docs.marimo.io),
在 `examples/` 文件夹下, 以及我们的[精选示例](https://marimo.io/@public)可以看到更多有趣的东西。

<table border="0">
  <tr>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/overview.html">
        <img src="https://docs.marimo.io/_static/reactive.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html">
        <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/plotting.html">
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
      <a target="_blank" href="https://docs.marimo.io/guides/overview.html"> 教程 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html"> 自定义输入 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/plotting.html"> 自定义绘图 </a>
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

## 致谢

我们感谢所有人的热情贡献! 这是为所有人设计的工具，我们真挚的欢迎任何人的任何意见！
请参阅[CONTRIBUTING.md](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md) 获取更多信息，了解如何参与到这个伟大的项目中来。

> 看到这里，如果你有任何的想法或者问题? 欢迎在Discord上加入我们！[讨论区](https://discord.gg/JE7nhX6mD8).

## 社区

我们也正在建设marimo社区，Let‘s rock～

- 🌟 [给我们的项目点一颗星星](https://github.com/marimo-team/marimo)
- 💬 [在Discord上与我们取得联系](https://discord.gg/JE7nhX6mD8)
- 📧 [最新信息](https://marimo.io/newsletter)
- ☁️ [加入我们的Cloud Waitlist](https://marimo.io/cloud)
- ✏️ [在github上开始一个讨论话题](https://github.com/marimo-team/marimo/discussions)
- 🐦 [在推特（现在叫X）上关注我们](https://twitter.com/marimo_io)
- 🕴️ [在领英上关注我们](https://www.linkedin.com/company/marimo-io)

## 愿景 ✨

一直以来，人类的进步就是工具的进步。

我们相信，我们可以通过技术的迭代为广大用户赋能，从而助力整个社区的每个用户能在他们的岗位上走的更远。

Marimo旨在重塑了Python笔记本的用户体验，使notebook变为用户可信赖的，可重复的、交互的和可共享可靠的工具。

我们始终坚信_Better tools, for better minds._。

我们的灵感来自于很多已有的项目, 特别是
[Pluto.jl](https://github.com/fonsp/Pluto.jl)，
[ObservableHQ](https://observablehq.com/tutorials)，和
[Bret Victor's essays](http://worrydream.com/)。
Marimo是反应式数据流编程的进一步发展。从
[IPyflow](https://github.com/ipyflow/ipyflow)，[streamlit](https://github.com/streamlit/streamlit)，
[TensorFlow](https://github.com/tensorflow/tensorflow)，
[PyTorch](https://github.com/pytorch/pytorch/tree/main)，
[JAX](https://github.com/google/jax)，到
[React](https://github.com/facebook/react)，我们可以看到，函数式编程，
声明式编程和反应式编程的概念正在对我们的工具产生广泛而深刻的影响，我们正在路上。

<p align="right">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-horizontal.png" height="200px">
</p>
](https://github.com/OOAAHH/marimo_chn/edit/main/README.md)
