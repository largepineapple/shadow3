# 企业知识问答 Agent

Python 3.11+ CLI，原生 Agent Loop，DeepSeek/OpenAI 兼容模型通过工具检索与读取合成制度/产品FAQ。交付回答、文档ID/版本日期/完整原文引用、资料缺口和任务状态。

**实际验证：35项测试通过；离线与最终DeepSeek套件各11/11通过。首轮10/11及冲突复测记录均保留，详见验收报告。**

评审入口：[验收报告](docs/03-evaluation.md)、[合成知识库](data/documents.json)、[主题别名](data/topics.json)、[实际输出](examples/outputs/)、[程序生成Trace](examples/traces/)。

## 安装与运行

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
python -m src.main --mode mock --input examples/inputs/conflict.json --trace examples/traces/local_mock.json --output examples/outputs/local_mock.json
python -m pytest -q
python -m examples.run_cases --mode mock
```

mock 不需要密钥，只验证工具/流程/安全边界，不能替代真实模型决策证据。CLI输出UTF-8 JSON。进程读取环境变量，不自动加载.env：

```powershell
$env:OPENAI_BASE_URL='https://api.deepseek.com'
$env:OPENAI_MODEL='deepseek-flash'
# 在本机安全配置 OPENAI_API_KEY，不写入项目或Git
python -m src.main --mode live --input examples/inputs/conflict.json --trace examples/traces/local_live.json
python -m examples.run_cases --mode live --prefix my_live
```

默认 endpoint/model 即上述值。DeepSeek 显式关闭 thinking 并设置 parallel_tool_calls=false，客户端只接受单工具响应；收到多工具会拒绝执行，并给模型有界格式修复机会。HTTP超时45秒，两次模型请求/格式错误返回incomplete。默认12轮、10次工具调用，finalize_answer也计入工具预算。超限保留已核验引用并返回incomplete。answered/conflict/not_found/needs_clarification退出码0（业务已处理），tool_failed/incomplete退出码1。

## 输入与数据

输入request_id、question和可选history（最多20条，角色仅user/assistant）。历史是问题背景，不是制度证据；上下文追问只沿用最近一条用户问题的主题，不越过无关新话题追溯旧制度，也不会把历史assistant的数字当事实。

合成文档带id、version_date、title、scope、priority及片段id/topic/text。D01写报销30天，D02写15天；没有明确适用范围与优先级，D02日期较新也不能自动覆盖D01。D03为正式员工年假5天，D04为Orion产品CSV/XLSX导出FAQ。

检索使用显式主题别名表与文档ID匹配，不使用外部网页、向量库或训练知识。模型可改写查询、补查、读取原文、根据工具失败决定重试/停止或追问。每次CLI运行重新载入指定知识库，避免沿用旧文本缓存。

## 可靠回答边界

- search_documents(query,max_results)：只返回候选元数据、片段ID、总匹配数及has_more，不把标题当原文证据。
- read_fragment(document_id,fragment_id)：只能读取已检索片段，返回原文、版本、范围和内容SHA-256。
- finalize_answer(mode,citations,decision_basis)：模型提出回答/追问/停止；应用核对引用和覆盖范围，拒绝未经读取、无关、重复、篡改或截断条件的引用。失败反馈回填模型，可继续检索或修正。

回答采用verified_extractive：应用只渲染通过校验的完整原文片段，不接受模型自由扩写的事实。这保证展示文字可回溯，不声称实现通用语义蕴含验证。模型负责选动作与证据，应用负责禁止无依据输出。

结束前必须核验知识库中与已识别问题主题相关的全部片段，不能因top-k只看到D01就忽略存在的D02。同主题不同规范文本视为潜在冲突，必须列出各方原文并请求确认适用范围/优先级，不能按日期自动选一个。如果指定库实际只含D01则可据其回答30天；替换为45天后回答与引用必须跟着变化。

状态：answered（原文支持）、conflict（列明冲突并追问）、not_found（无已核验依据）、needs_clarification（问题/上下文不明确）、tool_failed（工具失败阻碍核验）、incomplete（预算上限或模型响应异常）。检索/读取失败不能被说成“确定没有文档”。knowledge_gaps列出缺口，tool_errors保留真实错误；瞬时错误恢复后可answered，历史错误仍保留。仅本地问答，无发布接口。

## 文档替换、故障与证据

```powershell
python -m src.main --mode mock --input examples/inputs/single_document.json --documents examples/fixtures/single.json --trace examples/traces/single_local.json
python -m src.main --mode mock --input examples/inputs/changed_document.json --documents examples/fixtures/changed.json --trace examples/traces/changed_local.json
python -m src.main --mode mock --input examples/inputs/tool_failure.json --inject-failure read_fragment --failure-mode always --trace examples/traces/failure_local.json
```

fixtures/single.json移除D02；changed.json将D01原文从30天改45天并更新版本日期。once故障在对应工具首次执行前注入，重试可恢复；always持续失败。示例runner通过真实CLI运行，逐条对照实际选定知识库验证引用全文/版本、状态、退出码与Trace一致性，不手写成功日志。真实运行结果、失败记录与复测情况见03-evaluation.md。

## 限制与个人材料

这是固定主题与合成短条款的MVP：别名覆盖之外的问题会保守拒答/追问；手工topic标注需维护。不同表述即使语义等价也可能触发潜在冲突，暂不自动推理政策优先级或范围覆盖。回答是完整原文摘录，不是开放式长篇生成；不宣称完成大型企业RAG或生产身份鉴权。实际模型API费用未读取账单。个人贡献、投入时间与主观反思留给候选人本人填写。

仓库：https://github.com/largepineapple/shadow3。
