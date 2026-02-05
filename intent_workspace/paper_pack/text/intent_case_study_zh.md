## Intent 模块案例分析（Case Study）

本节基于 `intent_workspace/artifacts/casebook.md`，选取若干具有代表性的样本，分别覆盖澄清应用（clarify-applied）、多意图（multi-intent）、路由生效（route-active）以及失败/边界场景。每个案例均保留原始 run 与 id 信息，方便与主线 run `exp_default_intent_*_real_v1` 对照。

### Clarify-applied：歧义问题的保守处理

**Case 1（id=draft_33，clarify-applied）**  
问题 “拥塞避免算法 有哪些规定或要求？” 在 `casebook.md` 中被判定为同时命中 LIST 与 AMBIGUOUS 两类意图：`LIST(1.00), AMBIGUOUS(1.00)`。在 `rule_v1` 模式下，系统直接输出关于拥塞窗口随 RTT 增长的回答，EM/F1 为 `True / 1.000`；而在 `rule_v1_clarify` 下，由于被标记为歧义并启用澄清逻辑，最终回答被强制设为 `UNKNOWN`，EM/F1 变为 `False / 0.000`。这一案例说明：澄清模式在离线评测中可能牺牲单点指标，以换取对模糊需求更安全、可解释的处理。

**Case 2（id=draft_34，clarify-applied）**  
问题 “X.509 有哪些规定或要求？” 同样被预测为 `LIST(1.00), AMBIGUOUS(1.00)`，触发 `ambiguous_which` 与 `list_enumerate` 两条规则。在 `rule_v1` 模式中，系统给出证书字段与根认证中心相关要求的答案，F1 约为 `0.537`；在 `rule_v1_clarify` 下，最终回答被强制为 `UNKNOWN`，F1 降至 `0.000`。这一案例展示了，对于可能存在多种解释空间的安全相关协议问题，澄清策略倾向于将“看似合理但未必符合用户真实意图的回答”转化为 UNKNOWN，从而降低误导性回答的风险。

**Case 3（id=draft_54，clarify-applied）**  
问题 “TCP 有哪些要求？” 同时命中 LIST 与 AMBIGUOUS，澄清问题明确列出了两种可能的意图类型。在 `rule_v1` 模式下，系统直接返回与拥塞控制相关的一句话总结，EM/F1 均为 `0.000`；在 `rule_v1_clarify` 中，由于维持 UNKNOWN 输出，EM/F1 仍为 `0.000`。该案例表明，对于本身就答错的问题，澄清策略不会提升离线 F1，但能够显式暴露“当前答案不可靠”，有助于后续在线澄清或人为介入。

### Multi-intent：多意图与歧义的交叉

**Case 4（id=draft_54，multi-intent + ambiguous）**  
在多意图小节中，`casebook.md` 将同一问题 “TCP 有哪些要求？” 标记为 `is_multi_intent=True`、`is_ambiguous=True`。这说明当前规则在该问题上既识别出多个可能意图，又认为它们之间区分度不足。结合 Clarify-applied 小节可见，这类样本在澄清模式中往往被强制 UNKNOWN，是 Intent 模块重点关注的“高风险”问题类型。

**Case 5（id=draft_25，multi-intent 非歧义）**  
问题 “PPP协议 提供哪些功能或服务？” 的预测为 `AMBIGUOUS(1.00), FACTOID(0.80)`，被标记为 `is_multi_intent=True` 且 `is_ambiguous=False`。在 `rule_v1` 模式下，系统给出了较长的功能列表，F1 约为 `0.103`。这个案例显示：即便系统能够识别出多种潜在意图，并将其视为“多意图而非歧义”，在没有引入路由或澄清逻辑时，最终回答仍可能因覆盖不全或重点不对而得分较低。

**Case 6（id=draft_7，multi-intent 非歧义）**  
问题 “RTCP 提供哪些功能或服务？” 预测为 `AMBIGUOUS(1.00), FACTOID(0.80)`，同样是 `is_multi_intent=True` 且 `is_ambiguous=False`。`rule_v1` 模式下的答案列举了服务质量监视与反馈、多播组成员标志、媒体同步等多项功能，但 F1 约为 `0.340`。这一案例说明，多意图识别本身并不能保证对所有功能点的完整覆盖，但能在审计层面揭示“该问题涉及多个功能维度”，为后续的路由与补全策略提供基础。

### Route-active：意图驱动的检索与答案差异

**Case 7（id=draft_5，route-active）**  
问题 “UDP 提供哪些功能或服务？” 在 route-active 小节中被标为意图预测 `AMBIGUOUS(1.00), FACTOID(0.80)`。相比 `rule_v1`，路由模式 `rule_v1_route` 将检索的三元组数量从 10 提升到 20，答案从“复用和分用功能以及差错检测功能, 无连接的尽最大努力的数据传输服务”扩展为在末尾增加“简单的差错检测功能”。然而，两种模式下的 F1 分别约为 `0.652` 与 `0.545`，说明在该样本上，一味增加检索范围并不一定带来离线指标提升，但能让审计者看到答案信息密度与覆盖范围的变化。

**Case 8（id=draft_25，route-active）**  
在 route-active 小节中，同一 PPP 问题的 route 模式答案被简化为“封装方法、链路控制协议 LCP、网络控制协议 NCP”，而 rule_v1 模式则列出了更长的功能列表。对应的 F1 从约 `0.103` 提升到约 `0.187`。这一案例表明，对于部分高度结构化、教材式定义的问题，路由策略可以帮助系统聚焦更规范的定义片段，从而在离线评测中获得更好的重叠度。

### Failure / Boundary：澄清与主线指标的张力

**Case 9 与 Case 10（失败/边界样本）**  
在 Failure/boundary 小节中，`casebook.md` 再次对 `draft_33` 与 `draft_34` 进行对比，展示 `rule_v1` 与 `rule_v1_clarify` 在相同问题上的 EM/F1 变化：前者分别达到 `True/1.000` 与 `False/0.537`，后者则统一变为 `False/0.000`。这些案例提醒我们：澄清与强制 UNKNOWN 的策略在离线指标上可能被视为“退步”，但从安全性与用户信任角度，它通过显式拒绝不确定回答，为后续在线交互或人工审查留出了空间。

总体来看，`casebook.md` 中的这些样本共同说明：Intent 模块不仅提供了可解释的标签与规则触发信息，还通过路由与澄清机制，在“高风险、多意图、歧义”问题上主动暴露系统的不确定性，从而为下游的安全策略设计、产品体验与人工审查流程提供了可操作的支点。

