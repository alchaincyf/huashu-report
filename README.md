# huashu-report

做机构级研究报告的 Agent Skill。规范不是想出来的，是从 2026 年顶级机构报告的实物里反向拆出来的（下载到 42 个 PDF，进量化统计的是 41 份；来源清单与解剖数据在 `corpus/`）。

装上之后，你的 agent 做行业报告、白皮书、年度调研、数据洞察和 arXiv 论文时，会按研究员 / 编辑 / 信息设计师 / 数据可视化师四个角色依次工作，而不是把搜到的资料码成一个文档。

## 为什么会有这个 skill

2026 年 8 月我把能下载到的顶级机构 AI 报告全下了一遍——Stanford HAI、McKinsey、BCG、OpenAI、Anthropic、PwC、Deloitte、World Bank、Reuters Institute 等等，42 个 PDF（世行 WDR 的概览册与正文是同一份报告的两个文件，量化统计按 41 份算），后来又补入 2 份。原本只是想找选题弹药，读到一半发现更值钱的东西在版式和行文里：这些机构在结构、口径标注、图表标题、配色上有一套高度一致的做法，而 AI 默认写出来的「报告」全不长这样。

于是把这批实物拆了，规范落成这个 skill。

三条最反直觉的实测结论：

- **正文 98%（40/41 份）用近黑色，品牌色在正文里的字符占比中位只有 2.8%。** 品牌色是稀缺资源，只出现在图表、章节标记和强调数字上。想把正文染成品牌色之前，先想起这条。
- **图表标题写结论，不写主题。** 「年轻从业者的岗位缺口在持续扩大」而不是「分年龄段就业变化」。研报型是唯一的例外。
- **顶级报告都专门写一段「预先反驳自己」。** Stanford 那份 Canaries 主动把结论降级成「描述性指标不是因果估计」，这段反而成了所有人引用它时的锚点。

## 装它

skill 是纯文本 + 三个 Python 文件，不依赖任何服务，跨 agent 通用。

### Windows 11 说明

本 Skill 的写作规范跨平台；PDF 渲染器还需要本机安装 Chromium/Playwright 和 Poppler（`pdfinfo`、`pdftotext`、`pdftoppm`）。建议使用 Python 3.11 独立虚拟环境，先运行：

```powershell
python assets\doctor.py
```

Poppler 不在 PATH 时，可用 `HUASHU_PDFINFO`、`HUASHU_PDFTOTEXT`、`HUASHU_PDFTOPPM` 指向对应的 `.exe`。不要把真实浏览器用户资料目录交给报告流水线。

建议在提交前运行 `python -m unittest discover -s tests`；Python 3.14 可能可用，但生产环境建议固定 Python 3.11 虚拟环境。

```bash
# Claude Code
git clone https://github.com/alchaincyf/huashu-report ~/.claude/skills/huashu-report

# 三家 agent 共用一个 skill 池的话
git clone https://github.com/alchaincyf/huashu-report ~/.agents/skills/huashu-report
```

也可以直接把整个目录打成 zip，上传到支持自定义技能的产品里（豆包工作的「技能 → 新建 → 上传技能」实测可用，会完整跑通里面的生产流水线）。

装好之后不需要专门喊它，说「做一份 XX 的调研报告」「出个白皮书」就会触发。

## 里面有什么

```
SKILL.md              身份、三个开工前必答的问题、六种报告原型的选型表
references/
  结构骨架.md          六种原型各自的章节骨架
  行文.md              句子层面的规范：口径怎么标、hedge 怎么打
  研究深度.md          整理 → 机制 → 文献定位三层增值，报告里不写什么
  视觉系统.md          排版系统：字号阶、网格、数据源行格式
  视觉方向库.md        配色与风格方向
  图表模式库.md        8 种图型各自适用于比什么
  生产流水线.md        三文件架构（数据表 / 生成器 / 渲染器）+ 8 个具体的坑
  实证基线.md          41 份报告的量化基线，规范的出处
  科普.md              面向无背景读者的报告原型（三幕骨架）
  论文.md              arXiv 论文原型（IMRaD / LaTeX）
assets/
  chart.py             8 种图型的内联 SVG 库，支持负值
  render.py            渲染 + 目录页码自动回填 + 机械自检
  base.css             基础样式
corpus/
  samples.md           43 份样本清单：机构、日期、页数、官方链接、许可状态
  anatomy.json         41 份的量化解剖数据，实证基线的原始出处
```

`assets/` 里那两个 Python 文件是最省时间的部分——直接复制改配置，不要重造。

`corpus/` 是规范的出处，不是资料下载站——43 份报告的来源清单和量化结果在这里，报告实物一份不放（它们共约 234MB，而这是个要被人 clone 进 agent 的 skill 仓库）。想让量化基线可核查、或者给自己领域的报告立一套基线，都从那里的 `anatomy.json` 开始量——它覆盖全部 41 份，且只含量化结果不含原文。

## 一条判据

写报告时反复会遇到「这段要不要留」。判据只有一条：

> 把这句话删掉，读者对研究结论的判断会不会改变？不变就是工作日志，删。

样本框、纳入排除标准、口径统一属于方法论，必须写；工具怎么装的、脚本哪里报错了、中间返工了几次属于工程记录，不写。

## 已知的边界

- 单篇文章、PPT、演示稿不适用，那是别的活
- 规范来自英文机构报告的实物，中文语境下的行文习惯需要自己再校一遍
- 41 份的样本框偏 AI 与科技主题，其他领域的报告惯例可能不同

---

**English**

`huashu-report` is an agent skill for producing institution-grade research reports — industry reports, white papers, annual surveys, data insights, and arXiv papers. The conventions were reverse-engineered from real reports published in 2026 (42 PDFs retrieved, 41 in the quantitative baseline) by Stanford HAI, McKinsey, BCG, OpenAI, Anthropic, PwC, Deloitte, the World Bank, and others, rather than written from intuition.

Three findings that surprised me: body text is near-black in 40 of 41 reports (brand color occupies a median 2.8% of body characters); chart titles state the conclusion, not the topic; and every top-tier report devotes a section to arguing against itself.

The source list and the measured anatomy of that corpus live in `corpus/` — official links and quantitative metrics only, no report files (the 43 reports run to ~234MB, and this is a skill repo people clone).

Plain text plus three Python files, no external services, agent-agnostic. Clone into your agent's skills directory and it triggers on any request to produce a report.

MIT licensed.
