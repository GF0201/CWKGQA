## Intent 相关内容论文粘贴 Checklist

本清单用于指导如何将 `intent_workspace/paper_pack/` 中的中文正文、LaTeX 表格与附录材料粘贴进大论文初稿。默认论文结构包含「方法 / 实验结果 / 讨论与局限性 / 附录」等部分，可按需调整章节号与标题。

---

### 一、方法章节（Method / 系统设计）

- **推荐位置**  
  - 论文“方法”章节中，与主线 KGQA 方法并列的小节，例如：  
    - `第X章 方法` → 小节 `X.Y Intent 模块设计与审计`

- **需要粘贴的文件**  
  - **整段复制**：  
    - `text/intent_module_methods_zh.md`

- **作用说明**  
  - 介绍 IntentEngine v1 的规则式多标签 + 歧义检测 + 澄清生成、四种 `intent_mode`（none / rule_v1 / rule_v1_route / rule_v1_clarify），以及 `config_fingerprint`、`key_metrics` 等审计字段的来源与含义。

---

### 二、实验结果章节（Experiments / Results）

#### 2.1 Intent 消融结果（主线四种模式）

- **推荐位置**  
  - “实验结果”章节中的一个子小节，例如：  
    - `第X章 实验结果` → 小节 `X.Y Intent 模块消融实验（四种 intent_mode）`

- **正文粘贴**  
  - **整段复制**：  
    - `text/intent_ablation_results_zh.md`

- **LaTeX 表格插入**  
  - 在该小节中合适位置插入（使用 `\input{...}` 或直接复制表格环境）：  
    - 主消融表：`latex/intent_ablation_main_table.tex`  
    - 意图分布表：`latex/intent_trigger_stats_table.tex`

- **备注**  
  - 表格中的数值全部来自 `intent_ablation_main_table.csv`、`intent_ablation_compare.json` 与 `intent_trigger_stats.csv`，已转为百分比并在 notes 中说明 rule_v1 为 audit-only、route/clarify 为 behaviour-changing。

#### 2.2 阈值选择与敏感性分析

- **推荐位置**  
  - 紧接上一节，例如：  
    - `X.Y+1 Intent 阈值选择与敏感性分析`

- **正文粘贴**  
  - **整段复制**：  
    - `text/intent_thresholds_selection_zh.md`

- **LaTeX 表格插入**  
  - 插入阈值 sweep 子表：  
    - `latex/threshold_sweep_table.tex`

- **备注**  
  - 文中已明确指出 `threshold_sweep_summary.csv` 中的 `gold_macro_f1` 与 `gold_accuracy` 为空，本节只基于 `ambiguous_rate`、`multi_intent_rate`、`coverage_rate` 等字段做分析，不额外构造任务级指标。

#### 2.3 Case Study（案例分析）

- **推荐位置**  
  - 可放在“实验结果”或“分析”部分，例如：  
    - `X.Z Intent 模块案例分析（Case Study）`

- **正文粘贴**  
  - **整段复制**：  
    - `text/intent_case_study_zh.md`

- **备注**  
  - 所有案例均来自 `artifacts/casebook.md`，本节只对这些既有案例做中文总结与“为什么重要”的解释，不新增或修改样本。

---

### 三、讨论与局限性（Discussion / Threats to Validity）

#### 3.1 Threats to Validity（有效性与威胁）

- **推荐位置**  
  - 论文“讨论 / 局限性 / Threats to Validity”章节中的一个小节，例如：  
    - `第Y章 讨论与局限性` → 小节 `Y.X Intent 模块的有效性与威胁`

- **正文粘贴**  
  - **整段复制**：  
    - `text/threats_to_validity_intent_zh.md`

- **备注**  
  - 该小节强调：rule_v1 在主线中为审计-only 模式，route/clarify 为行为改变模式；并说明小样本规模、标签分布偏倚以及阈值指纹对齐假设等局限性，是答辩时回应“是否偷改主实验”的关键材料。

---

### 四、表格管理（List of Tables / 统一引用）

若论文有“表格清单”或专门的表格说明章节，可在其中统一罗列 Intent 相关表格的标签与含义（无需额外粘正文，只在主文中引用）：

- `latex/intent_ablation_main_table.tex`  
  - 主 Intent 消融表：四种 intent_mode 的 EM/F1/UNKNOWN、多意图率/歧义率/覆盖率。
- `latex/intent_trigger_stats_table.tex`  
  - 三个启用 Intent run 的 top1 意图分布。
- `latex/threshold_sweep_table.tex`  
  - 选取 `ambiguous_margin=0.15` 的阈值 sweep 子网格，展示不同阈值组合下的 ambiguous/multi-intent/coverage。
- `latex/rules_trigger_frequency_table.tex`  
  - 规则触发频率表，展示在当前 run 上最常触发的若干规则。

---

### 五、附录（Appendix）

若论文允许较长附录，建议将以下文件转写为附录各条目（可以翻译成英文，也可以中文为主、字段名保持英文）：

1. **Intent 审计字段清单**  
   - 论文附录：`附录 A Intent 审计字段`（名称可自定）  
   - 内容来源：  
     - `appendix/intent_audit_fields.md`

2. **Intent 实验工件与 schema**  
   - 论文附录：`附录 B Intent 实验工件与 schema`  
   - 内容来源：  
     - `appendix/intent_artifacts_schema.md`

3. **错误切片摘要**  
   - 论文附录：`附录 C Intent 错误切片分析`  
   - 内容来源：  
     - `appendix/intent_error_slices_summary.md`

4. **数据与字段来源总表（可并入某一附录）**  
   - 可作为某个附录的小节：  
   - 内容来源：  
     - `text/source_files_manifest.md`

---

### 六、快速自查 Checklist（可打印或在大论文边上勾选）

- [ ] 在“方法”章节添加 Intent 小节，并粘贴 `text/intent_module_methods_zh.md`  
- [ ] 在“实验结果”章节添加 Intent 消融小节，并粘贴 `text/intent_ablation_results_zh.md`  
- [ ] 在该小节中插入 `latex/intent_ablation_main_table.tex` 与 `latex/intent_trigger_stats_table.tex`  
- [ ] 在“实验结果/分析”中添加阈值敏感性小节，并粘贴 `text/intent_thresholds_selection_zh.md`  
- [ ] 在该小节中插入 `latex/threshold_sweep_table.tex`  
- [ ] 在“实验分析/讨论”中添加 Case Study 小节，并粘贴 `text/intent_case_study_zh.md`  
- [ ] 在“讨论/局限性”章节中添加 Threats to Validity 小节，并粘贴 `text/threats_to_validity_intent_zh.md`  
- [ ] 在附录中新增 2–3 个 Intent 相关附录条目，分别粘贴 3 个 `appendix/*.md` 文件内容  
- [ ] 在论文中至少一次提及 `text/source_files_manifest.md`（或其内容）作为所有 Intent 结论的“数据与字段来源总表”

