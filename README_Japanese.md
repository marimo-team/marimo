<p align="center">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  <em>再現性が高く、Git対応で、スクリプトやアプリとしても展開できる リアクティブなPythonノートブック。</em>
</p>

<p align="center">
  <a href="https://docs.marimo.io" target="_blank"><strong>ドキュメント</strong></a> ·
  <a href="https://marimo.io/discord?ref=readme" target="_blank"><strong>Discord</strong></a> ·
  <a href="https://github.com/marimo-team/marimo/tree/main/examples" target="_blank"><strong>サンプル</strong></a>
</p>

<p align="center">
  <a href="https://github.com/marimo-team/marimo/blob/main/README.md" target="_blank"><b>English</b></a>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Chinese.md" target="_blank"><b> | 简体中文</b></a>
  <b> | 日本語</b>
</p>

<p align="center">
<a href="https://pypi.org/project/marimo/"><img src="https://img.shields.io/pypi/v/marimo?color=%2334D058&label=pypi" /></a>
<a href="https://anaconda.org/conda-forge/marimo"><img src="https://img.shields.io/conda/vn/conda-forge/marimo.svg"/></a>
<a href="https://github.com/marimo-team/marimo/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo" /></a>
</p>

**marimo**はリアクティブなPythonノートブックです。セルを実行したり、UIエレメントと対話することで、依存するセルが自動的に実行される（または<a href="#expensive-notebooks">古い状態としてマーク</a>される）ため、コードと出力の一貫性が保たれます。marimoノートブックは純粋なPythonとして保存され、スクリプトとして実行したり、アプリケーションとしてデプロイすることができます。

**主な特徴**

