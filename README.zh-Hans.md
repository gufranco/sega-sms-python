# Sega SMS

用 Python 实现的世嘉 SG-1000 Mark III、两款 Master System 和 Game Gear：Z80、内置声音发生器的 VDP 封装和电路板运行在同一个时钟上，启动原版 BIOS 和真实卡带，并逐点给出 VDP 画出的帧。

[English](README.md) | [日本語](README.ja.md) | 简体中文 | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/sega-sms-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sega-sms-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sega-sms-python)](https://github.com/gufranco/sega-sms-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**2,608** 个不同的 Master System 和 Game Gear 映像各启动 **300** 帧，**813** 个零售映像中属性失败为 **0**，在手册中定位到 **5** 处引文，**695** 个测试，不排除任何内容的 **100%** 语句和分支覆盖率，除标准库和本家族的三个成员外无依赖

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

程序把 VDP 设为模式 4，让颜色 RAM 第 17 项作为背景色，并向其中写入白色 3Fh。显示保持关闭，所以 256 × 192 个有效点全部显示背景色。一帧就是按电子束绘制顺序排列的每个有效点的颜色 RAM 字，其摘要是对这些字计算的 SHA-256。最后一条指令是程序结尾循环的 `jr`，12 个 T 状态。

## 安装

| 要求   | 用途                                  |
| :----- | :------------------------------------ |
| Docker | 运行一切：Python、工具和测试          |
| git    | 获取仓库及其成员                      |
| uv     | 仅用于 `scripts/play`，即主机上的窗口 |

```bash
git clone --recurse-submodules https://github.com/gufranco/sega-sms-python.git
cd sega-sms-python
scripts/run python segasms/doctor.py
```

在 Windows 上，用 `scripts\run.ps1` 代替 `scripts/run`。首次运行会构建镜像，镜像固定了 Python、uv、Node 和所有工具，机器上无需安装任何东西。`scripts/run <command>` 在挂载了检出目录的镜像中运行任意命令。除标准库和本家族的三个成员外，本包没有其他依赖，克隆时它们作为子模块一同获取：`zilog-z80-python`、`sega-vdp-python` 和 `sms-mapper-python`。窗口 `window.play` 位于包之外，另外还需要 pygame-ce。从 download-zip 链接得到的源码压缩包不含子模块，无法运行。

doctor 检查容器、挂载的检出目录和机器，最后输出一行。提交错误报告时请粘贴完整输出。在 macOS 的 Colima 上，Colima 未共享的文件夹会以空目录挂载，doctor 的 checkout 一行会指出这一点。

## 接口

`segasms.Machine(model=None, cartridge=None, bios=None, region=None, handheld_mode=True)` 组装一台主机。`cartridge` 和 `bios` 是用 `smsmapper.Cartridge` 从转储字节构建的电路板，两者都可以省略。有 BIOS 时，主机像硬件一样从 BIOS 启动，由 BIOS 找到并启动卡带；没有 BIOS 时从 0000h 启动卡带。`handheld_mode=False` 让 Game Gear 像把第 42 针接地的卡带一样进入 Master System 模式：端口 0 到 6 消失，START 成为暂停，并显示整个 256 × 192 的画面。

| Model      | 别名                                     | VDP        | Processor | 省略时的地区 |
| :--------- | :--------------------------------------- | :--------- | :-------- | :----------- |
| `mark-iii` | `mark3`, `markiii`, `sg-1000 mark iii`   | `315-5124` | `z80`     | `japan`      |
| `sms`      | `master system`, `sms1`, `master-system` | `315-5124` | `z80`     | `usa`        |
| `sms2`     | `master system ii`, `master-system-ii`   | `315-5246` | `z80`     | `usa`        |
| `gg`       | `game gear`, `game-gear`, `gamegear`     | `315-5378` | `z80`     | `usa`        |

`smsmapper` 为主机接受的所有别名在这里同样可用。`region` 为 `japan`、`usa` 或 `europe`；欧洲版 Master System 的 VDP 每帧 313 行，其余主机每帧 262 行。

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

### 调用

| 调用                        | 作用                                                                   |
| :-------------------------- | :--------------------------------------------------------------------- |
| `reset()`                   | 像复位线一样复位 VDP 和处理器，返回机器                                |
| `step()`                    | 执行一条指令，其每个 T 状态让 VDP 前进三个滴答                         |
| `run_frame(limit=100000)`   | 运行到 VDP 画完一帧并返回该帧；超过 `limit` 条指令时抛出 `NoFrame`     |
| `press(button, player=1)`   | 按住手柄按钮，或 `pause`、`start`                                      |
| `release(button, player=1)` | 松开                                                                   |
| `windowed()`                | 帧经由 Game Gear 160 × 144 的窗口显示时为 True，只在它自己的模式下如此 |

### 状态

| 属性      | 含义                                                                  |
| :-------- | :-------------------------------------------------------------------- |
| `cpu`     | `z80.Cpu`：`registers`、`cycles`、`irq_line`、`nmi_line`              |
| `vdp`     | `segavdp` 部件：`line`、`dot`、`registers`、`cram`、`sound`、`cycles` |
| `console` | `smsmapper.Console`：内存映射、插槽使能、手柄端口                     |

`Frame` 持有每个有效点的颜色 RAM 字 `colours`、`width` 和 `height`，以及 `digest()`。

### 模块内容

| 名称                         | 内容                                       |
| :--------------------------- | :----------------------------------------- |
| `segasms.Machine`            | 一台主机                                   |
| `segasms.Frame`              | 画完的一帧                                 |
| `segasms.MODELS`             | 四个 `Model` 记录，以主机名为键            |
| `segasms.Model`              | 主机的名称、其 VDP 部件和处理器            |
| `segasms.NoFrame`            | 在允许的指令数内没有画完一帧时抛出         |
| `segasms.UnknownModelError`  | 主机名在 `smsmapper` 中不存在时抛出        |
| `segasms.UnknownRegionError` | 地区不是 `japan`、`usa` 或 `europe` 时抛出 |
| `segasms.__version__`        | 已安装的版本                               |

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

### 模块

| 模块              | 内容                                                   |
| :---------------- | :----------------------------------------------------- |
| `segasms.machine` | 主机：三个部件运行在同一个时钟上                       |
| `segasms.bus`     | 处理器的内存和端口，分派给电路板和 VDP                 |
| `segasms.frame`   | 画完的一帧，以及逐点收集它的屏幕                       |
| `segasms.models`  | 各主机的 VDP 部件和处理器，以及主机地区对应的 VDP 地区 |
| `segasms.errors`  | 本包自己抛出的所有异常                                 |
| `segasms.speaker` | 声音发生器的输出，平均为 44,100 Hz 立体声采样          |
| `segasms.record`  | 录制器：从任意映像生成动画 PNG 和 WAV                  |
| `window.play`     | 窗口：画面、声音，以及当作手柄的键盘                   |

## 时钟

VDP 的 `tick()` 是处理器时钟的三分之一，处理器在每个 T 状态结束时调用一次电路板。电路板在此让 VDP 前进三个滴答，然后把 VDP 的中断引脚复制到处理器的可屏蔽中断线，把暂停键（或 Master System 模式下 Game Gear 的 start）复制到不可屏蔽中断线。端口访问落在处理器选通信号所在之处，即 I/O 周期开始后第 10 个滴答：三个 T 状态加上第四个的第一个滴答。VDP 在那里接收写入，处理器在那里取得读取的值，而处理器采样的中断引脚，是之前每个 T 状态各自所见的那个。电路板上没有任何东西直接读取晶振，所以在所有型号上都是晶振五分之一的 VDP 滴答是最细的步进。

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

程序设置中断模式 1，在寄存器 1 中开启帧中断后等待。VDP 置起帧标志时，处理器执行完当前的 `jr` 后从 0038h 重新开始：从复位起共 43,969 个 T 状态，每个 T 状态恰好对应三个 VDP 滴答。

端口到达主机译码所指定的对象。VDP 的数据、控制和计数器端口以及声音发生器交给 VDP 封装，其余一切交给电路板。向端口 3F 写入使 TH 作为输出变高时，会在同一个 T 状态锁存 VDP 的 H 计数器；在 Game Gear 上，向端口 6 写入也会设置声音发生器的立体声寄存器。

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

Game Gear 向端口 6 的写入同样到达电路板的寄存器和立体声寄存器。按住暂停键，无论按多久都只会在 0066h 产生一次不可屏蔽中断，之后处理器继续运行。

## 启动 BIOS

BIOS 镜像和任何卡带一样是一块电路板。用 `bios=smsmapper.Cartridge(image)` 组装后，主机关闭卡带插槽从 BIOS 启动；BIOS 画出标志，把加载程序复制到 RAM 的 C700h，通过端口 3E 打开卡带，检查后再启动它。在装有 BIOS 1.3 和 _Sonic The Hedgehog_ 的 Master System 上，第 120 帧前出现标志，约第 340 帧端口 3E 打开卡带，约第 650 帧起 Sonic 开始绘制。

## 游玩与录制

```bash
scripts/play "Sonic The Hedgehog.sms"
scripts/play "Sonic The Hedgehog.sms" --replay 300
scripts/run python -m segasms.record "Sonic The Hedgehog.sms" --frames 300 --out recordings
```

`scripts/play` 打开一个窗口，运行与测试所用相同的机器，速度是逐周期模型能达到的速度，每秒几帧。没有为速度牺牲任何东西。方向键是手柄，Z 和 X 是按钮 1 和 2，Return 是暂停键（在 Game Gear 上是开始键），Backspace 是 Master System 的复位按钮，按 Escape 或关闭窗口即停止。每帧的声音在该帧画完时以正确的音高播放，直到下一帧之前保持静音。`--replay N` 先模拟 N 帧，然后以主机的速度同时播放画面和声音。`--bios FILE` 先启动原版 BIOS；不指定时，Master System 从 BIOS 交接时的状态开始，Game Gear 从复位值开始。`--scale N` 设置窗口大小，默认为 3。`--mode master-system` 让镜像在 Master System 模式的 Game Gear 上运行，用于像 R.C. Grand Prix (USA) 这样把第 42 针接地的 Game Gear 卡带。窗口从不以全屏打开。

窗口是唯一在主机上而不是在镜像中运行的工具，因为容器没有显示和声音设备。它需要 uv，由 uv 把 Python 3.12.14 和 `uv.lock` 固定的 pygame-ce 下载到检出目录之外的缓存文件夹。在 Windows 上运行 `scripts\play.ps1`。

`segasms.record` 在镜像中运行，写出 `<name>.png`（每帧按其在主机上所用的时间显示的动画 PNG）和 `<name>.wav`（16 位立体声，44,100 Hz）。每个采样是声音发生器的输出在它所跨越的各周期上的平均值。秒数由 Mark III 手册为处理器印出的 3.58 MHz 换算，用于所有型号。Game Gear 的帧是它 160 × 144 的窗口；在这里同样可用 `--mode master-system` 选择的 Master System 模式下，则是整个 256 × 192 的画面。浏览器可以播放该 PNG。

## 全面普查

```bash
scripts/run python -m conformance.census "external/Master EverDrive" "external/EverDrive GG" --frames 300 --jobs 2
```

普查按 MAME 软件列表指定的电路板，从卡带启动 Master System 和 Game Gear 卡带库中的每个镜像，并运行到帧数上限。`.sms` 镜像在 Master System 上运行，`.gg` 镜像在 Game Gear 上运行，但 MAME 清单标明把第 42 针接地的 Game Gear 卡带在 Master System 模式的 Game Gear 上运行；只有欧洲合集收录的镜像在欧洲主机上运行。对每个不同的镜像，它保留第一次显示两种以上颜色的帧，以及把所有帧摘要串联计算的 SHA-256，因此之后再运行时能立即知道任何一帧的任何一个点是否变化。它接受目录、zip 压缩包和单个镜像，输出摘要，写入 [`conformance/corpus.json`](conformance/corpus.json)，属性被破坏时以 1 退出。

两项属性决定运行结果：任何镜像都不会让机器抛出异常；每个零售镜像都在帧数上限内画出两种以上颜色。不画图的零售卡带说明本包把主机做错了。测试版、演示版等非零售镜像不画图时，会被计数并列出名称，而不判为失败。

| 上一次运行的结果                | 数量  |
| :------------------------------ | :---- |
| 两个卡带库中的条目              | 5,110 |
| 不同的映像                      | 2,608 |
| 零售映像，参与把关              | 813   |
| 在欧洲版主机上运行，每帧 313 行 | 233   |
| 在第一秒内画出两种以上颜色      | 2,014 |
| 之后才画出两种以上颜色          | 545   |
| 从未画出两种以上颜色            | 49    |

[`conformance/corpus.json`](conformance/corpus.json) 保存这些计数，以及按 SHA-256 记录的每个镜像第一次画图的帧和串联摘要，不含任何卡带的内容。

## 是否正确

各部件由各自的成员检验：Z80 由 SingleStepTests 及其普查检验，VDP 封装由世嘉手册、TI 文档及其普查检验，电路板由手册及其普查检验。本仓库只负责把它们连接起来所增加的部分：哪条线驱动哪个引脚、每个 T 状态三个滴答，以及启动路径。[`conformance/hardware.json`](conformance/hardware.json) 为每条事实附上出处，任何文档都未印出的值放在 `notStated` 下，标为未验证，并附有能确定它的测量方法。[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 列出了这些问题。

## 参与开发

| 需要                           | 位置                                                                |
| :----------------------------- | :------------------------------------------------------------------ |
| 所有关卡及其运行顺序           | [CONTRIBUTING.md](CONTRIBUTING.md)                                  |
| 给编码代理的同样内容           | [AGENTS.md](AGENTS.md)                                              |
| 本仓库与家族其他成员共享的标准 | [FAMILY.md](FAMILY.md)                                              |
| 错误报告                       | [GitHub Issues](https://github.com/gufranco/sega-sms-python/issues) |
| 安全报告                       | [SECURITY.md](SECURITY.md)                                          |

```bash
scripts/run make gate
scripts/run python segasms/machine.test.py
```

`make gate` 运行格式化工具、代码检查工具、类型检查器、YAML 检查器，以及覆盖率统计下的所有测试；覆盖率是语句和分支 100% 的硬性关卡，不排除任何内容。每个模块旁都有以其命名的测试文件，都能像上面那样单独运行。

## 参考资料

- _Software Reference Manual for the SEGA Mark III Console_，世嘉，未注明日期，重新录入的副本。45 页，184,840 字节，SHA-256 `166f09331ba9df055f7a352f10c6a7843911470bc72d9347eda4a0de86e8cfce`。不可再分发，也不在本仓库中。`scripts/run python -m conformance.documents` 从 https://segaretro.org/images/d/d6/SoftwareReferenceManualForSegaMarkIIIEU.pdf 下载，并拒绝任何其他文件。
- MAME，`hash/sms.xml` 和 `hash/gamegear.xml`，提交 `94fc55c9692b180dcb608e2e222e48315db5017a`，https://github.com/mamedev/mame，经由 `sms-mapper-python`，用于确定每个镜像所在的电路板。

## 引用

[CITATION.cff](CITATION.cff) 随每次发布由写入包版本的脚本更新。

## 许可证

MIT。见 [LICENSE](LICENSE)。
