<p align="center">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  <em>再現性が高く、Git に優しく、スクリプトやアプリとして展開できるリアクティブな Python ノートブック。</em>
</p>

<p align="center">
  <a href="https://docs.marimo.io" target="_blank"><strong>ドキュメント</strong></a> ·
  <a href="https://marimo.io/discord?ref=readme" target="_blank"><strong>Discord</strong></a> ·
  <a href="https://docs.marimo.io/examples/" target="_blank"><strong>サンプル</strong></a> ·
  <a href="https://marimo.io/gallery/" target="_blank"><strong>ギャラリー</strong></a> ·
  <a href="https://www.youtube.com/@marimo-team/" target="_blank"><strong>YouTube</strong></a>
</p>

<p align="center">
  <a href="https://github.com/marimo-team/marimo/blob/main/README.md" target="_blank"><b>English</b></a>
  <b> | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Traditional_Chinese.md" target="_blank"><b>繁體中文</b></a>
  <b> | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Chinese.md" target="_blank"><b>简体中文</b></a>
  <b> | </b>
  <b>日本語</b>
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

**marimo** はリアクティブな Python ノートブックです。セルを実行したり UI 要素を操作すると、marimo は依存するセルを自動的に実行する（または<a name="expensive-notebooks"></a><a href="#expensive-notebooks">影響を受けるセルを古いものとしてマークする</a>）ことで、コードと出力の一貫性を保ちます。marimo のノートブックは純粋な Python として保存され、スクリプトとして実行でき、アプリとしてデプロイできます。

**Highlights（主な特徴）**

