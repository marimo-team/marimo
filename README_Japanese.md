<p align="center">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  <em>再現性が高く、Git対応で、スクリプトやアプリとして展開できるリアクティブなPythonノートブック。</em>

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
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Chinese.md" target="_blank"><b>简体中文</b></a>
  <b> | </b>
  <b>日本語</b>
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

**marimo**はリアクティブなPythonノートブックです：セルを実行したりUI要素を操作すると、marimoは自動的に依存するセルを実行（または<a href="#expensive-notebooks">それらを古いものとしてマーク</a>）し、コードと出力の一貫性を保ちます。marimoノートブックは純粋なPythonとして保存され、スクリプトとして実行でき、アプリとして展開できます。

**主な特徴**

- 🚀 **すぐに使える充実機能**: `jupyter`、`streamlit`、`jupytext`、`ipywidgets`、`papermill`などの代替
- ⚡️ **リアクティブ**: セルを実行すると、marimoはリアクティブに[すべての依存セルを実行](https://docs.marimo.io/guides/reactivity.html)するか、<a href="#expensive-notebooks">それらを古いものとしてマーク</a>
- 🖐️ **インタラクティブ**: [スライダー、テーブル、プロットなど](https://docs.marimo.io/guides/interactivity.html)をPythonにバインド — コールバック不要
- 🔬 **再現性**: [隠れた状態なし](https://docs.marimo.io/guides/reactivity.html#no-hidden-state)、決定論的実行、[組み込みパッケージ管理](https://docs.marimo.io/guides/editor_features/package_management.html)
- 🏃 **実行可能**: [Pythonスクリプトとして実行](https://docs.marimo.io/guides/scripts.html)、CLIの引数によるパラメータ化
- 🛜 **共有可能**: [インタラクティブなWebアプリとして展開](https://docs.marimo.io/guides/apps.html)または[スライド](https://docs.marimo.io/guides/apps.html#slides-layout)、[ブラウザでWASM経由で実行](https://docs.marimo.io/guides/wasm.html)
- 🛢️ **データ向け設計**: [SQL](https://docs.marimo.io/guides/working_with_data/sql.html)でデータフレームやデータベースをクエリ、[データフレーム](https://docs.marimo.io/guides/working_with_data/dataframes.html)のフィルタリングと検索
- 🐍 **Git対応**: ノートブックは`.py`ファイルとして保存
- ⌨️ **モダンなエディタ**: [GitHub Copilot](https://docs.marimo.io/guides/editor_features/ai_completion.html#github-copilot)、[AIアシスタント](https://docs.marimo.io/guides/editor_features/ai_completion.html#using-ollama)、vimキーバインディング、変数エクスプローラー、[その他](https://docs.marimo.io/guides/editor_features/index.html)

```python
pip install marimo && marimo tutorial intro
```

_[オンラインプレイグラウンド](https://marimo.app/l/c7h6pz)でmarimoを試してみてください。完全にブラウザ内で動作します！_

_CLIの基本的な使い方については[クイックスタート](#クイックスタート)をご覧ください。_

## リアクティブなプログラミング環境

marimoはノートブックのコード、出力、プログラムの状態の一貫性を保証します。これにより、Jupyterのような従来のノートブックに関連する[多くの問題](https://docs.marimo.io/faq.html#faq-problems)を解決します。

**リアクティブなプログラミング環境**
セルを実行すると、marimoは_リアクト_し、その変数を参照するセルを自動的に実行することで、手動でセルを再実行するというエラーが起きやすいタスクを排除します。セルを削除すると、marimoはその変数をプログラムのメモリから削除し、隠れた状態を排除します。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/reactive.gif" width="700px" />

<a name="expensive-notebooks"></a>

**計算コストの高いノートブックとの互換性** marimoでは、[ランタイムを遅延評価に設定](https://docs.marimo.io/guides/configuration/runtime_configuration.html)することができ、影響を受けるセルを自動的に実行する代わりに古いものとしてマークします。これにより、プログラムの状態に関する保証を提供しながら、コストの高いセルの偶発的な実行を防ぎます。

**同期されたUI要素** [スライダー](https://docs.marimo.io/api/inputs/slider.html#slider)、[ドロップダウン](https://docs.marimo.io/api/inputs/dropdown.html)、[データフレーム変換](https://docs.marimo.io/api/inputs/dataframe.html)、[チャットインターフェース](https://docs.marimo.io/api/inputs/chat.html)などの[UI要素](https://docs.marimo.io/guides/interactivity.html)を操作すると、それらを使用するセルが自動的に最新の値で再実行されます。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" width="700px" />

**インタラクティブなデータフレーム** 何百万行ものデータを[ページング、検索、フィルタリング、ソート](https://docs.marimo.io/guides/working_with_data/dataframes.html)を、コード不要で驚くほど高速に実行できます。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-df.gif" width="700px" />

**高性能ランタイム** marimoはコードを静的に分析することで、実行が必要なセルのみを実行します。

**動的なマークダウンとSQL** マークダウンを使用して、Pythonデータに依存する動的なストーリーを作成できます。または、Pythonの値に依存する[SQL](https://docs.marimo.io/guides/working_with_data/sql.html)クエリを構築し、データフレーム、データベース、CSV、Google Sheets、またはその他のものに対して実行できます。組み込みのSQLエンジンを使用すると、結果がPythonのデータフレームとして返されます。

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

マークダウンやSQLを使用しても、ノートブックは純粋なPythonのままです。

**決定論的な実行順序** ノートブックは、セルのページ上の位置ではなく、変数の参照に基づいて決定論的な順序で実行されます。伝えたいストーリーに最適な方法でノートブックを整理できます。

**組み込みパッケージ管理** marimoには主要なパッケージマネージャーのサポートが組み込まれており、[インポート時にパッケージをインストール](https://docs.marimo.io/guides/editor_features/package_management.html)できます。marimoは[パッケージの要件をシリアル化](https://docs.marimo.io/guides/package_reproducibility.html)してノートブックファイルに保存し、隔離されたvenv環境に自動的にインストールすることもできます。

**必要な機能がすべて揃っている** marimoにはGitHub Copilot、AIアシスタント、Ruffコードフォーマット、HTML出力、高速コード補完、[VS Code拡張機能](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo)、インタラクティブなデータフレームビューワー、[その他多くの](https://docs.marimo.io/guides/editor_features/index.html)便利な機能が含まれています。

## クイックスタート

**インストール** ターミナルで次を実行します：

```bash
pip install marimo  # または conda install -c conda-forge marimo
marimo tutorial intro
```

SQL セル、AI 補完などの追加機能を含めてインストールするには、次を実行します：

```bash
pip install marimo[recommended]
```

**ノートブックの作成**

次のコマンドでノートブックを作成または編集します：

```bash
marimo edit
```

**アプリの実行** ノートブックをウェブアプリとして実行し、Pythonコードを非表示かつ編集不可にします：

```bash
marimo run your_notebook.py
```

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

**スクリプトとして実行** ノートブックをコマンドラインでスクリプトとして実行します：

```bash
python your_notebook.py
```

**Jupyterノートブックの自動変換** CLIを使用してJupyterノートブックをmarimoノートブックに自動変換します：

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

または[ウェブインターフェース](https://marimo.io/convert)を使用します。

**チュートリアル**
すべてのチュートリアルをリストします：

```bash
marimo tutorial --help
```

## 質問がありますか？

[FAQ](https://docs.marimo.io/faq.html)をご覧ください。

## もっと詳しく

marimoは簡単に始められ、パワーユーザー向けの多くの機能があります。
例えば、marimoで作成された埋め込み可視化ツールです
([動画](https://marimo.io/videos/landing/full.mp4))：

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/embedding.gif" width="700px" />

詳細については、[ドキュメント](https://docs.marimo.io)、[使用例](https://docs.marimo.io/examples/)、[ギャラリー](https://marimo.io/gallery)をご覧ください。

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
      <a target="_blank" href="https://docs.marimo.io/getting_started/key_concepts.html"> チュートリアル </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html"> 入力 </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/working_with_data/plotting.html"> プロット </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/layouts/index.html"> レイアウト </a>
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

## コントリビューション

すべての貢献を歓迎します！専門家である必要はありません。
開始方法の詳細については、[CONTRIBUTING.md](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md)をご覧ください。

> 質問がありますか？[Discord](https://marimo.io/discord?ref=readme)でお問い合わせください。

## コミュニティ

コミュニティを構築中です。ぜひ参加してください！

- 🌟 [GitHubでスターをつける](https://github.com/marimo-team/marimo)
- 💬 [Discordでチャット](https://marimo.io/discord?ref=readme)
- 📧 [ニュースレターを購読](https://marimo.io/newsletter)
- ☁️ [クラウドウェイトリストに参加](https://marimo.io/cloud)
- ✏️ [GitHubでディスカッションを開始](https://github.com/marimo-team/marimo/discussions)
- 🦋 [Blueskyでフォロー](https://bsky.app/profile/marimo.io)
- 🐦 [Twitterでフォロー](https://twitter.com/marimo_io)
- 🎥 [YouTubeで購読](https://www.youtube.com/@marimo-team)
- 🕴️ [LinkedInでフォロー](https://www.linkedin.com/company/marimo-io)

## インスピレーション ✨

marimoは、エラーが発生しやすいJSONのスクラッチパッドではなく、再現性が高く、インタラクティブで、共有可能なPythonプログラムとしてのPythonノートブックの**再発明**です。

私たちは、使用するツールが私たちの思考方法を形作ると信じています—より良いツールが、より良い思考をもたらします。marimoを通じて、研究を行い、それを伝えるため、コードを実験し、それを共有するため、計算科学を学び、それを教えるために、Pythonコミュニティにより良いプログラミング環境を提供したいと考えています。

私たちのインスピレーションは多くの場所やプロジェクト、特に[Pluto.jl](https://github.com/fonsp/Pluto.jl)、[ObservableHQ](https://observablehq.com/tutorials)、[Bret Victorのエッセイ](http://worrydream.com/)から来ています。marimoはリアクティブなデータフロープログラミングへの大きな動きの一部です。[IPyflow](https://github.com/ipyflow/ipyflow)、[streamlit](https://github.com/streamlit/streamlit)、[TensorFlow](https://github.com/tensorflow/tensorflow)、[PyTorch](https://github.com/pytorch/pytorch/tree/main)、[JAX](https://github.com/google/jax)、[React](https://github.com/facebook/react)から、関数型、宣言型、リアクティブプログラミングの考え方が広範囲のツールを良い方向に変革しています。

<p align="right">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-horizontal.png" height="200px">
</p>
