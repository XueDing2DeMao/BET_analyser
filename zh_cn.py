"""中文显示适配；仅转换说明文本，不修改分析结果或仪器字段。"""

from functools import lru_cache
from contextlib import contextmanager
import re
from threading import RLock


_MATPLOTLIB_LOCK = RLock()


@contextmanager
def matplotlib_rendering():
    """串行化 Matplotlib 排版/渲染，保护其进程级公式解析器。"""
    with _MATPLOTLIB_LOCK:
        yield


ISO_DESCRIPTIONS = {
    "Type VI": "阶梯状等温线，反映均一无孔表面上的逐层多层吸附。",
    "Type IV(a)": "存在滞后环，低相对压力区曲线向下弯曲，具有介孔材料的典型特征：先发生单层–多层吸附，随后发生介孔内的毛细凝聚。",
    "Type V": "存在滞后环，低相对压力区曲线向上弯曲，表明吸附质与吸附剂之间的相互作用较弱，同时存在介孔结构。",
    "Type I(a)": "在 p/p₀ < 0.01 时吸附量陡增，提示存在极窄微孔（< 1 nm）。常见于孔径分布较窄的活性炭或沸石。",
    "Type I(b)": "吸附量的陡增延伸至 p/p₀ 约 0.1，提示存在较宽微孔，并可能包含窄介孔，孔宽范围可延伸至约 2.5 nm。常见于金属有机框架（MOF）和分级多孔碳材料。",
    "Type II": "低相对压力区曲线向下弯曲，说明吸附质–吸附剂相互作用较强。发生不受限的单层–多层吸附，吸附层厚度随 p/p₀ → 1 持续增加。常见于无孔或大孔吸附剂；非刚性片状颗粒聚集体也可具有此类吸附支，并伴随 H3 型滞后环（Thommes 等，2015，§4.2、§4.3.2）。",
    "Type III": "等温线整体向上弯曲，吸附质–吸附剂相互作用较弱，表现为多层吸附。",
    "Unclassified": "p/p₀ < 0.35 的数据点少于 3 个，无法可靠判断低压区曲线的弯曲方向，因此暂不分类。",
}
HYST_DESCRIPTIONS = {
    "H1": "滞后环较窄且对称，吸附支和脱附支均较陡、近乎平行，通常对应均一、两端开放的圆柱形介孔。",
    "H2": "滞后环呈三角形，脱附支更陡，提示墨水瓶形孔（窄孔颈）、孔堵塞或空化效应，常见于无序介孔材料。",
    "H3": "当 p/p₀ → 1 时未出现极限吸附平台，通常与片状颗粒形成的非刚性聚集体和狭缝形孔有关，例如 C₃N₄ 等层状材料。",
    "H4": "滞后环较窄，吸附支与脱附支近乎水平且平行，常见于兼有介孔和窄狭缝形孔的微孔固体。",
    "None": "未检测到滞后环。",
}
LABELS = {
    "Unclassified": "未分类", "None": "无", "high": "高", "moderate": "中", "low": "低",
    "True": "是", "False": "否", "harkins-jura": "Harkins–Jura", "halsey": "Halsey",
    "hysteresis_area_norm": "归一化滞后环面积", "slope_ratio_max": "脱附/吸附最大斜率比",
    "slope_ratio_mean": "脱附/吸附平均斜率比", "peak_position_p/p0": "滞后环最大开度对应的 p/p₀",
    "has_plateau_ads": "吸附支是否存在平台", "flat_at_low_pp0": "低相对压力区是否平缓",
    "closure_point_p/p0": "滞后环闭合点 p/p₀", "forced_closure_N2": "是否出现 N₂ 强制闭合特征",
    "BJH pore size distribution": "BJH 孔径分布", "hysteresis classification": "滞后环分类",
    "instrument summary / comparison": "仪器参数汇总/比较", "BET summary": "BET 参数汇总",
    "S_total": "总比表面积 S_total", "S_ext": "外比表面积 S_ext", "S_micro": "微孔比表面积 S_micro",
    "V_micro": "微孔孔容 V_micro", "V_meso": "介孔与大孔合计孔容 V_meso+macro",
    "Rouquerol S_BET": "Rouquerol 比表面积 S_BET", "Rouquerol C": "Rouquerol 常数 C",
    "S_Langmuir": "Langmuir 比表面积 S_Langmuir", "n_m": "单层饱和吸附量 nₘ", "K": "吸附平衡常数 K",
    "fewer than 4 points in line-1 segment": "第一线段少于 4 个数据点",
    "fewer than 4 points in line-2 segment": "第二线段少于 4 个数据点",
    "mean pore diameter unreliable": "平均孔径估计值的可靠性不足",
    "2t < 0.7 nm": "2t < 0.7 nm，平均孔径估计值的可靠性不足",
}
MESSAGES = {
    "BET C < 2 — the isotherm is Type III/V and the BET method is not applicable (Thommes et al. 2015 §5.1.1).":
        "BET 常数 C < 2：对应 III/V 型等温线，BET 方法不适用（Thommes 等，2015，§5.1.1）。",
    "BET C < 50 — Point B cannot be identified as a single point and the interpretation of n_m is questionable (Thommes et al. 2015 §5.1.1).":
        "BET 常数 C < 50：无法把 B 点确定为单一明确的点，单层饱和吸附量 nₘ 的解释存在疑问（Thommes 等，2015，§5.1.1）。",
    "BET C ≥ 80 — the knee is sharp and Point B is well defined (Thommes et al. 2015 §5.1.1).":
        "BET 常数 C ≥ 80：等温线膝点清晰，B 点可以明确识别（Thommes 等，2015，§5.1.1）。",
    "Type I isotherm — the BET area is an apparent surface area (an adsorbent 'fingerprint'), not a realistic probe-accessible area (Thommes et al. 2015 §5.2.2, §5.1.1).":
        "I 型等温线的 BET 比表面积属于表观比表面积，可作为吸附剂的特征参数；它并不等同于探针分子实际可接近的比表面积（Thommes 等，2015，§5.2.2、§5.1.1）。",
    "The isotherm does not approach a plateau near p/p0 = 1 — the Gurvich-rule total pore volume is not valid for this (composite Type IV + Type II) isotherm (Thommes et al. 2015 §7.1).":
        "等温线在 p/p₀ 接近 1 时未趋于平台，按 Gurvich 规则求得的总孔容不适用于这类 IV 型与 II 型复合等温线（Thommes 等，2015，§7.1）。",
    "no BJH table supplied by a plain two-column isotherm": "两列等温线数据未提供 BJH 数据表",
    "no desorption branch supplied": "未提供脱附支数据",
    "no instrument Summary sheet supplied": "未提供仪器 Summary 汇总工作表",
    "total pore volume not determined": "未能确定总孔容",
    "p_rel and n must be 1-D arrays.": "相对压力和吸附量必须是一维数组。",
    "p_rel and n must be 1-D arrays of equal length.": "相对压力和吸附量必须是等长的一维数组。",
    "p_rel contains non-finite values.": "相对压力含有 NaN 或无穷大。",
    "n contains non-finite values.": "吸附量含有 NaN 或无穷大。",
    "p_rel must satisfy 0 < p/p0 < 1.": "相对压力必须满足 0 < p/p₀ < 1。",
    "n must be strictly positive (adsorbed amount > 0).": "吸附量必须大于 0。",
    "t and v must be 1-D arrays of equal length.": "膜厚与吸附量必须是等长的一维数组。",
    "Total pore volume is zero or negative.": "总孔容为零或负值。",
    "BET linearisation y-values are not strictly monotonically increasing over the selected range. Consider revising the point selection (start_pt/end_pt).":
        "所选区间内的 BET 线性化纵坐标未严格单调递增，请重新选择拟合数据点（start_pt/end_pt）。",
}
PARTS = {
    "micropore volume and surface area cannot be determined from this measurement (": "本次测量无法确定微孔孔容和微孔比表面积（",
    "). A t-plot micropore analysis needs at least one adsorption point below p/p0 ~ 0.015, ideally several lower still; check your instrument's low-pressure specification and measurement-range setting":
        "）。t-plot 微孔定量分析至少需要一个 p/p₀ 低于约 0.015 的吸附数据点，最好补充多个更低压力的数据点；请检查仪器的低压测量能力与测量范围设置",
    "§6.1 also recommends argon at 87 K over nitrogen at 77 K where surface functional groups interact with the N2 quadrupole.":
        "§6.1 还建议：当表面官能团会与 N₂ 四极矩发生相互作用时，优先选用 87 K 氩气，而非 77 K 氮气。",
    "Kelvin-equation (BJH) procedures underestimate narrow mesopore size by ~20-30%": "基于 Kelvin 方程的 BJH 方法可能低估窄介孔孔径约 20%–30%",
    "Unsupported unit in CSV header: found ": "CSV 表头的单位不受支持：检测到 ",
    "This tool expects cm3/g STP and does not convert automatically; convert the values and label the column 'cm3/g STP'.":
        "本工具要求 cm³(STP)/g，且不会自动换算单位；请先换算数值，并将列名标注为 'cm3/g STP'。",
    "CSV must have two columns ('relative pressure', 'quantity adsorbed (cm3/g STP)'); found columns: ":
        "CSV 至少需要相对压力和吸附量（cm³(STP)/g）两列；实际列名：",
    "Missing sections in CSV template: ": "CSV 模板缺少数据区：",
    "Missing summary parameters: ": "缺少仪器汇总参数：",
    "BET y-values are not strictly increasing over the selected range": "所选区间内 BET 纵坐标未严格递增",
    "not determined": "未能确定", "not reported": "不予报告",
    "No usable window found.": "未找到可用的拟合区间。",
}


