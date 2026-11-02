# Sega SMS

用 Python 實現的世嘉 SG-1000 Mark III、兩款 Master System 和 Game Gear：Z80、內置聲音產生器的 VDP 封裝和電路板運行在同一個時鐘上，啟動原版 BIOS 和真實卡帶，并逐點給出 VDP 畫出的幀。

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | 繁體中文（香港）

[![CI](https://github.com/gufranco/sega-sms-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sega-sms-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sega-sms-python)](https://github.com/gufranco/sega-sms-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**2,608** 個不同的 Master System 和 Game Gear 映像檔各啟動 **300** 幀，**813** 個零售映像檔中屬性失敗為 **0**，在手冊中找到 **5** 處引文，**695** 個測試，不排除任何內容的 **100%** 陳述式和分支覆蓋率，除標準庫和本家族的三個成員外沒有依賴套件

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

程式把 VDP 設為模式 4，讓顏色 RAM 第 17 項作為背景色，并向其中寫入白色 3Fh。顯示保持關閉，所以 256 × 192 個有效點全部顯示背景色。一幀就是按電子束繪製順序排列的每個有效點的顏色 RAM 字，其摘要是对這些字計算的 SHA-256。最後一條指令是程式結尾循環的 `jr`，12 個 T 狀態。

## 安裝

| 要求   | 用途                                  |
| :----- | :------------------------------------ |
| Docker | 運行一切：Python、工具和測試          |
| git    | 獲取儲存庫及其成員                    |
| uv     | 僅用於 `scripts/play`，即主機上的視窗 |

```bash
git clone --recurse-submodules https://github.com/gufranco/sega-sms-python.git
cd sega-sms-python
scripts/run python segasms/doctor.py
```

在 Windows 上，用 `scripts\run.ps1` 代替 `scripts/run`。首次運行會建置映像檔，映像檔固定了 Python、uv、Node 和所有工具，機器上無需安裝任何東西。`scripts/run <command>` 在掛載了檢出目錄的映像檔中運行任意命令。除標準庫和本家族的三個成員外，本套件沒有其他依賴，複製時它們作為子模組一同獲取：`zilog-z80-python`、`sega-vdp-python` 和 `sms-mapper-python`。視窗 `window.play` 位於套件之外，另外還需要 pygame-ce。從 download-zip 連結得到的原始碼壓縮檔不含子模組，無法運行。

doctor 檢查容器、掛載的檢出目錄和機器，最後輸出一行。提交錯誤報告時請貼上完整輸出。在 macOS 的 Colima 上，Colima 未共享的資料夾會以空目錄掛載，doctor 的 checkout 一行會指出這一點。

## 介面

`segasms.Machine(model=None, cartridge=None, bios=None, region=None, handheld_mode=True)` 組裝一台主機。`cartridge` 和 `bios` 是用 `smsmapper.Cartridge` 從傾印位元組建置的電路板，兩者都可以省略。有 BIOS 時，主機像硬件一樣從 BIOS 啟動，由 BIOS 找到并啟動卡帶；沒有 BIOS 時從 0000h 啟動卡帶。`handheld_mode=False` 令 Game Gear 像把第 42 針接地的卡帶一樣進入 Master System 模式：端口 0 到 6 消失，START 成為暫停，並顯示整個 256 × 192 的畫面。

| Model      | 別名                                     | VDP        | Processor | 省略時的地區 |
| :--------- | :--------------------------------------- | :--------- | :-------- | :----------- |
| `mark-iii` | `mark3`, `markiii`, `sg-1000 mark iii`   | `315-5124` | `z80`     | `japan`      |
| `sms`      | `master system`, `sms1`, `master-system` | `315-5124` | `z80`     | `usa`        |
| `sms2`     | `master system ii`, `master-system-ii`   | `315-5246` | `z80`     | `usa`        |
| `gg`       | `game gear`, `game-gear`, `gamegear`     | `315-5378` | `z80`     | `usa`        |

`smsmapper` 為主機接受的所有別名在這裡同樣可用。`region` 為 `japan`、`usa` 或 `europe`；歐洲版 Master System 的 VDP 每幀 313 行，其餘主機每幀 262 行。

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

### 呼叫

| 呼叫                        | 作用                                                                   |
| :-------------------------- | :--------------------------------------------------------------------- |
| `reset()`                   | 像重設線一樣重設 VDP 和處理器，傳回機器                                |
| `step()`                    | 執行一條指令，其每個 T 狀態讓 VDP 前進三個滴答                         |
| `run_frame(limit=100000)`   | 運行到 VDP 畫完一幀并傳回該幀；超過 `limit` 條指令時拋出 `NoFrame`     |
| `press(button, player=1)`   | 按住手掣按鈕，或 `pause`、`start`                                      |
| `release(button, player=1)` | 鬆開                                                                   |
| `windowed()`                | 幀經由 Game Gear 160 × 144 的視窗顯示時為 True，只在它自己的模式下如此 |

### 狀態

| 屬性      | 含義                                                                  |
| :-------- | :-------------------------------------------------------------------- |
| `cpu`     | `z80.Cpu`：`registers`、`cycles`、`irq_line`、`nmi_line`              |
| `vdp`     | `segavdp` 部件：`line`、`dot`、`registers`、`cram`、`sound`、`cycles` |
| `console` | `smsmapper.Console`：記憶體映射、插槽啟用、手掣連接埠                 |

`Frame` 持有每個有效點的顏色 RAM 字 `colours`、`width` 和 `height`，以及 `digest()`。

### 模組內容

| 名稱                         | 內容                                       |
| :--------------------------- | :----------------------------------------- |
| `segasms.Machine`            | 一台主機                                   |
| `segasms.Frame`              | 畫完的一幀                                 |
| `segasms.MODELS`             | 四個 `Model` 記錄，以主機名為鍵            |
| `segasms.Model`              | 主機的名稱、其 VDP 部件和處理器            |
| `segasms.NoFrame`            | 在允許的指令數內沒有畫完一幀時拋出         |
| `segasms.UnknownModelError`  | 主機名在 `smsmapper` 中不存在時拋出        |
| `segasms.UnknownRegionError` | 地區不是 `japan`、`usa` 或 `europe` 時拋出 |
| `segasms.__version__`        | 已安裝的版本                               |

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

### 模組

| 模組              | 內容                                                   |
| :---------------- | :----------------------------------------------------- |
| `segasms.machine` | 主機：三個部件運行在同一個時鐘上                       |
| `segasms.bus`     | 處理器的記憶體和連接埠，分派給電路板和 VDP             |
| `segasms.frame`   | 畫完的一幀，以及逐點收集它的螢幕                       |
| `segasms.models`  | 各主機的 VDP 部件和處理器，以及主機地區對應的 VDP 地區 |
| `segasms.errors`  | 本套件自己拋出的所有異常                               |
| `segasms.speaker` | 聲音產生器的輸出，平均為 44,100 Hz 立體聲取樣          |
| `segasms.record`  | 錄製器：從任意映像檔產生動畫 PNG 和 WAV                |
| `window.play`     | 視窗：畫面、聲音，以及當作手掣的鍵盤                   |

## 時鐘

VDP 的 `tick()` 是處理器時鐘的三分之一，處理器在每個 T 狀態結束時呼叫一次電路板。電路板在此讓 VDP 前進三個滴答，然後把 VDP 的中斷接腳複製到處理器的可遮蔽中斷線，把暫停鍵（或 Master System 模式下 Game Gear 的 start）複製到不可遮蔽中斷線。連接埠存取落在處理器選通訊號所在之處，即 I/O 週期開始後第 10 個滴答：三個 T 狀態加上第四個的第一個滴答。VDP 在那裏接收寫入，處理器在那裏取得讀取的值，而處理器取樣的中斷接腳，是之前每個 T 狀態各自所見的那個。電路板上沒有任何東西直接讀取晶振，所以在所有型號上都是晶振五分之一的 VDP 滴答是最細的步進。

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

程式設定中斷模式 1，在暫存器 1 中開啟幀中斷后等待。VDP 設定幀標誌時，處理器執行完目前的 `jr` 后從 0038h 重新開始：從重設起共 43,969 個 T 狀態，每個 T 狀態恰好對應三個 VDP 滴答。

連接埠到達主機解碼所指定的對象。VDP 的資料、控制和計數器連接埠以及聲音產生器交給 VDP 封裝，其餘一切交給電路板。向連接埠 3F 寫入使 TH 作為輸出變高時，會在同一個 T 狀態鎖存 VDP 的 H 計數器；在 Game Gear 上，向連接埠 6 寫入也會設定聲音產生器的立體聲暫存器。

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

Game Gear 向連接埠 6 的寫入同樣到達電路板的暫存器和立體聲暫存器。按住暫停鍵，無論按多久都只會在 0066h 產生一次不可遮蔽中斷，之後處理器繼續運行。

## 啟動 BIOS

BIOS 映像檔和任何卡帶一樣是一塊電路板。用 `bios=smsmapper.Cartridge(image)` 組裝后，主機關閉卡帶插槽從 BIOS 啟動；BIOS 畫出標誌，把載入程式複製到 RAM 的 C700h，通過連接埠 3E 打開卡帶，檢查后再啟動它。在裝有 BIOS 1.3 和 _Sonic The Hedgehog_ 的 Master System 上，第 120 幀前出現標誌，約第 340 幀連接埠 3E 打開卡帶，約第 650 幀起 Sonic 開始繪製。

## 遊玩與錄製

```bash
scripts/play "Sonic The Hedgehog.sms"
scripts/play "Sonic The Hedgehog.sms" --replay 300
scripts/run python -m segasms.record "Sonic The Hedgehog.sms" --frames 300 --out recordings
```

`scripts/play` 打開一個視窗，運行與測試所用相同的機器，速度是逐週期模型能達到的速度，每秒幾幀。沒有為速度犧牲任何東西。方向鍵是手掣，Z 和 X 是按鈕 1 和 2，Return 是暫停鍵（在 Game Gear 上是開始鍵），Backspace 是 Master System 的重設按鈕，按 Escape 或關閉視窗即停止。每幀的聲音在該幀畫完時以正確的音高播放，直到下一幀之前保持靜音。`--replay N` 先模擬 N 幀，然後以主機的速度同時播放畫面和聲音。`--bios FILE` 先啟動原版 BIOS；不指定時，Master System 從 BIOS 交接時的狀態開始，Game Gear 從重設值開始。`--scale N` 設定視窗大小，預設為 3。`--mode master-system` 讓映像檔在 Master System 模式的 Game Gear 上運行，用於像 R.C. Grand Prix (USA) 這樣把第 42 針接地的 Game Gear 卡帶。視窗從不以全螢幕打開。

視窗是唯一在主機上而不是在映像中運行的工具，因為容器沒有顯示和聲音裝置。它需要 uv，由 uv 把 Python 3.12.14 和 `uv.lock` 固定的 pygame-ce 下載到檢出目錄之外的快取資料夾。在 Windows 上運行 `scripts\play.ps1`。

`segasms.record` 在映像中運行，寫出 `<name>.png`（每幀按其在主機上所用的時間顯示的動畫 PNG）和 `<name>.wav`（16 位元立體聲，44,100 Hz）。每個取樣是聲音產生器的輸出在它所跨越的各週期上的平均值。秒數由 Mark III 手冊為處理器印出的 3.58 MHz 換算，用於所有型號。Game Gear 的幀是它 160 × 144 的視窗；在這裏同樣可用 `--mode master-system` 選擇的 Master System 模式下，則是整個 256 × 192 的畫面。瀏覽器可以播放該 PNG。

## 全面普查

```bash
scripts/run python -m conformance.census "external/Master EverDrive" "external/EverDrive GG" --frames 300 --jobs 2
```

普查按 MAME 軟件列表指定的電路板，從卡帶啟動 Master System 和 Game Gear 卡帶庫中的每個映像檔，并運行到幀數上限。`.sms` 映像檔在 Master System 上運行，`.gg` 映像檔在 Game Gear 上運行，但 MAME 清單標明把第 42 針接地的 Game Gear 卡帶在 Master System 模式的 Game Gear 上運行；只有歐洲合集收錄的映像檔在歐洲主機上運行。对每個不同的映像檔，它保留第一次顯示兩種以上顏色的幀，以及把所有幀摘要串聯計算的 SHA-256，因此之後再運行時能立即知道任何一幀的任何一個點是否變化。它接受目錄、zip 壓縮檔和單個映像檔，輸出摘要，寫入 [`conformance/corpus.json`](conformance/corpus.json)，屬性被破壞時以 1 退出。

兩項屬性決定運行結果：任何映像檔都不會讓機器拋出異常；每個零售映像檔都在幀數上限內畫出兩種以上顏色。不畫圖的零售卡帶說明本套件把主機做錯了。測試版、示範版等非零售映像檔不畫圖時，會被計數并列出名稱，而不判為失敗。

| 上次執行的結果                  | 數量  |
| :------------------------------ | :---- |
| 兩個卡帶庫中的項目              | 5,110 |
| 不同的映像檔                    | 2,608 |
| 零售映像檔，參與把關            | 813   |
| 在歐洲版主機上執行，每幀 313 行 | 233   |
| 在第一秒內畫出兩種以上顏色      | 2,014 |
| 之後才畫出兩種以上顏色          | 545   |
| 從未畫出兩種以上顏色            | 49    |

[`conformance/corpus.json`](conformance/corpus.json) 儲存這些計數，以及按 SHA-256 記錄的每個映像檔第一次畫圖的幀和串聯摘要，不含任何卡帶的內容。

## 是否正確

各部件由各自的成員檢驗：Z80 由 SingleStepTests 及其普查檢驗，VDP 封裝由世嘉手冊、TI 檔案及其普查檢驗，電路板由手冊及其普查檢驗。本儲存庫只負責把它們連接起来所增加的部分：哪條線驅動哪個接腳、每個 T 狀態三個滴答，以及啟動路徑。[`conformance/hardware.json`](conformance/hardware.json) 為每條事實附上出處，任何檔案都未印出的值放在 `notStated` 下，標為未驗證，并附有能確定它的測量方法。[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 列出了這些問題。

## 參與開發

| 需要                             | 位置                                                                |
| :------------------------------- | :------------------------------------------------------------------ |
| 所有關卡及其運行順序             | [CONTRIBUTING.md](CONTRIBUTING.md)                                  |
| 給編碼代理的同樣內容             | [AGENTS.md](AGENTS.md)                                              |
| 本儲存庫與家族其他成員共享的標準 | [FAMILY.md](FAMILY.md)                                              |
| 錯誤報告                         | [GitHub Issues](https://github.com/gufranco/sega-sms-python/issues) |
| 安全報告                         | [SECURITY.md](SECURITY.md)                                          |

```bash
scripts/run make gate
scripts/run python segasms/machine.test.py
```

`make gate` 運行格式化工具、程式碼檢查工具、型別檢查器、YAML 檢查器，以及覆蓋率統計下的所有測試；覆蓋率是陳述式和分支 100% 的硬性關卡，不排除任何內容。每個模块旁都有以其命名的測試檔案，都能像上面那样單獨運行。

## 參考資料

- _Software Reference Manual for the SEGA Mark III Console_，世嘉，未註明日期，重新輸入的副本。45 頁，184,840 位元組，SHA-256 `166f09331ba9df055f7a352f10c6a7843911470bc72d9347eda4a0de86e8cfce`。不可再散佈，也不在本儲存庫中。`scripts/run python -m conformance.documents` 從 https://segaretro.org/images/d/d6/SoftwareReferenceManualForSegaMarkIIIEU.pdf 下載，并拒絕任何其他檔案。
- MAME，`hash/sms.xml` 和 `hash/gamegear.xml`，提交 `94fc55c9692b180dcb608e2e222e48315db5017a`，https://github.com/mamedev/mame，經由 `sms-mapper-python`，用於確定每個映像檔所在的電路板。

## 引用

[CITATION.cff](CITATION.cff) 隨每次發佈由寫入包版本的指令碼更新。

## 授權條款

MIT。見 [LICENSE](LICENSE)。
