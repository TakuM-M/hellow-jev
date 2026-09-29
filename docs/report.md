## log_classification

| model | n | Acc | Macro-F1 | エラー率 | p50 ms | p95 ms | サーバ p50 ms | 入力tok/件 | コスト/1万件 | 実行環境 | run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| jev | 16 | 0.938 | 0.943 | 0.000 | 158.5 | 188.4 | - | 476 | $0.1999 | API (TypeSafe) | 20260928T102407Z_jev |
| laya | 16 | 0.875 | 0.876 | 0.000 | 155.2 | 176.1 | 153.2 | 146 | $0 | Apple M1 (8GB), mps | 20260928T102440Z_laya |
| llm_api<br>claude-haiku-4-5-20251001 | 16 | 1.000 | 1.000 | 0.000 | 913.8 | 1220.1 | - | 373 | $4.1825 | API (Anthropic) | 20260929T080714Z_llm_api |
| llm_local<br>qwen3:4b-instruct | 16 | 0.938 | 0.943 | 0.000 | 546.0 | 669.7 | - | 179 | $0 | Apple M1 (8GB) | 20260929T080735Z_llm_local |

- ⚠️ プロンプトが run 間で異なる（同一条件の比較になっていない）
- ⚠️ コード（git commit）が run 間で異なる（同一条件の比較になっていない）
- ⚠️ 未コミットの変更がある状態で実行: llm_api, llm_local

### 誤り分析

#### 誤った件

いずれかのモデルが間違えた件。間違えたモデル数の多い順（上限 20 件）。セルは予測ラベル（✓ は正解）。確率が取れるモデルは（予測の確率 / 正解の確率）を併記。

| id | テキスト | 正解 | jev | laya | llm_api | llm_local |
| --- | --- | --- | --- | --- | --- | --- |
| s003 | 2026-09-01T10:05:02Z INFO auth-svc login success user=u_8812 | normal | auth (0.94 / 0.06) | auth (0.91 / 0.08) | ✓ | auth |
| s010 | 2026-09-01T10:11:42Z WARN api-gw upstream timeout after 30000ms path=/api/checkout | performance | ✓ | normal (0.36 / 0.33) | ✓ | ✓ |

#### 混同ペア

正解 → 予測の組ごとの件数（全モデル合計の多い順、上限 10 組）。

| 正解 → 予測 | 件数 | モデル別 |
| --- | --- | --- |
| normal → auth | 3 | jev 1, laya 1, llm_local 1 |
| performance → normal | 1 | laya 1 |

#### 予測ラベルの確率（確率を返すモデルのみ）

| model | 正解時 n | 正解時 中央値 | 正解時 最小 | 誤り時 n | 誤り時 中央値 | 誤り時 最大 |
| --- | --- | --- | --- | --- | --- | --- |
| jev | 15 | 1.00 | 0.85 | 1 | 0.94 | 0.94 |
| laya | 14 | 0.88 | 0.48 | 2 | 0.63 | 0.91 |

#### 自信の低い判定を人に回した場合

「確率が閾値未満の判定は自動で処理せず、人が見直す（保留）」という運用を想定した試算。

- 保留率: 人に回った件の割合（人の手間）
- 自動処理分 Acc: 人に回さなかった件だけで数えた正解率
- 少ない保留率で Acc が上がるほど、確率が誤りを見つける手がかりとして役立っている。

| model | 閾値 0.5 保留率 | 閾値 0.5 自動処理分 Acc | 閾値 0.9 保留率 | 閾値 0.9 自動処理分 Acc |
| --- | --- | --- | --- | --- |
| jev | 0.000 | 0.938 | 0.062 | 0.933 |
| laya | 0.125 | 0.929 | 0.562 | 0.857 |

## jevbench_agnews

| model | n | Acc | Macro-F1 | エラー率 | p50 ms | p95 ms | サーバ p50 ms | 入力tok/件 | コスト/1万件 | 実行環境 | run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| jev | 500 | 0.844 | 0.844 | 0.000 | 169.0 | 216.9 | - | 439 | $0.1843 | API (TypeSafe) | 20260929T053713Z_jev |
| laya | 500 | 0.906 | 0.907 | 0.000 | 140.7 | 166.9 | 138.4 | 137 | $0 | Apple M1 (8GB), mps | 20260929T054550Z_laya |
| llm_local<br>qwen3:4b-instruct | 500 | 0.784 | 0.787 | 0.000 | 990.1 | 1408.9 | - | 165 | $0 | Apple M1 (8GB) | 20260929T082000Z_llm_local |
| llm_api<br>claude-haiku-4-5-20251001 | 500 | 0.832 | 0.831 | 0.000 | 749.1 | 1113.4 | - | 343 | $3.8943 | API (Anthropic) | 20260929T082101Z_llm_api |
| [jevbench] jev (typesafe/jev-1.13) | - | 0.843 | 0.842 | 0.004 | 381.0 | 715.0 | - | - | $0.1840 | - | 参考値 |
| [jevbench] laya (convaiinnovations/laya) | - | 0.906 | 0.907 | 0.000 | 59.0 | 68.0 | - | - | - | - | 参考値 |
| [jevbench] llm-frontier (anthropic/claude-sonnet-5) | - | 0.896 | 0.896 | 0.000 | 2014.0 | 2354.0 | - | - | $10.4080 | - | 参考値 |
| [jevbench] llm-cheap (openai/gpt-5-mini) | - | 0.802 | 0.802 | 0.000 | 1312.0 | 1887.0 | - | - | $1.0140 | - | 参考値 |
| [jevbench] bert-ft (distilbert-base-uncased) | - | 0.910 | 0.911 | 0.000 | 6.0 | 10.0 | - | - | - | - | 参考値 |
| [jevbench] bert-zs (facebook/bart-large-mnli) | - | 0.764 | 0.760 | 0.000 | 156.0 | 193.0 | - | - | - | - | 参考値 |