def zh(value) -> str:
    """翻译程序产生的说明；未知诊断保留原文，避免猜测或掩盖错误。"""
    text = str(value)
    if text in LABELS:
        return LABELS[text]
    if text in MESSAGES:
        return MESSAGES[text]
    if "; " in text and all(part in LABELS for part in text.split("; ")):
        return "；".join(LABELS[part] for part in text.split("; "))
    if re.fullmatch(r"Type [IVX]+(?:\([ab]\))?", text):
        return text.removeprefix("Type ") + " 型"
    for source, target in PARTS.items():
        text = text.replace(source, target)
    for pattern, replacement in PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


PATTERNS = [
    (r"only (\d+) point\(s\) below p/p0 = ([\d.]+) \(need at least (\d+)\)", r"p/p₀ < \2 时仅有 \1 个数据点（至少需要 \3 个）"),
    (r"CSV isotherm needs at least (\d+) points; found (\d+)\.", r"CSV 等温线至少需要 \1 个数据点，实际仅有 \2 个。"),
    (r"CSV isotherm has (\d+) non-numeric point\(s\)\.", r"CSV 等温线有 \1 个数据点不是有效数值。"),
    (r"CSV isotherm has (\d+) point\(s\) with negative adsorbed amount\.", r"CSV 等温线有 \1 个数据点的吸附量为负。"),
    (r"BJH peak diameter ([\d.]+) nm is below 10 nm — ", r"BJH 峰值孔径（直径）为 \1 nm，小于 10 nm："),
    (r"isotherm reaches only p/p0 = ([\d.]+) \(< 0.98\); Gurvich total pore volume needs a point near p/p0 = 0.99", r"等温线最高仅达到 p/p₀ = \1（< 0.98）；Gurvich 总孔容需要 p/p₀ 接近 0.99 的数据点"),
    (r"(?:two-segment )?t-plot fit needs at least (\d+) points in window \(([^)]+)\) but only (\d+) are available\.", r"t-plot 拟合在膜厚区间（\2）内至少需要 \1 个数据点，实际仅有 \3 个。"),
    (r"BET C constant is (?:negative|NEGATIVE) \(([^)]+)\)\.(.*)", r"BET 常数 C 为负（\1），当前拟合区间不符合 BET 适用条件。请重新检查和选择相对压力区间；该拟合结果不应报告。"),
    (r"line-2 fit needs at least (\d+) points in window \(([^)]+)\) but only (\d+) are available\.", r"第二线段拟合在膜厚区间（\2）内至少需要 \1 个数据点，实际仅有 \3 个。"),
    (r"Langmuir fit requires at least (\d+) points; got (\d+)\.", r"Langmuir 拟合至少需要 \1 个数据点，实际仅有 \2 个。"),
    (r"CSV isotherm has (\d+) point\(s\) with relative pressure <= 0; expected 0 < p/p0 <= 1\.", r"CSV 等温线有 \1 个点的相对压力不大于 0；要求 0 < p/p₀ ≤ 1。"),
    (r"CSV isotherm has (\d+) point\(s\) with relative pressure > 1; expected 0 < p/p0 <= 1\.", r"CSV 等温线有 \1 个点的相对压力大于 1；要求 0 < p/p₀ ≤ 1。"),
]


