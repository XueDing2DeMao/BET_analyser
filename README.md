# BET_analyser 中文增强版 🔬

用于气体物理吸附数据的 BET / BJH、t-plot、Rouquerol 和 Langmuir 分析。本仓库在原项目基础上增加中文界面与导出、ASAP 2460 报告兼容、受限格式的 SMP 原生读取，以及 Windows 便携打包工具。

## 致谢与项目来源

本项目基于 **[Hoda Jafari（GitHub: Hj1308）](https://github.com/Hj1308)** 开发的 **[BET_analyser](https://github.com/Hj1308/BET_analyser)** 进行二次开发。感谢原作者公开源代码、分析算法、参考数据、测试和文档，为本中文增强版提供了基础。

- 原项目：<https://github.com/Hj1308/BET_analyser>
- 中文增强版维护：[XueDing2DeMao](https://github.com/XueDing2DeMao)
- 本仓库保留原项目 Git 历史、原作者署名和 [MIT 许可证](LICENSE)，遵循原许可证发布。
- 原项目的 DOI 和 [CITATION.cff](CITATION.cff) 对应原作者的软件成果。研究中使用相关方法或软件时，请保留对原项目及相应文献的引用。

本版为独立维护的衍生项目，新增功能与兼容性说明由本仓库维护者负责。

## 本版功能与启动

- 中文分析界面、图表、术语说明及 CSV 导出。
- 批量导入 SMP / XLS / XLSX / CSV，逐样品分析、失败隔离、汇总 CSV 与图表 ZIP 下载。
- 支持 ASAP 2460 单工作表 XLS/XLSX 完整报告。
- 支持已验证的 ASAP 2460 Version 3.01 氮气 SMP 文件；具体版本、校正配置及验证边界见 [SMP_FORMAT.md](SMP_FORMAT.md)。
- 提供 [Windows 便携版构建工具](tools/PORTABLE.md)，便携构建使用 Windows x64 / Python 3.11.9。

```bash
git clone https://github.com/XueDing2DeMao/BET_analyser.git
cd BET_analyser
python -m pip install -r requirements.txt
python -m streamlit run app_bet.py
```

浏览器界面启动后，可上传数据或使用 `examples/reference_mesoporous.xlsx` 合成示例。便携包中的实测样品与本地分析结果不随源码仓库发布。

下方保留原项目的算法介绍和参考文献；原作者的在线演示对应上游版本，本版中文与 SMP 功能请按上述方式在本地启动。

---

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22116897.svg)](https://doi.org/10.5281/zenodo.22116897)
![Version](https://img.shields.io/badge/version-v3.0.0-blue?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![IUPAC](https://img.shields.io/badge/IUPAC-2015%20compliant-orange?style=flat-square)
[![Streamlit](https://img.shields.io/badge/demo-Streamlit-red?style=flat-square&logo=streamlit)](https://hj1308-bet-analyser-app-bet-tk3yef.streamlit.app/)
[![tests](https://github.com/XueDing2DeMao/BET_analyser/actions/workflows/tests.yml/badge.svg)](https://github.com/XueDing2DeMao/BET_analyser/actions/workflows/tests.yml)

**[▶ 原作者在线演示 / Upstream demo](https://hj1308-bet-analyser-app-bet-tk3yef.streamlit.app/)** — no installation required. Upload an XLS/XLSX/CSV, or use `examples/reference_mesoporous.xlsx` from this repo.

**Validated against published reference values.** On the BETSI round-robin
isotherms (Osterrieth et al., *Adv. Mater.* **2022**, *34*, 2201502), the
Rouquerol range selection reproduces the published BET areas for HKUST-1
(1556 m² g⁻¹) and Zeolite-13X (833 m² g⁻¹) to within 1.1 %. The classical
0.05–0.35 p/p₀ window gives negative C constants on both and underestimates
them by 24–27 %. This comparison runs in CI on every commit
(`tests/test_betsi_reference.py`).

**Publication-Quality BET/BJH + T-Plot Analysis Tool**  
Original author: [Hoda Jafari](https://github.com/Hj1308) | MIT License

> **ODS kinetics & catalytic activity?**  
> → See [CatLab-Tools](https://github.com/Hj1308/CatLab-Tools)

---

## What is BET_analyser?

A Python tool for **publication-quality physisorption analysis** from BET instrument XLS/XLSX output, with a Streamlit web app.  
Designed for PhD-level materials characterisation — covers full IUPAC 2015 isotherm and hysteresis classification, BET regression with validity checks, **Rouquerol auto BET range selection**, BJH pore size distribution, T-Plot micropore analysis, and a **Langmuir surface-area** model.

Developed and validated for **graphene-like carbon nitride (C₃N₄)**, MOFs, zeolites, and hierarchical porous materials.

---

![4-panel BET analysis output](assets/bet_analysis_example.png)

*Output of `bet_analysis.py` on the bundled reference dataset — a synthetic
Type IV isotherm whose true surface area is known by construction
(S_BET = n_m × 4.353 = 177.28 m² g⁻¹; the tool recovers 177.28, R² = 0.999999).
Reproduce it with:*

```bash
python examples/make_reference_data.py
python bet_analysis.py --file examples/reference_mesoporous.xlsx --sample "reference"
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/XueDing2DeMao/BET_analyser.git
cd BET_analyser
pip install -r requirements.txt

# Run BET + BJH analysis (with Rouquerol auto range)
python bet_analysis.py --file C3N4.xls --sample "C3N4" --rouquerol

# Run T-Plot standalone (demo)
python tplot_analysis.py --s-bet 95.3 --vtot 0.38 --sample "C3N4"

# Or launch the web app
streamlit run app_bet.py
```

A plain two-column CSV isotherm (`relative pressure, quantity adsorbed (cm3/g STP)`,
with a header row) is also accepted directly:

```bash
python bet_analysis.py --file examples/betsi_HKUST-1.csv --sample "HKUST-1" --rouquerol
```

For a raw isotherm — no desorption branch, no BJH table, no instrument
summary — BJH, hysteresis classification, and the instrument comparison are
declined rather than estimated, and the tool names what is missing instead of
reporting zero.

---

## 🖥️ Streamlit Web App

### 批量导入与分析

1. 在侧栏勾选 **“批量导入与分析”**，一次选择多个 SMP、XLS、XLSX 或 CSV 文件，允许混合格式。
2. 设置 Rouquerol、t-plot 选项，点击 **“开始批量分析”**。每份文件作为独立样品，样品名称取自文件名；同名 SMP/XLS 不自动配对或合并。
3. 查看汇总表中的状态、数据来源和方法提示。一个文件或附加分析失败不会阻止其他文件；未支持的 SMP 可改用仪器导出的 XLS/XLSX。
4. 下载 **批量汇总 CSV**；需要图表时点击 **“生成批量结果 ZIP（含图表）”**，再下载 ZIP。压缩包包含汇总、逐样品 CSV、300 dpi BET/BJH 四联图及失败记录，同名文件通过序号区分。
5. 在 **“查看单个样品详细分析”** 中选择样品，可进入原有七个分析标签页。

批量汇总分别保留 BET 报告参数、原区间重算参数与 Rouquerol 结果，面积、单层容量和 C 的来源可区分；“完成”表示计算流程结束，不代表全部方法适用。t-plot 使用默认 Harkins–Jura 曲线及默认膜厚区间，Langmuir 使用与单文件页面相同的默认压力区间，未通过适用性检查时不导出其面积。BJH 仍依赖输入报告表。四联图使用原区间 BET，t-plot 数值及实际区间保存在 CSV 中。

文件内容、列表顺序或 Rouquerol/t-plot 选项变化会使旧批量结果失效，需要重新分析。单样品详情中调整参数不会回写批量汇总。批量结果仅保留在当前网页会话中，请及时下载。

### ASAP 2460 报告与 SMP 原始文件

- **XLS/XLSX 可直接上传**：支持 ASAP 2460 的单工作表导出报告，按报告标题和表头识别，不要求工作表名为 `Sheet1`，也不依赖固定行列位置。
- 请导出包含测试条件（`Analysis adsorptive`）、`Summary Report`、`Isotherm Linear Plot` 和 `BET Report` 的完整报告。当前计算模型使用 N₂ 数据及 cm³/g STP 吸附量单位。
- BJH 分析还需 `BJH Adsorption Pore Distribution Report` 和 `BJH Adsorption dV/dD Pore Volume`。直径和 dV/dD 会转换为项目内部的半径和 dV/dr，绘图再还原；缺少 BJH 表时相应结果显示为缺失。
- **SMP 可直接读取（受限格式）**：支持已验证的 ASAP 2460 Version 3.01 氮气原始文件，无需配套 XLS。程序按二进制目录读取样品质量、压力、累计投气量、自由空间及校正系数，还原 cm³(STP)/g 吸附/脱附等温线。BET 优先采用满足 Rouquerol 判据的区间；结果由本项目重新计算。
- **兼容范围**：目前仅有一个真实 SMP/XLS 成对样品验证；容器版本 0200、样品子集 v19、测量子集 v13、气体子集 v15、逐点饱和蒸气压，以及已验证的样品管/气体校正配置。未知版本、配置、异常目录或损坏记录会拒绝解析，并提供 XLS/XLSX 入口。不要将此支持理解为任意厂家或任意版本的 SMP 通用解析。
- 尚未解码 SMP 的仪器 BET/BJH 报告设置和分布表；需要原仪器报告值时，可勾选“改用仪器导出的 XLS/XLSX 报告”。不同的 BET 选区会产生不同结果。
- CLI 同样支持直接传入已验证的 SMP 和 ASAP XLS/XLSX。

```bash
python bet_analysis.py --file sample.XLS --sample sample --rouquerol --no-show
python bet_analysis.py --file sample.SMP --sample sample --rouquerol --no-show
```

表内缺失数值、非氮气吸附质、异常压力顺序、BET 数据不一致、BJH 孔径网格不一致及重复报告会在计算前报错。多个样品请分别导出。

官方导出流程见 [ASAP 2460 操作手册](https://downloads.micromeritics.com/Guides/ASAP-2460-Operator-Manual-Rev-H-Dec-2024.pdf)。

原生读取的公式、字段来源和验证边界见 [SMP_FORMAT.md](SMP_FORMAT.md)。

`app_bet.py` provides a browser UI for the same analyses as the CLI, without
writing Python:

```bash
pip install -r requirements.txt
streamlit run app_bet.py
```

The app exposes tabs for the **Overview**, **BET**, **Langmuir**, **Rouquerol**,
**BJH / PSD**, **T-Plot**, and a **Download** tab that renders the publication
figure and a CSV report. It accepts XLS, XLSX and CSV uploads, and surfaces the
same IUPAC validity warnings and the t-plot sufficiency gate as the CLI.

---

## 📑 Modules

| Module | File | Description |
|--------|------|-------------|
| **BET/BJH** | `bet_analysis.py` | Isotherm + hysteresis classification, BET regression, BJH PSD, cumulative pore volume, 4-panel figure |
| **Rouquerol** | `rouquerol.py` | Auto BET linear-range selection via the four Rouquerol consistency criteria (IUPAC 2015 / ISO 9277); multi-window scan; instrument-range diagnosis |
| **Langmuir** | `langmuir.py` | Langmuir monolayer capacity, affinity constant, surface area, and propagated regression uncertainty |
| **T-Plot** | `tplot_analysis.py` | Harkins-Jura T-Plot: micropore volume, S_ext, pore type distribution (micro/meso/macro %), 2-panel figure |
| **Web app** | `app_bet.py` | Streamlit UI: XLS/XLSX/CSV upload, all analyses, downloadable figure + CSV report |
| **XLS reader** | `xls_reader.py` | Legacy .xls reader via xlrd API (bypasses pandas engine guard) |

---

## 🎯 Rouquerol BET Range Selection

The classical 0.05–0.35 p/p₀ window is **not unique** — two operators can report BET areas differing by ~20 % on the same isotherm. `rouquerol.py` replaces that subjective choice with the four consistency criteria of Rouquerol et al. (2007), adopted by IUPAC 2015 and ISO 9277:

| # | Criterion | Physical meaning |
|---|-----------|------------------|
| **C1** | C > 0 (and intercept > 0) | Physically meaningful monolayer capacity |
| **C2** | n(1 − p/p₀) increases continuously | Upper bound of the valid BET region (Rouquerol transform maximum) |
| **C3** | p(n_m) lies inside the window | Monolayer pressure must be within the fitted range |
| **C4** | 1/(√C + 1) ≈ p(n_m) within ±20 % | BET theory self-consistency |

All contiguous windows (≥ 4 points) are scanned; among fully valid windows the one with the **most points** (then highest R²) is selected. The instrument's own Starting/End point range is evaluated against the same criteria — matched by **p/p₀ values**, not sheet indices.

```python
from rouquerol import select_bet_range, format_rouquerol_report

result = select_bet_range(ads[:, 0], ads[:, 1])
print(format_rouquerol_report(result, "C3N4"))
```

Run the unit tests:

```bash
pip install pytest
pytest tests/ -v
```

---

## ⚗️ Langmuir Surface Area

`langmuir.py` provides a **complementary monolayer-adsorption model** alongside BET. It fits the linearised Langmuir isotherm `(p/p0)/n` vs `p/p0` to report the monolayer capacity `n_m`, the affinity constant `K`, the specific surface area `S_Langmuir = n_m × 4.353`, the regression `R²`, and the propagated first-order uncertainty on each quantity.

S_Langmuir uses the **same N₂ cross-section factor as BET**, so the two areas are directly comparable. However, Langmuir is *not* an automatic replacement for BET: it assumes monolayer adsorption on uniform, non-interacting sites, so it should be interpreted cautiously for heterogeneous, mesoporous, or multilayer-adsorption systems. It is particularly useful to compare alongside BET for **Type I / microporous isotherms**, where the monolayer model is often physically reasonable.

```python
from langmuir import fit_langmuir_window, format_langmuir_report

result = fit_langmuir_window(ads[:, 0], ads[:, 1])
print(format_langmuir_report(result, "C3N4"))
```

---

## 📊 Output

### BET/BJH (`bet_analysis.py`)

- **4-panel figure** (300 dpi, publication-ready):
  - Panel A — N₂ Adsorption–Desorption Isotherm with hysteresis fill
  - Panel B — BET Plot with regression line + C constant validity flag (⚠ if C < 0)
  - Panel C — BJH Differential Pore Size Distribution (adsorption branch) with N₂ cavitation marker
  - Panel D — Cumulative Pore Volume + S_BET vs S_BJH comparison
- **Console report**: S_BET, C, Vm, Vp_total, d_avg, S_BJH, isotherm type, hysteresis type with scoring, Rouquerol range report (with `--rouquerol`)

### T-Plot (`tplot_analysis.py`)

- **2-panel figure**: t-plot with linear fit | pore type distribution bar
- **Console report**: S_BET, S_ext, S_micro, V_micro, V_meso, V_macro

---

## 🔬 Isotherm Classification (IUPAC 2015)

Ref: Thommes et al., *Pure Appl. Chem.* **87**, 1051–1069 (2015).

| IUPAC Type | Pore Structure | Typical Material |
|------------|----------------|------------------|
| **Type I(a)** | Ultra-micropores < 1 nm; very sharp knee at p/p₀ < 0.01 | Zeolites, activated carbons |
| **Type I(b)** | Micropores 1–2.5 nm; knee extends to ~0.1 | MOFs, hierarchical carbons |
| **Type II** | Non-porous / macroporous; S-shaped | Silica, alumina |
| **Type III** | Weak adsorbate–adsorbent interaction; convex | PTFE, ice |
| **Type IV** | Mesoporous + hysteresis; capillary condensation | SBA-15, MCM-41 |
| **Type V** | Weak interaction + mesoporosity | Certain MOFs |
| **Type VI** | Stepped; uniform non-porous surface | Graphite |

---

## 🔁 Hysteresis Classification (IUPAC 2015)

Automatically scored using 6 physical features (area, slope ratio, closure point, plateau, flatness, loop shape).

| Type | Pore Geometry | Typical Material |
|------|---------------|------------------|
| **H1** | Uniform open-ended cylinders; narrow symmetric loop | SBA-15, MCM-41 |
| **H2** | Ink-bottle pores / pore blocking; triangular loop, steep desorption | Disordered silicas |
| **H3** | Non-rigid slit-shaped aggregates; no limiting adsorption at p/p₀→1 | C₃N₄, clay minerals |
| **H4** | Narrow slit + micropores; nearly flat parallel branches | Microporous carbons |

---

## ✅ IUPAC 2015 Validity Checks

### Refusing to report what the data cannot support

A t-plot micropore analysis needs adsorption points below p/p₀ ≈ 0.015. When
a measurement lacks them, this tool says so rather than printing a zero:

| Before (v2.1.0) | After (v3.0.0) |
|---|---|
| `V_micro = 0.0 cm³/g` · `Micropore = 0.0 %` | `⚠ Micropore analysis not possible` + the reason below |

A reported zero is indistinguishable from a genuine absence of micropores.
The refusal is not. The full message names what is missing:

```text
Micropore analysis not possible: micropore volume and surface area cannot be
determined from this measurement (only 1 point(s) below p/p0 = 0.08 (need at
least 3); only 0 point(s) below p/p0 = 0.015 (need at least 1)). A t-plot
micropore analysis needs at least one adsorption point below p/p0 ~ 0.015,
ideally several lower still; check your instrument's low-pressure
specification and measurement-range setting (Thommes et al. 2015 §6.1;
Cychosz & Thommes 2018 §3). §6.1 also recommends argon at 87 K over nitrogen
at 77 K where surface functional groups interact with the N2 quadrupole.
```

*This example message is from a measurement whose lowest adsorption point sits
above p/p₀ = 0.015. The bundled reference dataset is purely mesoporous and does
not trigger this gate.*

| Check | Behaviour |
|-------|-----------|
| **BET C constant** | `UserWarning` raised if C < 0 — invalid p/p₀ range; adjust `start_pt`/`end_pt` to 0.05 ≤ p/p₀ ≤ 0.35 |
| **Monotonicity** | `UserWarning` raised if BET y-values are not strictly increasing over the selected range |
| **Rouquerol criteria** | Four-criterion consistency check on every candidate window; PASS/FAIL reported per criterion |
| **BJH branch** | Adsorption branch used to avoid the ~3.4 nm N₂ cavitation artefact in desorption BJH at 77 K |
| **Missing data** | `ValueError` with descriptive message if required XLS sheets or row labels are absent |

### Reported validity caveats

Beyond raising on hard errors, the report (and the app) now surfaces IUPAC
validity caveats that were previously silent — a low BET C constant (interpretation
of `n_m` questionable when C < 50), the BET area on a Type I isotherm being an
*apparent* area, BJH underestimating narrow mesopores by 20–30 % below ~10 nm,
and the Gurvich-rule total pore volume being invalid without a high-p/p₀ plateau
(Thommes et al. 2015 §5.1.1, §5.2.2, §7.1, §7.2, §9).

A t-plot **micropore** analysis additionally requires adsorption points below
**p/p₀ ≈ 0.015**, ideally several lower still — check the instrument's
low-pressure specification and measurement-range setting. If the measurement
lacks them, the tool refuses to report a micropore volume rather than printing
`0.0` (Thommes et al. 2015 §6.1). BJH is valid only above ~2 nm pore diameter;
below that, HK/SF or DFT methods are required (Thommes et al. 2015 §7.2, §9).

---

## 📌 Physical Constants (N₂ at 77 K)

All constants are defined as named variables at the top of `bet_analysis.py` (no magic numbers).

| Constant | Value | Definition |
|----------|-------|------------|
| `N2_BET_FACTOR` | 4.353 m² g⁻¹ per cm³(STP) g⁻¹ | N₂ cross-section σ = 0.162 nm², Avogadro + molar volume |
| `N2_TPLOT_SLOPE_FACTOR` | 15.47 m² g⁻¹ per cm³/(g·Å) | Harkins-Jura t-curve conversion |
| `N2_STP_TO_LIQUID` | 1.5468e-3 cm³(liquid N₂) per cm³(STP) | Gurvich rule: V_liquid = V_STP × N2_STP_TO_LIQUID (77 K) |
| `N2_CAVITATION_NM` | 3.4 nm | Forced closure diameter for N₂ at 77 K |

---

## 📦 Usage as a Module

```python
from bet_analysis import read_bet_xls, classify_isotherm, verify_bet
from tplot_analysis import TPlotAnalyser

# Read instrument XLS
data = read_bet_xls("C3N4.xls")
s    = data["summary"]

# Isotherm classification
iso  = classify_isotherm(data["ads"], data["des"])
print(iso["type"], iso["explanation"])

# BET regression with IUPAC validity check + Rouquerol auto range
bet  = verify_bet(data["bet_pts"], s, ads=data["ads"])
print(f"S_BET = {bet['S_BET_calc']:.2f} m²/g  |  C = {bet['C']:.1f}  |  R² = {bet['R2']:.5f}")

# T-Plot micropore analysis
tp = TPlotAnalyser(
    pressure          = data["ads"][:, 0],
    volume_adsorbed   = data["ads"][:, 1],
    s_bet             = s["S_BET"],
    total_pore_volume = s["Vp_total"]
)
tp.print_report(sample_name="C3N4")
tp.plot_tplot(save_path="C3N4_tplot.png", sample_name="C3N4")
```

---

## 🗂 Repository Structure

```
BET_analyser/
├── app_bet.py             # Streamlit web application
├── bet_analysis.py        # BET + BJH main script
├── langmuir.py            # Langmuir monolayer-adsorption analysis
├── rouquerol.py           # Rouquerol auto BET range selection
├── tplot_analysis.py      # T-Plot analysis module
├── xls_reader.py          # Legacy .xls reader (xlrd API)
├── conftest.py            # pytest path configuration
├── assets/
│   └── bet_analysis_example.png        # example 4-panel figure
├── examples/
│   ├── make_reference_data.py          # regenerates the reference dataset
│   └── reference_mesoporous.xlsx       # synthetic Type IV reference isotherm
├── tests/
│   ├── synthetic_isotherms.py          # closed-form isotherm fixtures
│   ├── test_isotherm_classification.py
│   ├── test_langmuir.py
│   ├── test_rouquerol.py
│   └── test_tplot_two_segment.py
├── .streamlit/            # Streamlit config
├── .github/workflows/     # CI
├── .python-version        # pinned dev Python (3.11)
├── packages.txt           # Streamlit Cloud system deps
├── pyproject.toml         # packaging metadata + dev extra
├── CITATION.cff           # citation metadata
├── CHANGELOG.md           # release history
├── LICENSE                # MIT
├── requirements.txt       # runtime deps (single source)
└── README.md
```

## 📁 Bundled example data

`examples/reference_mesoporous.xlsx` is a synthetic Type IV isotherm generated
from the BET equation with a known monolayer capacity, so the correct surface
area is known in advance rather than assumed. `examples/make_reference_data.py`
regenerates it and prints the check.

It contains no measured data. All four sheets (AdsDes, BET, BJH, Summary)
derive from the same monolayer capacity and pore-size distribution, so the file
is internally self-consistent: S_BET and S_BJH agree to within 1.2 %.

Every figure in this README was produced from this synthetic file. No measured
instrument data is included in this repository.

---

## Known limitations

- The t-plot uses the Harkins–Jura reference curve. Instrument software may
  use a different reference t-curve, so t-plot quantities are not directly
  comparable with instrument output.
- BJH is based on the Kelvin equation and loses physical validity below about
  2 nm pore radius. Micropore volumes should be taken from the t-plot, not
  from BJH.
- On microporous reference materials the t-plot total surface area runs above
  the BET area; the cause is under investigation and the decomposition should
  be read as indicative.
- Raw two-column isotherms cannot support BJH, hysteresis classification, or
  comparison with instrument values. These are declined rather than estimated.

---

## 📚 References

1. Thommes, M. et al. *Pure Appl. Chem.* **2015**, 87, 1051–1069. DOI: [10.1515/pac-2014-1117](https://doi.org/10.1515/pac-2014-1117) — *IUPAC 2015 physisorption classification*
2. Rouquerol, J.; Llewellyn, P.; Rouquerol, F. *Stud. Surf. Sci. Catal.* **2007**, 160, 49–56. DOI: [10.1016/S0167-2991(07)80008-5](https://doi.org/10.1016/S0167-2991(07)80008-5) — *Rouquerol consistency criteria*
3. ISO 9277:2010 — *Determination of the specific surface area of solids by gas adsorption — BET method*
4. Osterrieth, J. W. M. et al. *Adv. Mater.* **2022**, 34, 2201502. DOI: [10.1002/adma.202201502](https://doi.org/10.1002/adma.202201502) — *BETSI multi-region fitting*
5. Rouquerol, J. et al. *Adsorption by Powders and Porous Solids*, 2nd ed.; Academic Press, 2014.
6. Gregg, S.J.; Sing, K.S.W. *Adsorption, Surface Area and Porosity*, 2nd ed.; Academic Press, 1982.
7. Barrett, E.P.; Joyner, L.G.; Halenda, P.P. *J. Am. Chem. Soc.* **1951**, 73, 373–380. DOI: [10.1021/ja01145a126](https://doi.org/10.1021/ja01145a126) — *BJH method*
8. Brunauer, S.; Emmett, P.H.; Teller, E. *J. Am. Chem. Soc.* **1938**, 60, 309–319. DOI: [10.1021/ja01269a023](https://doi.org/10.1021/ja01269a023) — *BET theory*

---

## 🔀 Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full release history.

---

## 🔗 Related Repositories

| Repo | Purpose |
|------|---------|
| [CatLab-Tools](https://github.com/Hj1308/CatLab-Tools) | ODS kinetics, TOF/TON, Arrhenius, residual diagnostics |
| [EISforge](https://github.com/Hj1308/EISforge) | EIS analysis + ML |
| [sem-particle-analyzer](https://github.com/Hj1308/sem-particle-analyzer) | SEM particle sizing |
| [Raman-analysis](https://github.com/Hj1308/Raman-analysis) | Raman spectroscopy toolkit |

---

## Cite the Original Software

If you use this derivative in your research, please credit this repository and cite the original BET_analyser software:

> Jafari, H. (2026). *BET_analyser: Publication-Quality BET/BJH + T-Plot Analysis Tool* (v3.0.0). Zenodo.  
> DOI: [10.5281/zenodo.22116897](https://doi.org/10.5281/zenodo.22116897)

---

## License

MIT — free to use, modify, and distribute.
