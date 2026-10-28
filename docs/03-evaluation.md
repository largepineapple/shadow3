# 验收报告

Python CLI + 原生DeepSeek Agent Loop + 本地合成检索/原文工具 + 服务端证据核验。`python -m pytest -q`实际结果：35 passed in 0.18s，见 [完整测试输出](../examples/test_results.txt)。

## 必须验收与实际运行

`python -m examples.run_cases --mode mock`：11/11通过、退出码0。[离线汇总](../examples/mock_results.json)。

最终代码执行 `python -m examples.run_cases --mode live --prefix deepseek_verified`：11/11通过、退出码0。模型deepseek-flash，服务https://api.deepseek.com。全部11个场景均有真实模型选动作、工具观察和后续决策，未用mock冒充。[真实运行汇总](../examples/deepseek_verified_results.json)。

| 场景 | 实际状态 | 秒 | 输出与真实Trace |
|---|---|---:|---|
| clear | answered | 17.109 | [输出](../examples/outputs/deepseek_verified_clear.json) / [Trace](../examples/traces/deepseek_verified_clear.json) |
| conflict | conflict | 23.593 | [输出](../examples/outputs/deepseek_verified_conflict.json) / [Trace](../examples/traces/deepseek_verified_conflict.json) |
| out_of_scope | not_found | 17.093 | [输出](../examples/outputs/deepseek_verified_out_of_scope.json) / [Trace](../examples/traces/deepseek_verified_out_of_scope.json) |
| paraphrase | answered | 23.607 | [输出](../examples/outputs/deepseek_verified_paraphrase.json) / [Trace](../examples/traces/deepseek_verified_paraphrase.json) |
| follow_up | answered | 17.365 | [输出](../examples/outputs/deepseek_verified_follow_up.json) / [Trace](../examples/traces/deepseek_verified_follow_up.json) |
| tool_failure | tool_failed | 23.306 | [输出](../examples/outputs/deepseek_verified_tool_failure.json) / [Trace](../examples/traces/deepseek_verified_tool_failure.json) |
| single_document | answered | 17.538 | [输出](../examples/outputs/deepseek_verified_single_document.json) / [Trace](../examples/traces/deepseek_verified_single_document.json) |
| changed_document | answered | 17.121 | [输出](../examples/outputs/deepseek_verified_changed_document.json) / [Trace](../examples/traces/deepseek_verified_changed_document.json) |
| product | answered | 17.488 | [输出](../examples/outputs/deepseek_verified_product.json) / [Trace](../examples/traces/deepseek_verified_product.json) |
| ambiguous | needs_clarification | 17.558 | [输出](../examples/outputs/deepseek_verified_ambiguous.json) / [Trace](../examples/traces/deepseek_verified_ambiguous.json) |
| transient_failure | answered | 23.171 | [输出](../examples/outputs/deepseek_verified_transient_failure.json) / [Trace](../examples/traces/deepseek_verified_transient_failure.json) |

最终真实套件总耗时 214.969 秒。API费用未读取账单，不报告确切金额。

六项强制验收对应clear、conflict、out_of_scope、paraphrase、follow_up、tool_failure；其余为单源制度、替换文档、产品问题、无上下文追问和瞬时失败恢复。

## 关键业务证据

- 明确答案：D03原文为正式员工每年5天年假，模型检索并读取后引用原文回答。
- 冲突：实际读取D01的30天及D02的15天，引用两份文档/版本/原文并请求确认适用制度；未因D02更新而选15天。
- 资料外：两次不同检索均无依据后not_found，不填充外部天气知识。
- 改写/上下文：相似问法和有明确最近user话题的追问都引用D03；不引用历史assistant内容。
- 工具失败：原文读取失败后有限重试，仍失败返回tool_failed，引用为空；once注入则重试成功answered，历史错误仍保留。
- 文档替换：single库只有D01时回答30天；changed库实际原文改45天、版本更新到2026-10-20，回答与引用同步变45天、内容SHA-256变化。
- 模型结束动作也要通过证据校验。无上下文追问场景中模型曾试图提前finalize，应用返回SEARCH_REQUIRED；模型随后检索再结束。没有把模型声明当成成功。

## 真实失败与修复记录

首轮 `--prefix deepseek` 实际10/11通过，冲突场景检索后连续两次返回多工具响应，被客户端单工具校验拒绝，返回incomplete且未给唯一答案。原始失败 [Trace](../examples/traces/deepseek_conflict.json) 与 [首轮汇总](../examples/deepseek_results.json) 原样保留。paraphrase中还有一次格式错误经有界重试恢复，也未移除。

强化系统的单工具数组约束，并把具体格式错误反馈给模型后，`--prefix deepseek_retry --cases conflict`复测1/1通过；该单项Trace仍有一次格式错误后恢复，见 [复测汇总](../examples/deepseek_retry_results.json)。随后用最终代码重新执行完整11项，deepseek_verified前缀的套件11/11通过。三个阶段使用不同文件，不覆写失败日志，也不把试跑记录改为成功。

离线首次runner还遇到Windows中文stdout编码不一致；CLI显式UTF-8输出后重新执行，11例通过。该修复不改变证据内容。

## 自动化与独立核对

35项pytest覆盖六项验收、原文替换/添加冲突条款、top-k遗漏冲突来源时拒答、完整原文引用、截断/篡改/未读/无关引用拒绝、工具持续失败和once恢复、上下文来源与新话题隔离、读取前检索、步数/工具限制及保留已核验片段、请求/文档校验、HTTP凭据脱敏、多工具拒绝、模型根据INVALID_CITATION反馈修正及错误次数上限、相同文本不误判冲突。

独立核对mock和最终live的输出与Trace逐项相等；每个引用与所选目录原文和版本相等，存在先前成功read_fragment观察，内容SHA-256正确。知识库/输入JSON校验、源码编译和文档本地链接检查通过。逐字节凭据扫描未发现本次密钥，临时模型测试进程清除密钥后退出。

## 完成定义与剩余项

- [x] CLI可复制运行；mock无密钥；live实际调用模型与动态调整动作。
- [x] 六项强制验收有单元/集成测试和真实模型记录。
- [x] 引用有文档ID、版本日期、完整原文和内容指纹；不接受未经读取/无关/改写引用。
- [x] 冲突列原文并追问，不按新旧日期擅自选答案；替换文档后答案同步变化。
- [x] 资料不足/工具错误/执行上限如实返回，不伪造执行记录。
- [x] README、五份文档、测试、合成数据、输入/输出/Trace、依赖和环境变量样例齐全。
- [ ] 候选人本人填写04-ai-usage.md的真实贡献/时间及05-retrospective.md的个人反思。

当前是固定主题合成条款的提取式QA，不是通用语义蕴含或大型企业RAG评测。topic/别名是人工维护的，文本差异采用保守潜在冲突机制，不自动推理政策范围与优先级；可能产生额外追问。未实现真实企业鉴权、外部知识库或开放式无约束答案生成。固定案例成功不保证模型每次严格遵循格式；无法修复时仍有界返回incomplete。

仓库：https://github.com/largepineapple/shadow3。最终提交SHA以git log及交付消息为准。
