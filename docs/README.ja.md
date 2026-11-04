# Code Review Lifecycle

[English](../README.md) · [简体中文](README.zh-CN.md) · 日本語

**Codex、Claude Code、OpenCode で PR のレビューからリリースまでを支援するスキルです。**

AI が問題を見つけ、修正を再確認します。レビュー担当者は、変更内容、実行したチェック、残っている判断事項をまとめて確認できます。既存の PR から始めることも、受け入れ条件の整理からリリースまで進めることもできます。

Claude Code チームの早期レビュー、レビュー回数の上限、重要なコードの解説を参考にしています。 [Claude Code チームのコードレビュー](https://claude.dev/blog/solving-code-review-at-anthropic/)

## インストールと使い方

Codex では `$code-review-lifecycle`、Claude Code では `/code-review-lifecycle` を使います。OpenCode では `code-review-lifecycle` スキルの読み込みと、レビューしたい内容を依頼します。HTML レンダラーは同梱されており、Node.js 20 以上で動作します。スキル本体と参照資料は主に中国語です。 [インストールと使い方](../README.md#install-and-try-it) · [対応エージェント](../references/agent-support.md)

## レビューの流れ

- **AI レビュー**では差分と関連する呼び出し経路を調べ、問題箇所、発生条件、影響、確認方法を示します。作成者が指摘を確認して修正し、レビュー担当が再確認します。既定では PR ごとに最大 3 回です。3 回目でもマージを妨げる問題が残る場合は、自動修正を止め、原因と次の対応案を示します。 [AI レビューの手順](../references/pr-workflow.md)
- **人によるレビュー**では、動作の変更点、重要なコード、差分全体、実際の検証結果、残るリスクを確認します。承認、修正依頼、保留の判断を対象の PR とコミットにひも付けます。 [人によるレビューの資料](../references/human-review.md)

## 例

たとえば、待機中のエクスポート処理が実行時にアクセス権を再確認しない問題を AI が指摘します。修正後は、権限が取り消された場合にファイルが生成されないことをテストします。利用者に表示するメッセージが十分に分かりやすいかは、人が判断します。 [レビュー例](../README.md#example-review)
