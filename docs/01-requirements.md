# 需求与验收

员工输入制度或产品问题及可选对话历史，获得有原文依据的回答、文档ID与版本日期、引用、资料缺口和任务状态。知识库全部为合成文档，不使用真实企业资料。

六项强制验收：明确答案；文档冲突；资料外问题；改写后的相似问题；上下文追问；工具失败。扩展验证包括单一文档、替换原文导致答案变化、产品FAQ、无上下文追问、瞬时失败恢复、top-k漏掉冲突文档、错误引用拦截及执行上限。

模型根据检索/原文/错误观察选择补查、读取、修正引用、追问或停止。不得凭空决定报销15天与30天谁正确；日期新不等于优先级高。历史assistant文本不是权威来源。引用不匹配实际原文属于关键缺陷。

输出状态answered/conflict/not_found/needs_clarification/tool_failed/incomplete，含answer、citations、knowledge_gaps、clarifying_question、conflicts与tool_errors。当前采用精确原文摘录，不生成未核验的事实解释。
