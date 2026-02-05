## Intent 错误切片摘要（intent\_error\_slices\_summary）

本附录基于 `intent_workspace/artifacts/error_slices.md`、`intent_workspace/artifacts/intent_trigger_stats.csv` 与 `intent_workspace/artifacts/intent_ablation_compare.json`，对不同 top1 意图标签下的性能表现与误差模式做简要总结。所有数值均直接来源于上述工件，仅做四舍五入到两位小数的近似；其中各切片的基准统计以 `artifacts/error_slices.md` 为准，如本摘要中的四舍五入与原始文件存在轻微差异，一律以原始切片文件为准。

### 1. 按 top1 intent 切片的整体表现

`error_slices.md` 对源 run `exp_default_intent_rule_v1_real_v1` 给出按 top1 `intent_label` 聚合的切片结果：

- AMBIGUOUS：`n = 6`，`EM_avg ≈ 0.17`，`F1_avg ≈ 0.46`，`unknown_rate = 0.00`；
- FACTOID：`n = 4`，`EM_avg = 0.50`，`F1_avg ≈ 0.79`，`unknown_rate = 0.00`；
- FILTER：`n = 1`，`EM_avg = 1.00`，`F1_avg = 1.00`，`unknown_rate = 0.00`；
- LIST：`n = 3`，`EM_avg ≈ 0.33`，`F1_avg ≈ 0.51`，`unknown_rate = 0.00`；
- UNKNOWN：`n = 41`，`EM_avg ≈ 0.34`，`F1_avg ≈ 0.75`，`unknown_rate ≈ 0.02`。

这些切片表明，在 rule\_v1 模式下：

- AMBIGUOUS 与 LIST 类别的样本数较少（分别为 6 与 3 条），平均 EM/F1 相对较低，说明当前系统在处理“多种可能理解”或“枚举型”问题时更容易出现部分覆盖或重点偏移；
- FACTOID 与 UNKNOWN 类别的平均 F1 相对较高（约 0.75–0.79），其中 UNKNOWN 类在样本数最多（41 条）的前提下仍保持较好的平均表现，这与主线 run 中 UNKNOWN 标签的高占比（见下文）相呼应。

### 2. 与 top1 意图分布的对应关系

`intent_trigger_stats.csv` 与 `intent_ablation_compare.json.intent_label_top1` 对应 run `exp_default_intent_rule_v1_real_v1` 给出的 top1 意图分布为：

- UNKNOWN：`count = 41`，`ratio ≈ 0.75`；
- AMBIGUOUS：`count = 6`，`ratio ≈ 0.11`；
- FACTOID：`count = 4`，`ratio ≈ 0.07`；
- LIST：`count = 3`，`ratio ≈ 0.05`；
- FILTER：`count = 1`，`ratio ≈ 0.02`。

结合切片结果可以看到：

- UNKNOWN 类别既是样本量最多的类别，又在平均 EM/F1 上不低于 FACTOID 类别，这说明“被 Intent 模块标记为 UNKNOWN 的问题”并不等价于“系统在该问题上一概表现较差”；UNKNOWN 更像是一个“语义上保守”的意图标签，其下仍可能包含相对易答的 factoid 或列表型问题。
- AMBIGUOUS 与 LIST 类别样本较少且平均表现较弱，这与 casebook 中的 Clarify-applied 与 multi-intent 案例（如 draft\_33、draft\_34、draft\_54 等）相吻合：这些问题往往具备多种合理解释或涉及多种功能点，当前规则与检索策略难以在一次回答中完全覆盖。

### 3. 对澄清与路由策略的启示

从错误切片与 top1 分布中，可以对澄清（clarify）与路由（route）策略得到若干启示：

- 澄清策略的定位：  
  - error\_slices 显示 AMBIGUOUS 类别在 rule\_v1 模式下平均 EM/F1 较低；casebook 中的 Clarify-applied 案例表明，`rule_v1_clarify` 会在这些样本上强制输出 UNKNOWN。  
  - 这种策略不会提升离线 EM/F1，但能将“本就表现较差的 AMBIGUOUS 样本”显式暴露为 UNKNOWN，从而在在线场景中通过澄清问句或人工介入进行补救。

- 路由策略的边界：  
  - 对 LIST 与 MULTI\_FACT 等类别，error\_slices 和 casebook 中的 route-active 案例（如 UDP 与 PPP 问题）表明，增加检索 top\_k 或调整检索配置可以在部分样本上提高 F1，但在另一些样本上也可能引入更多噪声或不相关片段。  
  - 因此，路由策略更适合作为“在多意图或多事实问题上提高信息覆盖率”的工具，而非保证指标单调提升的万能方案。

### 4. 与整体指标的一致性检查

`intent_ablation_compare.json` 中 `exp_default_intent_rule_v1_real_v1.metrics` 给出的整体 `EM ≈ 0.35`、`F1 ≈ 0.71` 与 error\_slices 中各类 `EM_avg`、`F1_avg` 的加权平均是一致的：  
UNKNOWN 类别在样本量上占主导，并具有略高的平均 F1，使得整体 F1 被拉近到 UNKNOWN 与 FACTOID 之间；AMBIGUOUS 与 LIST 等少量困难类别则贡献了长尾误差。

本附录不尝试对上述切片做任何模型层面的解释，只在现有工件的基础上给出观测到的误差模式，为后续在 Intent 模块之上设计更细粒度的澄清、路由与人工审查策略提供参考。

