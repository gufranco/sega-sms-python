# Sega SMS

Sega の SG-1000 Mark III、2 機種のマスターシステム、ゲームギアを Python で実装したものです。Z80、サウンドジェネレータを内蔵した VDP パッケージ、ボードを 1 つのクロックで動かし、オリジナルの BIOS と実際のカートリッジを起動して、VDP が描いたフレームをドットごとに返します。

[English](README.md) | 日本語 | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/sega-sms-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sega-sms-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sega-sms-python)](https://github.com/gufranco/sega-sms-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

異なるマスターシステムとゲームギアのイメージ **2,608** 本をそれぞれ **300** フレーム起動、市販の **813** 本で性質の不合格 **0** 件、マニュアルで所在を確認した引用 **5** 件、テスト **695** 件、何も除外しないステートメントとブランチのカバレッジ **100%**、標準ライブラリとこのファミリーの 3 つのメンバー以外への依存関係なし

```python
import smsmapper
import segasms

program = bytes(
    [0x3E, 0x04, 0xD3, 0xBF, 0x3E, 0x80, 0xD3, 0xBF]
    + [0x3E, 0x01, 0xD3, 0xBF, 0x3E, 0x87, 0xD3, 0xBF]
    + [0x3E, 0x11, 0xD3, 0xBF, 0x3E, 0xC0, 0xD3, 0xBF]
    + [0x3E, 0x3F, 0xD3, 0xBE, 0x18, 0xFE]
)
cartridge = smsmapper.Cartridge(program + bytes(0x8000 - len(program)))
machine = segasms.Machine("sms", cartridge=cartridge).reset()

first = machine.run_frame()
second = machine.run_frame()
print(first.width, first.height, len(second.colours), sorted(set(second.colours)))
print(machine.vdp.model, machine.vdp.region, machine.cpu.model)
print(second.digest()[:16])

spent = machine.step()
print(spent, machine.cpu.registers.pc)
```

```
256 192 49152 [63]
315-5124 ntsc z80
f927d1a55081d857
12 28
```

プログラムは VDP をモード 4 にし、カラー RAM のエントリ 17 を背景色にして、そこに白の 3Fh を書き込みます。表示はオフのままなので、256 × 192 のアクティブドットはすべて背景色を示します。フレームはビームが描く順に並んだ各アクティブドットのカラー RAM ワードで、そのダイジェストはそれらのワードに対する SHA-256 です。最後の命令はプログラムが最後に回る `jr` で、12 T ステートです。

## インストール

| 要件   | 理由                                           |
| :----- | :--------------------------------------------- |
| Docker | Python、ツール、テストのすべてを動かす         |
| git    | リポジトリとそのメンバーを取得する             |
| uv     | `scripts/play`、ホスト上のウィンドウにだけ使う |

```bash
git clone --recurse-submodules https://github.com/gufranco/sega-sms-python.git
cd sega-sms-python
scripts/run python segasms/doctor.py
```

Windows では `scripts/run` の代わりに `scripts\run.ps1` を実行します。最初の実行でイメージをビルドします。イメージは Python、uv、Node とすべてのツールを固定しており、マシンには何もインストールしません。`scripts/run <command>` はチェックアウトをマウントしたイメージの中で任意のコマンドを実行します。パッケージは標準ライブラリとこのファミリーの 3 つのメンバー以外への依存関係がなく、それらはクローンがサブモジュールとして持ち込みます: `zilog-z80-python`、`sega-vdp-python`、`sms-mapper-python`。ウィンドウの `window.play` はパッケージの外にあり、pygame-ce も必要です。download-zip リンクから得たソースアーカイブにはサブモジュールがなく、動きません。

doctor はコンテナ、マウントしたチェックアウト、マシンを調べ、最後に 1 行を出力します。バグ報告には出力全体を貼り付けてください。macOS の Colima では、Colima が共有していないフォルダは空でマウントされ、doctor の checkout の行がそれを伝えます。

## インターフェース

`segasms.Machine(model=None, cartridge=None, bios=None, region=None, handheld_mode=True)` はコンソールを 1 台組み立てます。`cartridge` と `bios` はダンプのバイト列から `smsmapper.Cartridge` で作ったボードで、どちらも省略できます。BIOS があればハードウェアと同じくコンソールはその中で起動し、BIOS がカートリッジを見つけて起動します。なければ 0000h からカートリッジを起動します。`handheld_mode=False` にすると、ピン 42 を接地するカートリッジと同じくゲームギアがマスターシステムモードになり、ポート 0 から 6 が消え、START がポーズになり、256 × 192 の画面全体が表示されます。

| Model      | 別名                                     | VDP        | Processor | 省略時の地域 |
| :--------- | :--------------------------------------- | :--------- | :-------- | :----------- |
| `mark-iii` | `mark3`, `markiii`, `sg-1000 mark iii`   | `315-5124` | `z80`     | `japan`      |
| `sms`      | `master system`, `sms1`, `master-system` | `315-5124` | `z80`     | `usa`        |
| `sms2`     | `master system ii`, `master-system-ii`   | `315-5246` | `z80`     | `usa`        |
| `gg`       | `game gear`, `game-gear`, `gamegear`     | `315-5378` | `z80`     | `usa`        |

`smsmapper` がコンソールに受け付ける別名はここでもすべて使えます。`region` は `japan`、`usa`、`europe` のいずれかです。ヨーロッパのマスターシステムは VDP を 1 フレーム 313 ラインで、それ以外のコンソールは 262 ラインで動かします。

```python
import segasms

for machine in (
    segasms.Machine("mark-iii"),
    segasms.Machine("sms", region="europe"),
    segasms.Machine("sms2"),
    segasms.Machine("gg"),
):
    print(machine.console.model.name, machine.console.region, machine.vdp.model, machine.vdp.region)
```

```
mark-iii japan 315-5124 ntsc
sms europe 315-5124 pal
sms2 usa 315-5246 ntsc
gg usa 315-5378 ntsc
```

### 呼び出し

| 呼び出し                    | 効果                                                                                   |
| :-------------------------- | :------------------------------------------------------------------------------------- |
| `reset()`                   | リセット線と同じく VDP とプロセッサをリセットします。マシンを返します                  |
| `step()`                    | 命令を 1 つ実行し、その T ステートごとに VDP を 3 ティック進めます                     |
| `run_frame(limit=100000)`   | VDP がフレームを描き終えるまで実行してそれを返します。`limit` 命令を超えると `NoFrame` |
| `press(button, player=1)`   | コントローラのボタン、または `pause` か `start` を押したままにします                   |
| `release(button, player=1)` | 離します                                                                               |
| `windowed()`                | フレームをゲームギアの 160 × 144 の窓で見せるとき True。自分のモードのときだけです     |

### 状態

| 属性      | 意味                                                                      |
| :-------- | :------------------------------------------------------------------------ |
| `cpu`     | `z80.Cpu`: `registers`、`cycles`、`irq_line`、`nmi_line`                  |
| `vdp`     | `segavdp` のパーツ: `line`、`dot`、`registers`、`cram`、`sound`、`cycles` |
| `console` | `smsmapper.Console`: メモリマップ、スロットの有効化、コントローラポート   |

`Frame` は各アクティブドットのカラー RAM ワード `colours`、`width` と `height`、`digest()` を持ちます。

### モジュールの内容

| 名前                         | 内容                                               |
| :--------------------------- | :------------------------------------------------- |
| `segasms.Machine`            | コンソール 1 台                                    |
| `segasms.Frame`              | 描き終えたフレーム 1 枚                            |
| `segasms.MODELS`             | 4 つの `Model` レコード、コンソール名がキー        |
| `segasms.Model`              | コンソールの名前、その VDP パーツとプロセッサ      |
| `segasms.NoFrame`            | 許された命令数の中でフレームが終わらないときに送出 |
| `segasms.UnknownModelError`  | `smsmapper` にないコンソール名で送出               |
| `segasms.UnknownRegionError` | `japan`、`usa`、`europe` 以外の地域で送出          |
| `segasms.__version__`        | インストールされているバージョン                   |

```python
import segasms

for name, model in sorted(segasms.MODELS.items()):
    print(name, model.vdp, model.processor)

try:
    segasms.Machine("neo geo")
except segasms.UnknownModelError as error:
    print(error)
```

```
gg 315-5378 z80
mark-iii 315-5124 z80
sms 315-5124 z80
sms2 315-5246 z80
no console is called 'neo geo'; the consoles are ['gg', 'mark-iii', 'sms', 'sms2']
```

### モジュール

| モジュール        | 内容                                                                       |
| :---------------- | :------------------------------------------------------------------------- |
| `segasms.machine` | コンソール: 3 つのパーツを 1 つのクロックで                                |
| `segasms.bus`     | プロセッサのメモリとポート、ボードと VDP への振り分け                      |
| `segasms.frame`   | 描き終えたフレームと、それをドットごとに集めるスクリーン                   |
| `segasms.models`  | 各コンソールの VDP パーツとプロセッサ、コンソールの地域が動かす VDP の地域 |
| `segasms.errors`  | パッケージが自ら送出するすべて                                             |
| `segasms.speaker` | 音源の出力を平均した 44,100 Hz ステレオのサンプル                          |
| `segasms.record`  | レコーダー: どのイメージからもアニメーション PNG と WAV を作る             |
| `window.play`     | ウィンドウ: 画面、音、パッドとしてのキーボード                             |

## クロック

VDP の `tick()` はプロセッサクロックの 3 分の 1 で、プロセッサは各 T ステートの終わりに 1 回ボードを呼びます。ボードはそこで VDP を 3 ティック進め、VDP の割り込みピンをプロセッサのマスク可能な線に、ポーズボタン、またはマスターシステムモードのゲームギアの start をマスク不能な線に写します。ポートアクセスはプロセッサのストローブと同じ、I/O サイクルに入って 10 ティック目、つまり 3 つの T ステートと 4 つ目の最初のティックに届きます。VDP はそこで書き込みを受け取り、プロセッサはそこで読み込みを受け取り、それより前の各 T ステートが見た割り込みピンをプロセッサがサンプルします。ボードの上で水晶そのものを読むものはなく、どの機種でも水晶の 5 分の 1 である VDP ティックが最も細かい刻みです。

```python
import smsmapper
import segasms

program = bytes([0xED, 0x56, 0x3E, 0x20, 0xD3, 0xBF, 0x3E, 0x81, 0xD3, 0xBF, 0xFB, 0x18, 0xFE])
cartridge = smsmapper.Cartridge(program + bytes(0x8000 - len(program)))
machine = segasms.Machine("sms", cartridge=cartridge).reset()
machine.cpu.registers.sp = 0xDFF0

before = (machine.cpu.cycles, machine.vdp.cycles)
machine.cpu.run_until(lambda part: part.registers.pc == 0x0038, limit=20000)
states = machine.cpu.cycles - before[0]
ticks = machine.vdp.cycles - before[1]
print(states, ticks, ticks == 3 * states, machine.vdp.line, hex(machine.vdp.status))
```

```
43969 131907 True 193 0x80
```

プログラムは割り込みモード 1 を設定し、レジスタ 1 でフレーム割り込みを有効にして待ちます。VDP がフレームフラグを立てると、プロセッサは実行中の `jr` を終えて 0038h から再開します。リセットから 43,969 T ステートで、どの T ステートにも VDP ティックはちょうど 3 つです。

ポートはコンソールのデコードが名指すものに届きます。VDP のデータ、コントロール、カウンタのポートとサウンドジェネレータは VDP パッケージへ、それ以外はすべてボードへ行きます。ポート 3F への書き込みで TH を出力として上げると、同じ T ステートで VDP の H カウンタがラッチされ、ゲームギアではポート 6 への書き込みがサウンドジェネレータのステレオレジスタも設定します。

```python
import smsmapper
import segasms

program = bytes([0x3E, 0x0F, 0xD3, 0x06, 0x18, 0xFE])
game_gear = segasms.Machine("gg", cartridge=smsmapper.Cartridge(program + bytes(0x7FFA))).reset()
game_gear.step()
game_gear.step()
print(hex(game_gear.vdp.sound.stereo), hex(game_gear.console.registers[6]))

console = segasms.Machine(
    "sms", cartridge=smsmapper.Cartridge(bytes([0x18, 0xFE]) + bytes(0x7FFE))
).reset()
console.cpu.registers.sp = 0xDFF0
console.press("pause")
taken = [console.step() and console.cpu.registers.pc for _ in range(4)]
print([hex(one) for one in taken])
```

```
0xf 0xf
['0x66', '0x67', '0x68', '0x69']
```

ゲームギアのポート 6 への書き込みは、ボードのレジスタにもステレオレジスタにも同じように届きます。ポーズを押し続けると、どれだけ長く押してもマスク不能割り込みは 0066h で 1 回だけ起こり、プロセッサはそこから先へ進みます。

## BIOS の起動

BIOS イメージはどのカートリッジとも同じボードです。`bios=smsmapper.Cartridge(image)` で組み立てると、コンソールはカートリッジスロットをオフにして BIOS の中で起動し、BIOS はロゴを描き、ローダーを RAM の C700h にコピーし、ポート 3E でカートリッジをオンにして、検査してから起動します。BIOS 1.3 と _Sonic The Hedgehog_ のマスターシステムでは、フレーム 120 までにロゴが出て、フレーム 340 付近でポート 3E がカートリッジをオンにし、Sonic はフレーム 650 ごろから描きます。

## 遊ぶ、録る

```bash
scripts/play "Sonic The Hedgehog.sms"
scripts/play "Sonic The Hedgehog.sms" --replay 300
scripts/run python -m segasms.record "Sonic The Hedgehog.sms" --frames 300 --out recordings
```

`scripts/play` はウィンドウを開き、テストが動かすのと同じマシンを、サイクル単位のモデルが出せる速さ、毎秒数フレームで動かします。速さのために何も犠牲にしていません。矢印キーがパッド、Z と X がボタン 1 と 2、Return がポーズ (ゲームギアではスタート)、Backspace がマスターシステムのリセットボタンで、Escape かウィンドウを閉じると止まります。各フレームの音はフレームを描き終えたときに正しい音程で鳴り、次のフレームまでは無音です。`--replay N` は先に N フレームをエミュレートし、そのあと画面と音を本体の速さで一緒に再生します。`--bios FILE` は先に本物の BIOS を起動します。指定しなければ、マスターシステムは BIOS が引き渡す状態から、ゲームギアはリセット時の値から始まります。`--scale N` はウィンドウの大きさで、既定は 3 です。`--mode master-system` は、R.C. Grand Prix (USA) のようにピン 42 を接地するゲームギアのカートリッジのために、イメージをマスターシステムモードのゲームギアで動かします。ウィンドウが全画面で開くことはありません。

ウィンドウはイメージの中ではなくホストで動く唯一のツールです。コンテナには画面も音の出力装置もないからです。必要なのは uv で、uv が Python 3.12.14 と `uv.lock` が固定する pygame-ce を、チェックアウトの外のキャッシュフォルダに持ち込みます。Windows では `scripts\play.ps1` を実行します。

`segasms.record` はイメージの中で動き、`<name>.png` (各フレームを本体でかかった時間だけ表示するアニメーション PNG) と `<name>.wav` (16 ビットステレオ、44,100 Hz) を書きます。各サンプルは、それがまたがる周期について音源の出力を平均したものです。秒は Mark III のマニュアルがプロセッサについて記す 3.58 MHz から求め、すべてのモデルに使います。ゲームギアのフレームは 160 × 144 の窓で、ここでも `--mode master-system` で選べるマスターシステムモードでは 256 × 192 の画面全体です。PNG はブラウザで再生できます。

## 全数調査

```bash
scripts/run python -m conformance.census "external/Master EverDrive" "external/EverDrive GG" --frames 300 --jobs 2
```

全数調査は、マスターシステムとゲームギアのライブラリにあるすべてのイメージを、MAME のソフトウェアリストが名指すボードの上でカートリッジから起動し、フレームの上限まで動かします。`.sms` のイメージはマスターシステムで、`.gg` のイメージはゲームギアで動き、MAME のリストがピン 42 を接地すると記すゲームギアのカートリッジはマスターシステムモードのゲームギアで動き、ヨーロッパのセットだけが載せているイメージはヨーロッパのコンソールで動きます。異なるイメージごとに、2 色以上を示した最初のフレームと、すべてのフレームのダイジェストを連鎖させた SHA-256 を残すので、後の実行でどのフレームのどのドットが動いたかがすぐにわかります。ディレクトリ、zip アーカイブ、単体のイメージを受け付け、要約を出力し、[`conformance/corpus.json`](conformance/corpus.json) を書き、性質が破れると 1 で終了します。

2 つの性質が実行を判定します: どのイメージでもマシンが例外を出さないこと、そしてすべての市販イメージがフレームの上限内に 2 色以上を描くこと。描かない市販カートリッジは、このパッケージがコンソールを間違えていることを示します。ベータやデモなど市販以外のイメージで描かないものは、不合格にせず数えて名前を挙げます。

| 直近の実行の結果                                        | 件数  |
| :------------------------------------------------------ | :---- |
| 2 つのライブラリにある項目                              | 5,110 |
| 異なるイメージ                                          | 2,608 |
| 市販イメージ。判定の対象です                            | 813   |
| ヨーロッパ版の本体で動かしたもの。1 フレーム 313 ライン | 233   |
| 最初の 1 秒で 2 色以上を描いたもの                      | 2,014 |
| それより後に 2 色以上を描いたもの                       | 545   |
| 2 色以上を一度も描かなかったもの                        | 49    |

[`conformance/corpus.json`](conformance/corpus.json) はそれらの数と、各イメージの SHA-256 ごとの最初に描いたフレームと連鎖ダイジェストを持ち、どのカートリッジの中身も持ちません。

## 正しいかどうか

各パーツはそれぞれのメンバーで検証されています: Z80 は SingleStepTests とその全数調査に、VDP パッケージは Sega のマニュアル、TI の文書とその全数調査に、ボードはマニュアルとその全数調査に。このリポジトリが持つのはそれらをつなぐことで加わるものです: どの線がどのピンを駆動するか、T ステートあたり 3 ティック、起動経路。[`conformance/hardware.json`](conformance/hardware.json) はそれぞれの事実を出典とともに持ち、どの文書にも印刷されていない値は `notStated` の下に未検証として、決着させる測定とともに置かれています。[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) がそれらを一覧にしています。

## 開発に参加する

| 必要なもの                                             | 場所                                                                |
| :----------------------------------------------------- | :------------------------------------------------------------------ |
| すべてのゲートと実行する順番                           | [CONTRIBUTING.md](CONTRIBUTING.md)                                  |
| コーディングエージェント向けの同じ内容                 | [AGENTS.md](AGENTS.md)                                              |
| このリポジトリがファミリーの他のメンバーと共有する標準 | [FAMILY.md](FAMILY.md)                                              |
| バグ報告                                               | [GitHub Issues](https://github.com/gufranco/sega-sms-python/issues) |
| セキュリティ報告                                       | [SECURITY.md](SECURITY.md)                                          |

```bash
scripts/run make gate
scripts/run python segasms/machine.test.py
```

`make gate` はフォーマッタ、リンタ、型チェッカ、YAML チェッカと、カバレッジ下のすべてのテストを実行します。カバレッジはステートメントとブランチで 100% の厳格なゲートで、何も除外していません。各モジュールの隣にはその名前のテストファイルがあり、どれも上のように単独で動きます。

## 参考文献

- _Software Reference Manual for the SEGA Mark III Console_、Sega、日付なし、打ち直した写し。45 ページ、184,840 バイト、SHA-256 `166f09331ba9df055f7a352f10c6a7843911470bc72d9347eda4a0de86e8cfce`。再配布できず、このリポジトリにはありません。`scripts/run python -m conformance.documents` が https://segaretro.org/images/d/d6/SoftwareReferenceManualForSegaMarkIIIEU.pdf からダウンロードし、ほかのファイルは拒否します。
- MAME、`hash/sms.xml` と `hash/gamegear.xml`、コミット `94fc55c9692b180dcb608e2e222e48315db5017a`、https://github.com/mamedev/mame、`sms-mapper-python` を通して、各イメージが載るボードのために。

## 引用

[CITATION.cff](CITATION.cff) は、パッケージのバージョンを刻むスクリプトによってリリースごとに更新されます。

## ライセンス

MIT。[LICENSE](LICENSE) を参照してください。