- 🚀 **batteries-included:** `jupyter`、`streamlit`、`jupytext`、`ipywidgets`、`papermill` などの代替を目指します。
- ⚡️ **reactive:** セルを実行すると marimo はリアクティブに[すべての依存セルを実行](https://docs.marimo.io/guides/reactivity.html)するか、影響を受けるセルを古いものとしてマークします。
- 🖐️ **interactive:** [スライダー、テーブル、プロットなど](https://docs.marimo.io/guides/interactivity.html)を Python にバインドできます（コールバック不要）。
- 🐍 **git-friendly:** ノートブックは `.py` ファイルとして保存されます。
- 🛢️ **designed for data:** データフレーム、データベース、ウェアハウス、レイクハウスを [SQL でクエリ](https://docs.marimo.io/guides/working_with_data/sql.html)したり、[データフレームをフィルタ・検索](https://docs.marimo.io/guides/working_with_data/dataframes.html)できます。
- 🤖 **AI-native:** データ作業に特化した AI でセルを[生成](https://docs.marimo.io/guides/generate_with_ai/)できます。
- 🔬 **reproducible:** [隠れた状態なし](https://docs.marimo.io/guides/reactivity.html#no-hidden-state)、決定論的な実行、[組み込みパッケージ管理](https://docs.marimo.io/guides/package_management/)を備えています。
- 🏃 **executable:** ノートブックを [Python スクリプトとして実行](https://docs.marimo.io/guides/scripts.html)でき、CLI 引数でパラメータ化できます。
- 🛜 **shareable:** インタラクティブな Web アプリとしてデプロイしたり、[スライド](https://docs.marimo.io/guides/apps.html#slides-layout)に変換したり、[WASM でブラウザ実行](https://docs.marimo.io/guides/wasm.html)できます。
- 🧩 **reusable:** ノートブック間で関数やクラスを[インポートして再利用](https://docs.marimo.io/guides/reusing_functions/)できます。
- 🧪 **testable:** ノートブックに対して [pytest を実行](https://docs.marimo.io/guides/testing/)できます。
- ⌨️ **a modern editor:** GitHub Copilot、AI アシスタント、Ruff によるコード整形、高速補完、[VS Code 拡張](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo) などのエディタ機能を備えています。
- 🧑‍💻 **use your favorite editor:** VS Code や Cursor、neovim、Zed、その他のテキストエディタで編集できます。

```python
pip install marimo && marimo tutorial intro
```

_ブラウザのみで動作するオンラインプレイグラウンドでも marimo を試すことができます: https://marimo.app/l/c7h6pz_

_クイックスタートは次のセクションを参照してください。_

## A reactive programming environment

marimo はノートブックのコード、出力、プログラム状態の一貫性を保証します。これにより Jupyter のような従来のノートブックに関連する多くの問題が解決されます（詳細は [FAQ](https://docs.marimo.io/faq.html#faq-problems) を参照）。

**A reactive programming environment.**
セルを実行すると marimo は _反応_ し、その変数を参照するセルを自動的に再実行することで、手動でセルを再実行することに起因するミスを防ぎます。セルを削除すると、marimo はその変数をメモリから削除し、隠れた状態を排除します。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/reactive.gif" width="700px" />

**Compatible with expensive notebooks.** marimo はランタイムを遅延評価に設定でき、影響を受けるセルを自動実行する代わりに古いものとしてマークできます。これにより、高コストなセルの誤実行を防ぎつつプログラム状態の保証を提供します。

**Synchronized UI elements.** [スライダーやドロップダウン、データフレーム変換、チャットインターフェースなどの UI 要素](https://docs.marimo.io/guides/interactivity.html)を操作すると、それらを使うセルが自動的に最新の値で再実行されます。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" width="700px" />

**Interactive dataframes.** 数百万行のデータをコード不要でページング、検索、フィルタ、ソートできます。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-df.gif" width="700px" />

**Generate cells with data-aware AI.** データに文脈を持った AI アシスタントでコードを生成したり、ノートブック全体をゼロショットで生成できます。システムプロンプトのカスタマイズや独自 API キーの利用、ローカルモデルの使用にも対応します。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-generate-with-ai.gif" width="700px" />

**Query data with SQL.** Python 値に依存する SQL クエリを組み立て、データフレーム、データベース、CSV、Google Sheets などに対して実行できます。組み込みの SQL エンジンは結果を Python のデータフレームとして返します。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

ノートブックは SQL を使っていても純粋な Python のままです。

**Dynamic markdown.** Python 変数でパラメタライズされた Markdown を使って動的なストーリーを作成できます。

**Built-in package management.** marimo は主要なパッケージマネージャをサポートし、インポート時にパッケージをインストールしたり、ノートブック内に依存関係を埋め込んで再現可能な環境を構築できます。

**Deterministic execution order.** ノートブックの実行順序はセルのページ上の位置ではなく、変数参照に基づいて決定されます。

**Performant runtime.** 静的解析により、実行が必要なセルのみを効率的に実行します。

**Batteries-included.** GitHub Copilot、AI アシスタント、Ruff による整形、HTML 出力、インタラクティブなデータフレームビューア、そして [VS Code 拡張](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo) など、多数の便利機能が含まれています。

## Quickstart

_[marimo の基本的な概念を説明するプレイリスト](https://www.youtube.com/watch?v=3N6lInzq5MI&list=PLNJXGo8e1XT9jP7gPbRdm1XwloZVFvLEq) が公式 YouTube にあります。_

**Installation.** ターミナルで次を実行します。

```bash
pip install marimo  # または conda install -c conda-forge marimo
marimo tutorial intro
```

SQL セルや AI 補完などの追加機能を含めてインストールするには、次を実行します。

```bash
pip install "marimo[recommended]"
```

**Create notebooks.**

ノートブックを作成または編集するには:

```bash
marimo edit
```

**Run apps.** ノートブックを Web アプリとして実行し、Python コードを非表示にして編集不可にできます:

```bash
marimo run your_notebook.py
```

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

**Execute as scripts.** ノートブックをスクリプトとしてコマンドラインから実行できます:

```bash
python your_notebook.py
```

**Automatically convert Jupyter notebooks.** CLI で Jupyter ノートブックを marimo ノートブックに変換できます:

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

または [ウェブインターフェース](https://marimo.io/convert) を使えます。

**Tutorials.**

すべてのチュートリアルを一覧表示するには:

```bash
marimo tutorial --help
```

**Share cloud-based notebooks.**

[molab](https://molab.marimo.io/notebooks) は marimo のクラウドサービスで、ノートブックの共有や実行が可能です。

## Questions?

詳細はドキュメントの [FAQ](https://docs.marimo.io/faq.html) を参照してください。

## Learn more

marimo は導入が簡単で、パワーユーザーにも多くの機能を提供します。例えば、marimo で作られた埋め込み可視化ツールの例があります（[動画](https://marimo.io/videos/landing/full.mp4)）。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/embedding.gif" width="700px" />

詳細は [ドキュメント](https://docs.marimo.io)、[使用例](https://docs.marimo.io/examples/) や [ギャラリー](https://marimo.io/gallery) をご覧ください。

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
      <a target="_blank" href="https://docs.marimo.io/getting_started/key_concepts.html"> Tutorial </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html"> Inputs </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/working_with_data/plotting.html"> Plots </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/layouts/index.html"> Layout </a>
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

## Contributing

貢献を歓迎します。詳しい開始方法は [CONTRIBUTING.md](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md) を参照してください。

> 質問がありますか？[Discord](https://marimo.io/discord?ref=readme) でお問い合わせください。

## Community

コミュニティに参加してください！

- 🌟 [GitHub でスターをつける](https://github.com/marimo-team/marimo)
- 💬 [Discord でチャット](https://marimo.io/discord?ref=readme)
- 📧 [ニュースレターを購読](https://marimo.io/newsletter)
- ☁️ [クラウドウェイトリストに参加](https://marimo.io/cloud)
- ✏️ [GitHub でディスカッションを開始](https://github.com/marimo-team/marimo/discussions)
- 🦋 [Bluesky でフォロー](https://bsky.app/profile/marimo.io)
- 🐦 [Twitter でフォロー](https://twitter.com/marimo_io)
- 🎥 [YouTube で購読](https://www.youtube.com/@marimo-team)
- 🕴️ [LinkedIn でフォロー](https://www.linkedin.com/company/marimo-io)

**A NumFOCUS affiliated project.** marimo は NumFOCUS コミュニティに所属しています。

## インスピレーション ✨

marimo は、エラーが発生しやすい JSON のスクラッチパッドではなく、再現性が高く、インタラクティブで、共有可能な Python プログラムとしての Python ノートブックの**再発明**です。

私たちは、使用するツールが思考のあり方を形作ると信じています — より良いツールは、より良い思考を促します。marimo を通じて、研究とその伝達、コードの実験と共有、計算科学の学習と教育に適した、より良いプログラミング環境を Python コミュニティに提供したいと考えています。

私たちのインスピレーションは多くの場所やプロジェクトから来ています。特に [Pluto.jl](https://github.com/fonsp/Pluto.jl)、[ObservableHQ](https://observablehq.com/tutorials)、および [Bret Victor のエッセイ](http://worrydream.com/) から多くを学びました。marimo はリアクティブなデータフロープログラミングへの大きなムーブメントの一部です。IPyflow、streamlit、TensorFlow、PyTorch、JAX、React といったプロジェクトから、関数型・宣言型・リアクティブプログラミングの考え方が多くのツールをより良く変えているのを見ています。

<p align="right">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-horizontal.png" height="200px">
</p>