- 参考値は [jevbench](https://github.com/dhruvmehra/jevbench/blob/c983cc4/docs/results/2026-09-22-n500-summary.md) の公開結果。jevbench 公表値（n=500, seed=0, 旧ラベル説明）。Acc はエラー件を除外（本リポジトリは不正解扱い）。Jev・LLM のレイテンシは OpenRouter 経由。スループットは並列計測のため省略
- ⚠️ タスク定義（instructions・ラベル説明）が run 間で異なる（同一条件の比較になっていない）
- ⚠️ プロンプトが run 間で異なる（同一条件の比較になっていない）
- ⚠️ コード（git commit）が run 間で異なる（同一条件の比較になっていない）
- ⚠️ 未コミットの変更がある状態で実行: laya

### 誤り分析

#### 誤った件

いずれかのモデルが間違えた件。間違えたモデル数の多い順（上限 20 件）。セルは予測ラベル（✓ は正解）。確率が取れるモデルは（予測の確率 / 正解の確率）を併記。

| id | テキスト | 正解 | jev | laya | llm_local | llm_api |
| --- | --- | --- | --- | --- | --- | --- |
| agnews-2234 | Spread of GM grass raises fears of crossbreeding Pollen from a genetically modified grass was found 21 kilometres from … | business | sci_tech (1.00 / 0.00) | sci_tech (0.74 / 0.08) | sci_tech | sci_tech |
| agnews-4000 | Google puts desktop search privacy up front Google has announced a new desktop search application that enables users to… | business | sci_tech (1.00 / 0.00) | sci_tech (0.84 / 0.10) | sci_tech | sci_tech |
| agnews-5740 | Dow Jones Agrees to Buy MarketWatch in \$519 Million Deal Dow Jones Company, the publisher of The Wall Street Journal, … | world | business (1.00 / 0.00) | business (0.64 / 0.06) | business | business |
| agnews-4097 | Greenspan: Debt, home prices not dangerous The record level of debt carried by American households and soaring home pri… | sci_tech | business (1.00 / 0.00) | business (0.91 / 0.02) | business | business |
| agnews-2333 | Rumours surround Google browser The search giant Google is rumoured to be working on its own web browser. | business | sci_tech (1.00 / 0.00) | sci_tech (0.78 / 0.12) | sci_tech | sci_tech |
| agnews-3116 | OPM Delving Deeper Into Employees #39; Backgrounds which sets hiring and employment standards for the government -- is … | sci_tech | world (0.95 / 0.00) | business (0.37 / 0.22) | world | world |
| agnews-6089 | Football: Brazil legend's UK debut Brazil football great Socrates is set to make his debut for non-league Garforth Town… | world | sports (1.00 / 0.00) | sports (0.94 / 0.04) | sports | sports |
| agnews-7461 | Clarke takes charge of Blunkett's Fear Agenda &lt;strong&gt;Analysis&lt;/strong&gt; Horizontal drinkers rejoice | sci_tech | world (0.89 / 0.05) | world (0.32 / 0.23) | world | world |
| agnews-3077 | Brewers buyer expected to step out of the shadows Monday MILWAUKEE - Paul Attanasio says the story of his brother buyin… | business | sports (0.85 / 0.15) | sports (0.94 / 0.03) | sports | sports |
| agnews-4275 | Erdogan Believes European Council #39;s Decision Will Be A Milestone PARIS - Turkish PM Recep Tayyip Erdogan expressed … | business | world (1.00 / 0.00) | world (0.62 / 0.25) | world | world |
| agnews-6006 | Russia #39;s Putin Defends Reforms, Worries About Clans Russian President Vladimir Putin said on Thursday he had no pla… | business | world (1.00 / 0.00) | world (0.75 / 0.15) | world | world |
| agnews-614 | Pakistan down India to ensure top six finish (AFP) AFP - Pakistan defeated arch-rivals India 3-0 here to ensure they st… | world | sports (1.00 / 0.00) | sports (0.48 / 0.45) | sports | sports |
| agnews-2752 | BlueGene sneaks past Earth Simulator The Earth Simulator, an NEC supercomputer, is surpassed, at last. IBM announced ye… | business | sci_tech (1.00 / 0.00) | sci_tech (0.82 / 0.12) | sci_tech | sci_tech |
| agnews-2028 | Ryder Cup: Europe close on victory Another good day at Oakland Hills sees Europe move 11-5 clear of the USA going into … | world | sports (1.00 / 0.00) | sports (0.95 / 0.03) | sports | sports |
| agnews-1494 | Telescope snaps distant 'planet' The first direct image of a planet circling another star may have been obtained by a U… | world | sci_tech (1.00 / 0.00) | sci_tech (0.70 / 0.18) | sci_tech | sci_tech |
| agnews-6936 | China's Lenovo to buy IBM's PC business TOKYO - China's Lenovo Group Ltd. signed a definitive agreement on Wednesday to… | sci_tech | business (1.00 / 0.00) | business (0.85 / 0.08) | business | business |
| agnews-5145 | Serial HIV Assault Verdict Expected Mon. (AP) AP - A verdict will be announced Monday in the trial of a man charged wit… | sci_tech | world (0.96 / 0.04) | world (0.54 / 0.36) | world | world |
| agnews-4844 | Voters Checking Out Other Sides' Sites Are right-leaning voters spending all their online time on Rushlimbaugh.com? Are… | sci_tech | world (0.84 / 0.16) | world (0.47 / 0.37) | world | world |
| agnews-5886 | Producer Price Surge Fuels Inflation Fears Producer prices surged 1.7 percent in October, their sharpest monthly increa… | world | business (1.00 / 0.00) | business (0.81 / 0.13) | business | business |
| agnews-1447 | Florida Starts To Recover in the Wake of Hurricane Frances President Bush will travel to Florida Wednesday to survey da… | sci_tech | world (0.99 / 0.00) | world (0.45 / 0.19) | world | world |

他 134 件（全件は results/<run>/predictions.jsonl）

#### 混同ペア

正解 → 予測の組ごとの件数（全モデル合計の多い順、上限 10 組）。

| 正解 → 予測 | 件数 | モデル別 |
| --- | --- | --- |
| sci_tech → business | 92 | jev 27, laya 4, llm_local 23, llm_api 38 |
| sci_tech → world | 60 | jev 16, laya 4, llm_local 24, llm_api 16 |
| business → world | 44 | jev 10, laya 4, llm_local 23, llm_api 7 |
| business → sci_tech | 40 | jev 8, laya 17, llm_local 9, llm_api 6 |
| world → business | 21 | jev 7, laya 4, llm_local 3, llm_api 7 |
| world → sports | 21 | jev 6, laya 3, llm_local 6, llm_api 6 |
| sports → world | 20 | jev 1, laya 3, llm_local 16 |
| world → sci_tech | 12 | jev 2, laya 6, llm_local 2, llm_api 2 |
| business → sports | 4 | jev 1, laya 1, llm_local 1, llm_api 1 |
| sports → business | 3 | laya 1, llm_local 1, llm_api 1 |

#### 予測ラベルの確率（確率を返すモデルのみ）

| model | 正解時 n | 正解時 中央値 | 正解時 最小 | 誤り時 n | 誤り時 中央値 | 誤り時 最大 |
| --- | --- | --- | --- | --- | --- | --- |
| jev | 422 | 1.00 | 0.51 | 78 | 0.93 | 1.00 |
| laya | 453 | 0.92 | 0.32 | 47 | 0.66 | 0.96 |

#### 自信の低い判定を人に回した場合

「確率が閾値未満の判定は自動で処理せず、人が見直す（保留）」という運用を想定した試算。

- 保留率: 人に回った件の割合（人の手間）
- 自動処理分 Acc: 人に回さなかった件だけで数えた正解率
- 少ない保留率で Acc が上がるほど、確率が誤りを見つける手がかりとして役立っている。

| model | 閾値 0.5 保留率 | 閾値 0.5 自動処理分 Acc | 閾値 0.9 保留率 | 閾値 0.9 自動処理分 Acc |
| --- | --- | --- | --- | --- |
| jev | 0.000 | 0.844 | 0.136 | 0.903 |
| laya | 0.034 | 0.925 | 0.452 | 0.974 |

## jevbench_agnews_v2

| model | n | Acc | Macro-F1 | エラー率 | p50 ms | p95 ms | サーバ p50 ms | 入力tok/件 | コスト/1万件 | 実行環境 | run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| jev | 500 | 0.856 | 0.857 | 0.000 | 164.6 | 216.8 | - | 510 | $0.2142 | API (TypeSafe) | 20260929T053841Z_jev |
| laya | 500 | 0.862 | 0.864 | 0.000 | 177.9 | 203.6 | 175.2 | 204 | $0 | Apple M1 (8GB), mps | 20260929T054659Z_laya |
| llm_api<br>claude-haiku-4-5-20251001 | 500 | 0.850 | 0.851 | 0.000 | 768.4 | 1169.2 | - | 419 | $4.6611 | API (Anthropic) | 20260929T082747Z_llm_api |
| llm_local<br>qwen3:4b-instruct | 500 | 0.766 | 0.771 | 0.000 | 954.0 | 1495.1 | - | 236 | $0 | Apple M1 (8GB) | 20260929T082820Z_llm_local |
| [jevbench] jev (typesafe/jev-1.13) | - | 0.858 | 0.859 | 0.000 | 378.0 | 648.0 | - | - | $0.2140 | - | 参考値 |

- 参考値は [jevbench](https://github.com/dhruvmehra/jevbench/blob/c983cc4/docs/results/2026-09-22-n500-summary.md) の公開結果。jevbench 公表値の jev (new descriptions) 行（n=500, seed=0, 新ラベル説明）。Acc はエラー件を除外（本リポジトリは不正解扱い）。Jev・LLM のレイテンシは OpenRouter 経由。スループットは並列計測のため省略
- ⚠️ タスク定義（instructions・ラベル説明）が run 間で異なる（同一条件の比較になっていない）
- ⚠️ プロンプトが run 間で異なる（同一条件の比較になっていない）
- ⚠️ コード（git commit）が run 間で異なる（同一条件の比較になっていない）
- ⚠️ 未コミットの変更がある状態で実行: laya

### 誤り分析

#### 誤った件

いずれかのモデルが間違えた件。間違えたモデル数の多い順（上限 20 件）。セルは予測ラベル（✓ は正解）。確率が取れるモデルは（予測の確率 / 正解の確率）を併記。

| id | テキスト | 正解 | jev | laya | llm_api | llm_local |
| --- | --- | --- | --- | --- | --- | --- |
| agnews-6117 | Big Dig Tunnel Is Riddled With Leaks In a burgeoning political and engineering scandal, Boston #39;s gleaming new under… | business | world (0.85 / 0.11) | sci_tech (0.51 / 0.30) | world | world |
| agnews-2234 | Spread of GM grass raises fears of crossbreeding Pollen from a genetically modified grass was found 21 kilometres from … | business | sci_tech (1.00 / 0.00) | sci_tech (0.71 / 0.14) | sci_tech | sci_tech |
| agnews-6576 | Toshiba claims Hollywood backing in war for next DVD standard (AFP) AFP - Toshiba said four major Hollywood studios had… | world | sci_tech (1.00 / 0.00) | sci_tech (0.81 / 0.13) | sci_tech | sci_tech |
| agnews-4000 | Google puts desktop search privacy up front Google has announced a new desktop search application that enables users to… | business | sci_tech (1.00 / 0.00) | sci_tech (0.86 / 0.09) | sci_tech | sci_tech |
| agnews-5740 | Dow Jones Agrees to Buy MarketWatch in \$519 Million Deal Dow Jones Company, the publisher of The Wall Street Journal, … | world | business (1.00 / 0.00) | sci_tech (0.71 / 0.05) | business | business |
| agnews-4097 | Greenspan: Debt, home prices not dangerous The record level of debt carried by American households and soaring home pri… | sci_tech | business (1.00 / 0.00) | business (0.81 / 0.10) | business | world |
| agnews-2333 | Rumours surround Google browser The search giant Google is rumoured to be working on its own web browser. | business | sci_tech (1.00 / 0.00) | sci_tech (0.76 / 0.13) | sci_tech | sci_tech |
| agnews-6089 | Football: Brazil legend's UK debut Brazil football great Socrates is set to make his debut for non-league Garforth Town… | world | sports (1.00 / 0.00) | sports (0.54 / 0.17) | sports | sports |
| agnews-5839 | Google shares released for sale Employees and some investors in Google will be able to sell shares in the company as th… | business | sci_tech (0.77 / 0.23) | sci_tech (0.68 / 0.17) | sci_tech | sci_tech |
| agnews-3077 | Brewers buyer expected to step out of the shadows Monday MILWAUKEE - Paul Attanasio says the story of his brother buyin… | business | sports (0.92 / 0.08) | sports (0.89 / 0.05) | sports | sports |
| agnews-2759 | Telecom equipment maker Agere to cut 500 employees, 7.6 of &lt;b&gt;...&lt;/b&gt; Telecommunications equipment maker Ag… | business | sci_tech (0.96 / 0.04) | sci_tech (0.53 / 0.41) | sci_tech | sci_tech |
| agnews-4275 | Erdogan Believes European Council #39;s Decision Will Be A Milestone PARIS - Turkish PM Recep Tayyip Erdogan expressed … | business | world (1.00 / 0.00) | world (0.38 / 0.33) | world | world |
| agnews-6006 | Russia #39;s Putin Defends Reforms, Worries About Clans Russian President Vladimir Putin said on Thursday he had no pla… | business | world (1.00 / 0.00) | world (0.38 / 0.30) | world | world |
| agnews-2752 | BlueGene sneaks past Earth Simulator The Earth Simulator, an NEC supercomputer, is surpassed, at last. IBM announced ye… | business | sci_tech (1.00 / 0.00) | sci_tech (0.84 / 0.09) | sci_tech | sci_tech |
| agnews-2028 | Ryder Cup: Europe close on victory Another good day at Oakland Hills sees Europe move 11-5 clear of the USA going into … | world | sports (1.00 / 0.00) | sports (0.74 / 0.06) | sports | sports |
| agnews-1494 | Telescope snaps distant 'planet' The first direct image of a planet circling another star may have been obtained by a U… | world | sci_tech (1.00 / 0.00) | sci_tech (0.59 / 0.13) | sci_tech | sci_tech |
| agnews-5145 | Serial HIV Assault Verdict Expected Mon. (AP) AP - A verdict will be announced Monday in the trial of a man charged wit… | sci_tech | world (1.00 / 0.00) | world (0.42 / 0.42) | world | world |
| agnews-4571 | Microsoft Readies Next Business IM Server A little over a year after introducing the first version of Office Live Commu… | business | sci_tech (1.00 / 0.00) | sci_tech (0.84 / 0.09) | sci_tech | sci_tech |
| agnews-877 | For Now, Unwired Means Unlisted. That May Change. In October, most major cellphone carriers plan to start compiling a p… | business | sci_tech (0.99 / 0.01) | sci_tech (0.86 / 0.08) | sci_tech | sci_tech |
| agnews-930 | Iraqi oil exports slump: report NEAR daily attacks on pipelines and pumping stations had pushed down Iraq #39;s oil exp… | world | business (0.99 / 0.01) | business (0.38 / 0.33) | business | business |

他 149 件（全件は results/<run>/predictions.jsonl）

#### 混同ペア

正解 → 予測の組ごとの件数（全モデル合計の多い順、上限 10 組）。

| 正解 → 予測 | 件数 | モデル別 |
| --- | --- | --- |
| business → sci_tech | 94 | jev 29, laya 32, llm_api 18, llm_local 15 |
| sci_tech → world | 57 | jev 15, laya 1, llm_api 16, llm_local 25 |
| sci_tech → business | 38 | jev 4, laya 2, llm_api 18, llm_local 14 |
| business → world | 34 | jev 6, laya 2, llm_api 4, llm_local 22 |
| world → sci_tech | 33 | jev 4, laya 21, llm_api 4, llm_local 4 |
| sports → world | 28 | jev 1, laya 2, llm_api 1, llm_local 24 |
| world → business | 21 | jev 6, laya 4, llm_api 6, llm_local 5 |
| world → sports | 20 | jev 6, laya 2, llm_api 6, llm_local 6 |
| business → sports | 4 | jev 1, laya 1, llm_api 1, llm_local 1 |
| sports → business | 3 | laya 1, llm_api 1, llm_local 1 |

他 1 組

#### 予測ラベルの確率（確率を返すモデルのみ）

| model | 正解時 n | 正解時 中央値 | 正解時 最小 | 誤り時 n | 誤り時 中央値 | 誤り時 最大 |
| --- | --- | --- | --- | --- | --- | --- |
| jev | 428 | 1.00 | 0.52 | 72 | 0.94 | 1.00 |
| laya | 431 | 0.81 | 0.31 | 69 | 0.53 | 0.91 |

#### 自信の低い判定を人に回した場合

「確率が閾値未満の判定は自動で処理せず、人が見直す（保留）」という運用を想定した試算。

- 保留率: 人に回った件の割合（人の手間）
- 自動処理分 Acc: 人に回さなかった件だけで数えた正解率
- 少ない保留率で Acc が上がるほど、確率が誤りを見つける手がかりとして役立っている。

| model | 閾値 0.5 保留率 | 閾値 0.5 自動処理分 Acc | 閾値 0.9 保留率 | 閾値 0.9 自動処理分 Acc |
| --- | --- | --- | --- | --- |
| jev | 0.000 | 0.856 | 0.120 | 0.905 |
| laya | 0.114 | 0.907 | 0.774 | 0.991 |

## jevbench_banking77

| model | n | Acc | Macro-F1 | エラー率 | p50 ms | p95 ms | サーバ p50 ms | 入力tok/件 | コスト/1万件 | 実行環境 | run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| jev | 500 | 0.768 | 0.758 | 0.000 | 175.4 | 233.5 | - | 1979 | $0.8312 | API (TypeSafe) | 20260929T054008Z_jev |
| laya | 500 | 0.382 | 0.321 | 0.000 | 279.1 | 317.0 | 275.8 | 332 | $0 | Apple M1 (8GB), mps | 20260929T054830Z_laya |
| llm_api<br>claude-haiku-4-5-20251001 | 500 | 0.758 | 0.750 | 0.000 | 820.3 | 1246.1 | - | 2222 | $22.8837 | API (Anthropic) | 20260929T083449Z_llm_api |
| llm_local<br>qwen3:4b-instruct | 500 | 0.662 | 0.643 | 0.000 | 1416.1 | 2045.9 | - | 1149 | $0 | Apple M1 (8GB) | 20260929T083656Z_llm_local |
| [jevbench] jev (typesafe/jev-1.13) | - | 0.764 | 0.753 | 0.000 | 389.0 | 676.0 | - | - | $0.8310 | - | 参考値 |
| [jevbench] laya (convaiinnovations/laya) | - | 0.382 | 0.321 | 0.000 | 130.0 | 137.0 | - | - | - | - | 参考値 |
| [jevbench] llm-frontier (anthropic/claude-sonnet-5) | - | 0.774 | 0.767 | 0.000 | 1995.0 | 2634.0 | - | - | $64.3290 | - | 参考値 |
| [jevbench] llm-cheap (openai/gpt-5-mini) | - | 0.736 | 0.733 | 0.000 | 1312.0 | 1989.0 | - | - | $3.7580 | - | 参考値 |
| [jevbench] bert-ft (distilbert-base-uncased) | - | 0.880 | 0.864 | 0.000 | 8.0 | 13.0 | - | - | - | - | 参考値 |
| [jevbench] bert-zs (facebook/bart-large-mnli) | - | 0.428 | 0.397 | 0.000 | 2571.0 | 3029.0 | - | - | - | - | 参考値 |

- 参考値は [jevbench](https://github.com/dhruvmehra/jevbench/blob/c983cc4/docs/results/2026-09-22-n500-summary.md) の公開結果。jevbench 公表値（n=500, seed=0）。Acc はエラー件を除外（本リポジトリは不正解扱い）。Jev・LLM のレイテンシは OpenRouter 経由。スループットは並列計測のため省略
- ⚠️ タスク定義（instructions・ラベル説明）が run 間で異なる（同一条件の比較になっていない）
- ⚠️ プロンプトが run 間で異なる（同一条件の比較になっていない）
- ⚠️ コード（git commit）が run 間で異なる（同一条件の比較になっていない）
- ⚠️ 未コミットの変更がある状態で実行: laya

### 誤り分析

#### 誤った件

いずれかのモデルが間違えた件。間違えたモデル数の多い順（上限 20 件）。セルは予測ラベル（✓ は正解）。確率が取れるモデルは（予測の確率 / 正解の確率）を併記。

| id | テキスト | 正解 | jev | laya | llm_api | llm_local |
| --- | --- | --- | --- | --- | --- | --- |
| banking77-1272 | Help me find my card pin! | get_physical_card | change_pin (0.60 / 0.00) | pin_blocked (0.98 / 0.00) | passcode_forgotten | passcode_forgotten |
| banking77-1334 | I have friends that would like to top-up my account is that possible? | topping_up_by_card | receiving_money (0.41 / 0.32) | top_up_reverted (0.94 / 0.00) | receiving_money | top_up_by_card_charge |
| banking77-1243 | Are PIN separately? | get_physical_card | change_pin (0.72 / 0.02) | pending_top_up (0.07 / 0.02) | change_pin | change_pin |
| banking77-887 | If I only have 1 other US card, can you take it? | supported_cards_and_currencies | topping_up_by_card (0.38 / 0.15) | disposable_card_limits (0.47 / 0.27) | card_linking | visa_or_mastercard |
| banking77-377 | My card was declined today when eating and I need to know what's wrong. | card_not_working | declined_card_payment (1.00 / 0.00) | declined_card_payment (1.00 / 0.00) | declined_card_payment | declined_card_payment |
| banking77-622 | How much am I charged for a SEPA transfer? | top_up_by_bank_transfer_charge | transfer_fee_charged (0.98 / 0.02) | transfer_fee_charged (1.00 / 0.00) | transfer_fee_charged | transfer_fee_charged |
| banking77-1080 | I have a strange payment in my statement | card_payment_not_recognised | extra_charge_on_statement (0.59 / 0.40) | wrong_exchange_rate_for_cash_withdrawal (0.57 / 0.00) | extra_charge_on_statement | transaction_charged_twice |
| banking77-2694 | I made an out of country transfer and it hasn't went through yet. | balance_not_updated_after_bank_transfer | pending_transfer (0.88 / 0.00) | failed_transfer (0.97 / 0.00) | pending_transfer | transfer_not_received_by_recipient |
| banking77-2988 | I got my American Express in Apple Bay but top up is not working | apple_pay_or_google_pay | top_up_failed (0.95 / 0.00) | top_up_reverted (0.84 / 0.00) | top_up_failed | card_not_working |
| banking77-1356 | I topped up my card but the money disappeared. | topping_up_by_card | top_up_failed (0.71 / 0.03) | top_up_reverted (0.56 / 0.10) | top_up_reverted | top_up_reverted |
| banking77-2103 | Why was my card payment cancelled? | reverted_card_payment | declined_card_payment (0.91 / 0.09) | declined_transfer (0.99 / 0.00) | cancel_transfer | declined_card_payment |
| banking77-812 | im not sure what this charge is for | card_payment_fee_charged | extra_charge_on_statement (0.70 / 0.00) | extra_charge_on_statement (1.00 / 0.00) | extra_charge_on_statement | exchange_charge |
| banking77-1296 | Am I allowed to use any card to make a payment? | visa_or_mastercard | card_acceptance (0.72 / 0.01) | supported_cards_and_currencies (1.00 / 0.00) | card_acceptance | supported_cards_and_currencies |
| banking77-2252 | Is GBP a supported currency? | receiving_money | fiat_currency_support (0.63 / 0.00) | country_support (0.91 / 0.00) | fiat_currency_support | fiat_currency_support |
| banking77-1358 | Why can't I see the top-up amount I just added to my account? | topping_up_by_card | pending_top_up (0.92 / 0.02) | top_up_reverted (1.00 / 0.00) | pending_top_up | balance_not_updated_after_bank_transfer |
| banking77-1054 | I have paid money into my account but it doesn't show. | balance_not_updated_after_cheque_or_cash_deposit | balance_not_updated_after_bank_transfer (0.56 / 0.01) | declined_transfer (0.54 / 0.00) | balance_not_updated_after_bank_transfer | balance_not_updated_after_bank_transfer |
| banking77-650 | I topped up but it didn't complete | pending_top_up | top_up_failed (0.89 / 0.11) | top_up_reverted (0.90 / 0.00) | top_up_failed | top_up_failed |
| banking77-1171 | Can I still use my account, even though the identity verification has not passed yet? | why_verify_identity | unable_to_verify_identity (0.94 / 0.00) | pending_top_up (0.75 / 0.00) | unable_to_verify_identity | unable_to_verify_identity |
| banking77-1734 | How do I contact customer support about a transfer? | declined_transfer | pending_transfer (0.33 / 0.04) | transfer_not_received_by_recipient (0.41 / 0.03) | transfer_into_account | transfer_not_received_by_recipient |
| banking77-666 | OMG! I'm trying to load my card and it wont top up! I desperately need the money either on my card or in my bank, where… | pending_top_up | top_up_failed (0.97 / 0.01) | top_up_reverted (0.81 / 0.00) | top_up_failed | top_up_failed |

他 321 件（全件は results/<run>/predictions.jsonl）

#### 混同ペア

正解 → 予測の組ごとの件数（全モデル合計の多い順、上限 10 組）。

| 正解 → 予測 | 件数 | モデル別 |
| --- | --- | --- |
| get_physical_card → change_pin | 26 | jev 12, llm_api 6, llm_local 8 |
| get_physical_card → passcode_forgotten | 20 | jev 2, laya 7, llm_api 7, llm_local 4 |
| beneficiary_not_allowed → declined_transfer | 13 | jev 3, laya 4, llm_api 2, llm_local 4 |
| order_physical_card → get_physical_card | 12 | jev 5, llm_api 4, llm_local 3 |
| pending_transfer → transfer_timing | 12 | jev 1, laya 4, llm_api 2, llm_local 5 |
| top_up_by_bank_transfer_charge → transfer_fee_charged | 12 | jev 2, laya 4, llm_api 2, llm_local 4 |
| fiat_currency_support → supported_cards_and_currencies | 11 | jev 2, laya 5, llm_local 4 |
| why_verify_identity → verify_my_identity | 11 | jev 3, laya 7, llm_local 1 |
| card_arrival → card_delivery_estimate | 10 | jev 1, laya 4, llm_api 1, llm_local 4 |
| card_delivery_estimate → card_arrival | 9 | jev 4, llm_api 5 |

他 237 組

#### 予測ラベルの確率（確率を返すモデルのみ）

| model | 正解時 n | 正解時 中央値 | 正解時 最小 | 誤り時 n | 誤り時 中央値 | 誤り時 最大 |
| --- | --- | --- | --- | --- | --- | --- |
| jev | 384 | 0.99 | 0.35 | 116 | 0.74 | 1.00 |
| laya | 191 | 1.00 | 0.33 | 309 | 0.97 | 1.00 |

#### 自信の低い判定を人に回した場合

「確率が閾値未満の判定は自動で処理せず、人が見直す（保留）」という運用を想定した試算。

- 保留率: 人に回った件の割合（人の手間）
- 自動処理分 Acc: 人に回さなかった件だけで数えた正解率
- 少ない保留率で Acc が上がるほど、確率が誤りを見つける手がかりとして役立っている。

| model | 閾値 0.5 保留率 | 閾値 0.5 自動処理分 Acc | 閾値 0.9 保留率 | 閾値 0.9 自動処理分 Acc |
| --- | --- | --- | --- | --- |
| jev | 0.040 | 0.790 | 0.306 | 0.899 |
| laya | 0.062 | 0.401 | 0.272 | 0.459 |

## jevbench_sst2

| model | n | Acc | Macro-F1 | エラー率 | p50 ms | p95 ms | サーバ p50 ms | 入力tok/件 | コスト/1万件 | 実行環境 | run |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| jev | 500 | 0.950 | 0.950 | 0.000 | 168.3 | 227.2 | - | 351 | $0.1475 | API (TypeSafe) | 20260929T053545Z_jev |
| laya | 500 | 0.920 | 0.920 | 0.000 | 101.9 | 127.0 | 99.6 | 66 | $0 | Apple M1 (8GB), mps | 20260929T054458Z_laya |
| llm_api<br>claude-haiku-4-5-20251001 | 500 | 0.960 | 0.960 | 0.000 | 798.9 | 1164.6 | - | 257 | $3.0210 | API (Anthropic) | 20260929T081350Z_llm_api |
| llm_local<br>qwen3:4b-instruct | 500 | 0.940 | 0.940 | 0.000 | 685.6 | 1092.2 | - | 95 | $0 | Apple M1 (8GB) | 20260929T081352Z_llm_local |
| [jevbench] jev (typesafe/jev-1.13) | - | 0.954 | 0.954 | 0.000 | 376.0 | 678.0 | - | - | $0.1480 | - | 参考値 |
| [jevbench] laya (convaiinnovations/laya) | - | 0.920 | 0.920 | 0.000 | 41.0 | 49.0 | - | - | - | - | 参考値 |
| [jevbench] llm-frontier (anthropic/claude-sonnet-5) | - | 0.956 | 0.956 | 0.000 | 2076.0 | 2615.0 | - | - | $8.0350 | - | 参考値 |
| [jevbench] llm-cheap (openai/gpt-5-mini) | - | 0.950 | 0.950 | 0.000 | 1385.0 | 2190.0 | - | - | $0.8160 | - | 参考値 |
| [jevbench] bert-ft (distilbert-base-uncased) | - | 0.910 | 0.910 | 0.000 | 6.0 | 8.0 | - | - | - | - | 参考値 |
| [jevbench] bert-zs (facebook/bart-large-mnli) | - | 0.896 | 0.895 | 0.000 | 63.0 | 71.0 | - | - | - | - | 参考値 |

- 参考値は [jevbench](https://github.com/dhruvmehra/jevbench/blob/c983cc4/docs/results/2026-09-22-n500-summary.md) の公開結果。jevbench 公表値（n=500, seed=0）。Acc はエラー件を除外（本リポジトリは不正解扱い）。Jev・LLM のレイテンシは OpenRouter 経由。スループットは並列計測のため省略
- ⚠️ タスク定義（instructions・ラベル説明）が run 間で異なる（同一条件の比較になっていない）
- ⚠️ プロンプトが run 間で異なる（同一条件の比較になっていない）
- ⚠️ コード（git commit）が run 間で異なる（同一条件の比較になっていない）
- ⚠️ 未コミットの変更がある状態で実行: laya

### 誤り分析

#### 誤った件

いずれかのモデルが間違えた件。間違えたモデル数の多い順（上限 20 件）。セルは予測ラベル（✓ は正解）。確率が取れるモデルは（予測の確率 / 正解の確率）を併記。

| id | テキスト | 正解 | jev | laya | llm_api | llm_local |
| --- | --- | --- | --- | --- | --- | --- |
| sst2-464 | intriguing documentary which is emotionally diluted by focusing on the story 's least interesting subject . | positive | negative (0.99 / 0.01) | negative (0.96 / 0.04) | negative | negative |
| sst2-519 | moretti 's compelling anatomy of grief and the difficult process of adapting to loss . | negative | positive (1.00 / 0.00) | positive (0.96 / 0.04) | positive | positive |
| sst2-791 | it 's somewhat clumsy and too lethargically paced -- but its story about a mysterious creature with psychic abilities o… | negative | positive (0.96 / 0.04) | positive (0.75 / 0.25) | positive | positive |
| sst2-850 | miller is playing so free with emotions , and the fact that children are hostages to fortune , that he makes the audien… | positive | negative (0.98 / 0.02) | negative (0.80 / 0.20) | negative | negative |
| sst2-271 | as unseemly as its title suggests . | positive | negative (0.99 / 0.01) | negative (0.91 / 0.09) | negative | negative |
| sst2-865 | mcconaughey 's fun to watch , the dragons are okay , not much fire in the script . | positive | negative (0.71 / 0.29) | negative (0.86 / 0.14) | negative | negative |
| sst2-112 | hilariously inept and ridiculous . | positive | negative (0.82 / 0.18) | negative (0.58 / 0.42) | negative | negative |
| sst2-388 | when leguizamo finally plugged an irritating character late in the movie . | negative | ✓ | positive (0.59 / 0.41) | positive | positive |
| sst2-760 | writer/director joe carnahan 's grimy crime drama is a manual of precinct cliches , but it moves fast enough to cover i… | positive | negative (0.77 / 0.23) | negative (0.95 / 0.05) | ✓ | negative |
| sst2-422 | it moves quickly , adroitly , and without fuss ; it does n't give you time to reflect on the inanity -- and the cold wa… | positive | negative (0.84 / 0.16) | negative (0.56 / 0.44) | ✓ | negative |
| sst2-273 | minority report is exactly what the title indicates , a report . | positive | negative (0.82 / 0.18) | negative (0.67 / 0.33) | negative | ✓ |
| sst2-377 | nothing is sacred in this gut-buster . | negative | positive (0.73 / 0.27) | positive (0.94 / 0.06) | positive | ✓ |
| sst2-812 | this surreal gilliam-esque film is also a troubling interpretation of ecclesiastes . | positive | negative (0.81 / 0.19) | negative (0.52 / 0.48) | negative | ✓ |
| sst2-230 | reign of fire looks as if it was made without much thought -- and is best watched that way . | positive | negative (0.98 / 0.02) | ✓ | negative | negative |
| sst2-749 | a working class `` us vs. them '' opera that leaves no heartstring untugged and no liberal cause unplundered . | positive | negative (0.90 / 0.10) | negative (0.98 / 0.02) | negative | ✓ |
| sst2-846 | an absurdist comedy about alienation , separation and loss . | negative | ✓ | positive (0.57 / 0.43) | positive | positive |
| sst2-673 | drops you into a dizzying , volatile , pressure-cooker of a situation that quickly snowballs out of control , while foc… | positive | negative (0.97 / 0.03) | ✓ | negative | negative |
| sst2-399 | if director michael dowse only superficially understands his characters , he does n't hold them in contempt . | negative | positive (0.51 / 0.49) | positive (0.72 / 0.28) | positive | ✓ |
| sst2-707 | no telegraphing is too obvious or simplistic for this movie . | negative | positive (0.77 / 0.23) | positive (0.51 / 0.49) | ✓ | positive |
| sst2-166 | characters still need to function according to some set of believable and comprehensible impulses , no matter how many … | negative | ✓ | positive (0.68 / 0.32) | ✓ | positive |

他 39 件（全件は results/<run>/predictions.jsonl）

#### 混同ペア

正解 → 予測の組ごとの件数（全モデル合計の多い順、上限 10 組）。

| 正解 → 予測 | 件数 | モデル別 |
| --- | --- | --- |
| positive → negative | 64 | jev 17, laya 19, llm_api 14, llm_local 14 |
| negative → positive | 51 | jev 8, laya 21, llm_api 6, llm_local 16 |

#### 予測ラベルの確率（確率を返すモデルのみ）

| model | 正解時 n | 正解時 中央値 | 正解時 最小 | 誤り時 n | 誤り時 中央値 | 誤り時 最大 |
| --- | --- | --- | --- | --- | --- | --- |
| jev | 475 | 1.00 | 0.51 | 25 | 0.77 | 1.00 |
| laya | 460 | 0.95 | 0.50 | 40 | 0.72 | 0.98 |

#### 自信の低い判定を人に回した場合

「確率が閾値未満の判定は自動で処理せず、人が見直す（保留）」という運用を想定した試算。

- 保留率: 人に回った件の割合（人の手間）
- 自動処理分 Acc: 人に回さなかった件だけで数えた正解率
- 少ない保留率で Acc が上がるほど、確率が誤りを見つける手がかりとして役立っている。

| model | 閾値 0.5 保留率 | 閾値 0.5 自動処理分 Acc | 閾値 0.9 保留率 | 閾値 0.9 自動処理分 Acc |
| --- | --- | --- | --- | --- |
| jev | 0.000 | 0.950 | 0.118 | 0.982 |
| laya | 0.000 | 0.920 | 0.332 | 0.973 |

## 注記

- p50 / p95 はクライアント側の往復時間（API はネットワーク込み）。warmup 分・エラー件は除外
- 接続は使い回す（keep-alive）。張り直した件数は metrics.json の new_connections
- エラー率はリトライしても応答が得られなかった件の割合（Acc では不正解として数える）
- サーバ p50 はサーバが返す純推論時間（X-Inference-Time-Ms ヘッダがある場合のみ。laya は 0.3.21 以降が返し、0.3.20 と Jev は返さない）
- コストは集計時点の configs/<name>.toml の [pricing]（USD / 1M tokens）から概算（無ければ実行時の config）。未設定は -
- ローカル実行（laya / llm_local）は API 課金が無いので $0。マシン代・電力は含まない
- 実行環境は実行時の config の hardware（無ければ実行マシンの CPU）。API はリクエスト先を書く
- 誤り分析の確率は Jev / Laya が返す probabilities の値（confidence ではない）。LLM は確率を返さないので確率の表から除く
- jev の確率は小数 2 桁に丸めて返される。確率の表はエラー件を除く
- 件数が少ないうちは、誤り分析は個別事例として読む（傾向の根拠にはならない）