- 🚀 **オールインワン:** `jupyter`、`streamlit`、`jupytext`、`ipywidgets`、`papermill`などの代替として
- ⚡️ **リアクティブ:** セルを実行すると、marimoは依存するすべてのセルを[リアクティブに実行](https://docs.marimo.io/guides/reactivity.html)、または<a href="#expensive-notebooks">古い状態としてマーク</a>
- 🖐️ **インタラクティブ:** [スライダー、テーブル、プロットなど](https://docs.marimo.io/guides/interactivity.html)のUI要素をPythonにバインド - コールバック不要
- 🔬 **再現性:** [隠れた状態なし](https://docs.marimo.io/guides/reactivity.html#no-hidden-state)、決定論的な実行、[ビルトインのパッケージ管理](https://docs.marimo.io/guides/editor_features/package_management.html)
- 🏃 **実行可能:** CLIの引数でパラメータ化された[Pythonスクリプトとして実行](https://docs.marimo.io/guides/scripts.html)
- 🛜 **共有可能:** [インタラクティブなWebアプリ](https://docs.marimo.io/guides/apps.html)や[スライド](https://docs.marimo.io/guides/apps.html#slides-layout)としてデプロイ、[WASMでブラウザ上で実行](https://docs.marimo.io/guides/wasm.html)
- 🛢️ **データ処理向け:** [SQL](https://docs.marimo.io/guides/working_with_data/sql.html)でデータフレームやデータベースを照会、[データフレーム](https://docs.marimo.io/guides/working_with_data/dataframes.html)のフィルタリングと検索
- 🐍 **Git対応:** ノートブックは`.py`ファイルとして保存
- ⌨️ **モダンなエディタ:** [GitHub Copilot](https://docs.marimo.io/guides/editor_features/ai_completion.html#github-copilot)、[AIアシスタント](https://docs.marimo.io/guides/editor_features/ai_completion.html#using-ollama)、vimキーバインド、変数エクスプローラーなど[多数の機能](https://docs.marimo.io/guides/editor_features/index.html)

```python
pip install marimo && marimo tutorial intro
```

_[オンラインプレイグラウンド](https://marimo.app/l/c7h6pz)で試してみましょう！完全にブラウザ上で動作します。_

_CLIの基本を学ぶには[クイックスタート](#クイックスタート)へジャンプ。_

## リアクティブなプログラミング環境

marimoは、ノートブックのコード、出力、プログラムの状態の一貫性を保証します。これにより、Jupyterなどの従来のノートブックに関連する[多くの問題](https://docs.marimo.io/faq.html#faq-problems)を解決します。

**リアクティブなプログラミング環境**
セルを実行すると、marimoはその変数を参照するセルを自動的に実行し、セルを手動で再実行するというエラーが起きやすいタスクを排除します。セルを削除すると、marimoはそのセルの変数をプログラムメモリから削除し、隠れた状態を排除します。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/reactive.gif" width="700px" />

<a name="expensive-notebooks"></a>

**重い処理のノートブックにも対応** marimoでは、[ランタイムを遅延実行するように設定](https://docs.marimo.io/guides/configuration/runtime_configuration.html)できます。影響を受けるセルを自動実行する代わりに、古い状態としてマークします。これにより、プログラムの状態を保証しながら、重い処理のセルが誤って実行されることを防ぎます。

**同期されたUI要素** [スライダー](https://docs.marimo.io/api/inputs/slider.html#slider)、[ドロップダウン](https://docs.marimo.io/api/inputs/dropdown.html)、[データフレーム変換](https://docs.marimo.io/api/inputs/dataframe.html)、[チャットインターフェース](https://docs.marimo.io/api/inputs/chat.html)などの[UI要素](https://docs.marimo.io/guides/interactivity.html)と対話すると、それらを使用するセルが最新の値で自動的に再実行されます。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" width="700px" />

**インタラクティブなデータフレーム** 数百万行のデータを高速に[ページング、検索、フィルタリング、ソート](https://docs.marimo.io/guides/working_with_data/dataframes.html)できます。コード不要です。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-df.gif" width="700px" />

**パフォーマンスの高いランタイム** marimoは、コードを静的に分析することで、実行が必要なセルのみを実行します。

**動的なマークダウンとSQL** マークダウンを使用して、Pythonのデータに依存する動的なストーリーを作成できます。または、Pythonの値に依存する[SQL](https://docs.marimo.io/guides/working_with_data/sql.html)クエリを作成し、データフレーム、データベース、CSV、Google Sheets、その他のデータソースに対して実行できます。組み込みのSQLエンジンは結果をPythonデータフレームとして返します。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

マークダウンやSQLを使用していても、ノートブックは純粋なPythonのままです。

**決定論的な実行順序** ノートブックは、セルのページ上の位置ではなく、変数の参照に基づいて決定論的な順序で実行されます。伝えたいストーリーに合わせてノートブックを整理できます。

**ビルトインのパッケージ管理** marimoには、すべての主要なパッケージマネージャーのビルトインサポートがあり、[インポート時にパッケージをインストール](https://docs.marimo.io/guides/editor_features/package_management.html)できます。marimoは[パッケージの依存関係をノートブックファイルにシリアライズ](https://docs.marimo.io/guides/package_reproducibility.html)し、隔離された仮想環境サンドボックスに自動インストールすることもできます。

**オールインワン** marimoには、GitHub Copilot、AIアシスタント、Ruffコードフォーマッティング、HTMLエクスポート、高速なコード補完、[VS Code拡張機能](https://marketplace.visualstudio.com/items?itemname=marimo-team.vscode-marimo)、インタラクティブなデータフレームビューアー、[その他多くの](https://docs.marimo.io/guides/editor_features/index.html)機能が付属しています。

## クイックスタート

**インストール** ターミナルで以下を実行:

```bash
pip install marimo  # または conda install -c conda-forge marimo
marimo tutorial intro
```

**ノートブックの作成**

以下のコマンドでノートブックを作成・編集:

```bash
marimo edit
```

**アプリとして実行** Pythonコードを非表示かつ編集不可の状態でWebアプリとして実行:

```bash
marimo run your_notebook.py
```

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

**スクリプトとして実行** コマンドラインでノートブックをスクリプトとして実行:

```bash
python your_notebook.py
```

**Jupyterノートブックの自動変換** CLIを使用してJupyterノートブックをmarimoノートブックに自動変換:

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

または[Web変換ツール](https://marimo.io/convert)を使用することもできます。

**チュートリアル**
全てのチュートリアルを表示:

```bash
marimo tutorial --help
```

## 質問がありますか？

ドキュメントの[FAQ](https://docs.marimo.io/faq.html)をご覧ください。

## もっと詳しく

marimoは簡単に始められ、パワーユーザーのための機能も豊富です。
例えば、こちらはmarimoで作成した埋め込み可視化ツール
([動画](https://marimo.io/videos/landing/full.mp4))です:

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/embedding.gif" width="700px" />

詳しくは[ドキュメント](https://docs.marimo.io)、[`examples/`](examples/)フォルダ、[ギャラリー](https://marimo.io/gallery)をご覧ください。

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
      <a target="_blank" href="https://docs.marimo.io/getting_started/key_concepts.html">チュートリアル</a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html">入力</a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/working_with_data/plotting.html">プロット</a>
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

## 貢献

すべての貢献を歓迎します！専門家でなくても助けることができます。
[CONTRIBUTING.md](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md) をご覧ください。

> 質問がありますか？ [Discord](https://marimo.io/discord?ref=readme)！ でお問い合わせください。

コミュニティ

私たちはコミュニティを構築しています。ぜひ一緒に交流しましょう！

- 🌟 [GitHubでスターを付ける](https://github.com/marimo-team/marimo)
- 💬 [Discordでチャットする](https://github.com/marimo-team/marimo)
- 📧 [ニュースレターを購読する](https://marimo.io/discord?ref=readme)
- ☁️ [クラウドのウェイトリストに登録する](https://marimo.io/newsletter)
- ✏️ [GitHubディスカッションを開始する](https://marimo.io/cloud)
- 🦋 [Blueskyでフォローする](https://github.com/marimo-team/marimo/discussions)
- 🐦 [Twitterでフォローする](https://twitter.com/marimo_io)
- 🎥 [YouTubeでフォローする](https://www.youtube.com/@marimo-team)
- 🕴️ [LinkedInでフォローする](https://www.linkedin.com/company/marimo-io)

## インスピレーション ✨

marimoは、エラーが発生しやすいJSONのスクラッチパッドではなく、再現可能でインタラクティブかつ共有可能なPythonプログラムとして、Pythonノートブックを再発明したものです。

私たちは、使用するツールが思考の仕方を形作ると信じています。より良いツールは、より良い思考をもたらします。marimoを通じて、Pythonコミュニティに研究を行い、それを伝えるための、コードを試し、共有するための、計算科学を学び、教えるための、より良いプログラミング環境を提供したいと考えています。

私たちのインスピレーションは、
[Pluto.jl](https://github.com/fonsp/Pluto.jl)，
[ObservableHQ](https://observablehq.com/tutorials)，
[Bret Victor's essays](http://worrydream.com/) など、多くの場所やプロジェクトから得ています。
marimoは、リアクティブデータフロープログラミングへの大きな流れの一部です。
[IPyflow](https://github.com/ipyflow/ipyflow)，[streamlit](https://github.com/streamlit/streamlit)，
[TensorFlow](https://github.com/tensorflow/tensorflow)，
[PyTorch](https://github.com/pytorch/pytorch/tree/main)，
[JAX](https://github.com/google/jax)，
[React](https://github.com/facebook/react) など、関数型、宣言型、リアクティブプログラミングのアイデアが、幅広いツールをより良いものへと変革しています。

<p align="right">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-horizontal.png" height="200px">
</p>