def classification_description(result, *, hysteresis=False) -> str:
    """根据既有分类代码显示中文说明，保留分类算法及其判断结果。"""
    labels = HYST_DESCRIPTIONS if hysteresis else ISO_DESCRIPTIONS
    kind = result["type"]
    if kind in labels:
        return labels[kind]
    if hysteresis and "/" in kind:
        return f"{kind} 的分类得分并列。实测特征同时符合多种滞后环类型，暂不强行归为单一类型。"
    return zh(result["explanation"])


def rouquerol_report_zh(result, sample_name) -> str:
    """生成中文完整报告；样品名称按原样保留。"""
    best = result["best"]
    rules = {
        "Rouquerol-valid + R²≥0.999, then max points, then max R²": "先满足 Rouquerol 判据且 R²≥0.999，再优先最多数据点，其次最高 R²",
        "Rouquerol-valid, max R² (no window reaches R²≥0.999)": "无区间达到 R²≥0.999，在满足 Rouquerol 判据的区间中优先最高 R²",
    }
    lines = [f"Rouquerol BET 区间 — {sample_name}",
             f"候选区间数：{result['n_candidates']}", f"满足判据的区间数：{result['n_valid']}",
             f"选择规则：{rules.get(result['selection_rule'], zh(result['selection_rule']))}"]
    if best is None:
        return "\n".join(lines + ["未找到可用的 BET 拟合区间。"])
    status = "通过" if best.valid else "未通过全部判据，仅显示最佳折中结果"
    lines += [f"状态：{status}", f"相对压力区间：{best.p_min:.4f}–{best.p_max:.4f}（{best.n_points} 个点）",
              f"BET 比表面积：{best.S_BET:.3f} ± {best.sigma_S_BET:.3f} m² g⁻¹",
              f"单层饱和吸附量 Vm：{best.Vm:.4f} ± {best.sigma_Vm:.4f} cm³(STP) g⁻¹",
              f"BET 常数 C：{best.C:.2f} ± {best.sigma_C:.2f}", f"决定系数 R²：{best.R2:.6f}",
              f"C1：C > 0：{zh(best.c1_C_positive)}",
              f"C2：n(1−p/p₀) 随相对压力递增：{zh(best.c2_n1mp_increasing)}",
              f"C3：p(nₘ) 位于所选区间内：{zh(best.c3_nm_in_range)}；实验 pₘ = {best.pm_exp:.4f}",
              f"C4：理论与实验单层压力一致：{zh(best.c4_pm_consistency)}；理论 pₘ = {best.pm_theory:.4f}（允许偏差 ±20%）"]
    return "\n".join(lines)


@lru_cache(maxsize=1)
def chinese_font():
    from matplotlib import font_manager
    installed = {font.name for font in font_manager.fontManager.ttflist}
    candidates = ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC", "SimSun")
    return next((font for font in candidates if font in installed), "DejaVu Sans")


def setup_chinese_font():
    """优先使用系统中文字体，公式继续使用科学排版字体。"""
    import matplotlib as mpl
    family = chinese_font()
    mpl.rcParams.update({"font.family": [family, "DejaVu Sans"],
                         "axes.unicode_minus": False,
                         "mathtext.fontset": "custom", "mathtext.rm": family,
                         "mathtext.it": "DejaVu Sans:italic", "mathtext.bf": "DejaVu Sans:bold"})


def prepare_figure(fig):
    """把普通文本中的 Unicode 上标转为数学排版，避免中文字体缺少负指数。"""
    from matplotlib.text import Text
    superscripts = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
    for artist in fig.findobj(match=Text):
        pieces = artist.get_text().split("$")
        for index in range(0, len(pieces), 2):
            pieces[index] = re.sub(
                r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+",
                lambda match: "$^{" + match[0].translate(superscripts) + "}$",
                pieces[index],
            )
        artist.set_text("$".join(pieces))
