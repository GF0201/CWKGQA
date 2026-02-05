# Intent casebook (from mainline runs)

- Source runs (none / rule / route / clarify):
  - `exp_default_intent_none_real_v1`, `exp_default_intent_rule_v1_real_v1`, `exp_default_intent_route_real_v1`, `exp_default_intent_clarify_real_v1`


## Clarify-applied cases (歧义 + 强制 UNKNOWN)

### Case 1: id=draft_33
- Question: 拥塞避免算法 有哪些规定或要求？
- Intent prediction: LIST(1.00), AMBIGUOUS(1.00)
- Clarification question: 这个问题可能有多种理解：LIST, AMBIGUOUS。请问你更关心哪一类？
- Clarification options: LIST, AMBIGUOUS
- Before clarify (rule_v1 final_answer): '每经过一个往返时间RTT，发送方的拥塞窗口cwnd的大小就加1'
- After clarify (clarify final_answer): 'UNKNOWN'
- EM/F1 before → after: True / 1.000 → False / 0.000
- Triggered rules: ambiguous_which, list_enumerate

### Case 2: id=draft_34
- Question: X.509 有哪些规定或要求？
- Intent prediction: LIST(1.00), AMBIGUOUS(1.00)
- Clarification question: 这个问题可能有多种理解：LIST, AMBIGUOUS。请问你更关心哪一类？
- Clarification options: LIST, AMBIGUOUS
- Before clarify (rule_v1 final_answer): '规定数字证书必须包括的字段,规定根认证中心为公认可信的认证中心'
- After clarify (clarify final_answer): 'UNKNOWN'
- EM/F1 before → after: False / 0.537 → False / 0.000
- Triggered rules: ambiguous_which, list_enumerate

### Case 3: id=draft_54
- Question: TCP 有哪些要求？
- Intent prediction: LIST(1.00), AMBIGUOUS(1.00)
- Clarification question: 这个问题可能有多种理解：LIST, AMBIGUOUS。请问你更关心哪一类？
- Clarification options: LIST, AMBIGUOUS
- Before clarify (rule_v1 final_answer): '区分有线网络拥塞和无线链路拥塞'
- After clarify (clarify final_answer): 'UNKNOWN'
- EM/F1 before → after: False / 0.000 → False / 0.000
- Triggered rules: ambiguous_which, list_enumerate


## Multi-intent cases

### Case 4: id=draft_54
- Question: TCP 有哪些要求？
- Intent prediction: LIST(1.00), AMBIGUOUS(1.00)
- is_multi_intent: True
- is_ambiguous: True
- Final answer (rule_v1): '区分有线网络拥塞和无线链路拥塞'
- EM/F1: False / 0.000

### Case 5: id=draft_25
- Question: PPP协议 提供哪些功能或服务？
- Intent prediction: AMBIGUOUS(1.00), FACTOID(0.80)
- is_multi_intent: True
- is_ambiguous: False
- Final answer (rule_v1): '在链路打开状态时PPP端点可以彼此向对方发送分组,在链路建立状态时建立链路层的LCP连接,通过NCP分配临时IP地址,允许双方协商使用压缩的TCP和IP首部,使用IP控制协议IPCP'
- EM/F1: False / 0.103

### Case 6: id=draft_7
- Question: RTCP 提供哪些功能或服务？
- Intent prediction: AMBIGUOUS(1.00), FACTOID(0.80)
- is_multi_intent: True
- is_ambiguous: False
- Final answer (rule_v1): '服务质量监视与反馈,多播组成员的标志,媒体间的同步,服务质量的监视与反馈,实时传送控制'
- EM/F1: False / 0.340


## Route-active cases (retrieval/answer changed)

### Case 7: id=draft_5
- Question: UDP 提供哪些功能或服务？
- Intent prediction (route): AMBIGUOUS(1.00), FACTOID(0.80)
- Retrieved triples: rule_v1=10, route=20
- Final answer: rule_v1='复用和分用功能以及差错检测功能,无连接的尽最大努力的数据传输服务', route='复用和分用功能以及差错检测功能,无连接的尽最大努力的数据传输服务,简单的差错检测功能'
- EM/F1: rule_v1=False/0.652, route=False/0.545

### Case 8: id=draft_25
- Question: PPP协议 提供哪些功能或服务？
- Intent prediction (route): AMBIGUOUS(1.00), FACTOID(0.80)
- Retrieved triples: rule_v1=10, route=20
- Final answer: rule_v1='在链路打开状态时PPP端点可以彼此向对方发送分组,在链路建立状态时建立链路层的LCP连接,通过NCP分配临时IP地址,允许双方协商使用压缩的TCP和IP首部,使用IP控制协议IPCP', route='封装方法、链路控制协议LCP、网络控制协议NCP'
- EM/F1: rule_v1=False/0.103, route=False/0.187


## Failure/boundary cases

### Case 9: id=draft_33
- Question: 拥塞避免算法 有哪些规定或要求？
- Final answer (rule_v1 / clarify): '每经过一个往返时间RTT，发送方的拥塞窗口cwnd的大小就加1' / 'UNKNOWN'
- EM/F1 (rule_v1 / clarify): True/1.000 / False/0.000

### Case 10: id=draft_34
- Question: X.509 有哪些规定或要求？
- Final answer (rule_v1 / clarify): '规定数字证书必须包括的字段,规定根认证中心为公认可信的认证中心' / 'UNKNOWN'
- EM/F1 (rule_v1 / clarify): False/0.537 / False/0.000
