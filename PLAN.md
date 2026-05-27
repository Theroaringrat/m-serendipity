# M-Serendipity 项目计划
**最后更新：2026-05-27**

---

## 项目定位

帮学生判断"这个 Lab 值不值得联系"，回答三个核心问题：
1. 研究方向和我的兴趣匹不匹配？
2. 这个 Lab 带不带本科生？
3. 有没有机会进去？

**技术定位**：面向暑假实习申请的核心 portfolio 项目，覆盖完整 RAG + Agent 链路。

---

## JD 技能图谱

| JD 要求 | 状态 | 覆盖阶段 |
|---------|------|---------|
| RAG（LangChain、ChromaDB、Embedding） | ✅ | Phase 1 |
| 结构化输出（Pydantic） | ✅ | 已有 |
| Agent（Tool calling、ReAct） | ✅ | Phase 2a |
| 多轮对话 + 记忆 | ❌ | Phase 2b |
| 工程基础（数据管道） | ✅ | Phase 1 |
| LangGraph | ✅ | Phase 2a |

---

## Phase 1：数据层

**目标**：35 位教授的 lab 数据进 vector_db，质量撑得起简历描述。

**爬虫方案**：Crawl4AI（Playwright）两层架构（professors_index.json → lab 主页 → 子页，最多1层）
- 爬取目标：research / people / join / teaching 四类页面
- 清洗：rules-based（去导航/图片/重复行/空表格行）
- 降级：403 / 无lab URL → fallback 到 faculty profile 页

**Content Cap**：

| page_type | 回答的问题 | Cap |
|-----------|-----------|-----|
| research | 研究方向匹不匹配？ | 10000 chars |
| home | 总体定位兜底 | 6000 chars |
| people | 带不带本科生？ | 不截断 |
| join | 有没有机会进去？ | 不截断 |
| teaching | 辅助了解教授方向 | 不截断 |

**简历描述**：Built a RAG pipeline covering 35+ professors using LangChain + ChromaDB + Gemini Embedding

---

## Phase 2：Agent 能力

**目标**：从单步 RAG Pipeline 升级为 ReAct Agent，让 LLM 主动决定搜索策略。

### 2a. 两个工具 + ReAct Agent ✅

**核心设计**：控制流从固定 pipeline 改为 Agent 驱动的循环——每步执行完 LLM 自己决定下一步。

**Tool 1: `search_by_direction(query: str)`**
- 向量检索，filter `page_type in [research, home]`
- 返回：教授名单 + 研究方向摘要
- 作用：让 Agent 找方向匹配的候选人

**Tool 2: `get_professor_details(name: str)`**
- 直接从 `deep_scraped_professors.json` 按名字取，不走向量检索
- 返回：该教授所有页面（research + join + people）完整内容
- 作用：让 Agent 对具体候选人做深度核查（招不招本科生、具体研究内容）

**Agent 流程**（运行时由 LLM 动态决定）：
```
学生输入 → Agent 推理搜索策略
  → search_by_direction(...)   # 找方向候选
  → get_professor_details(...) # 对感兴趣的教授深查
  → 反思：信息够了吗？
  → Final Answer
```

输出：自由文本推荐，UI 直接展示。结构化卡片 UI 留到后续迭代。

**简历描述**：Replaced single-step RAG with a multi-tool ReAct agent; LLM dynamically routes between semantic search and direct lookup tools

---

### 2b. 多轮对话追问（后续）

学生问"为什么 Mavrogiannis 排第一"或"他招本科生吗"，Agent 实时调工具回答。
依赖：`st.session_state` + `ConversationBufferMemory`

### 2c. Publications 实时抓取（后续）

不预先 ingest，追问时 Agent 实时抓取最近5篇论文。

### 2d. LangGraph 重写（已完成，集成在 2a）

使用 `langgraph.prebuilt.create_react_agent` 替代 AgentExecutor，原生支持 Gemini function calling，无需 text-parsing ReAct。

---

## Phase 3：架构升级（可选）

LangGraph 重写 Agent 流程。Phase 1 + 2 稳定后根据面试反馈决定。

---

## Ideas（有余力时）

- 核心论文概括（LLM 生成代表作摘要）
- 学生主页抓取（推断 lab 适合什么背景的人）
- 出版质量/频率评估（venue 档次作为 lab 活跃度信号）

---

## 执行顺序

```
Phase 1（爬虫 → ingest）✅ → Phase 2a（两工具 + ReAct）✅ → Phase 2b（追问）← 当前 → Phase 2c（Publications）→ Phase 3（可选）
```

每一步都是可独立交付的节点。

---

# 工程日志

---

## 当前状态（2026-05-14）

- [x] 基础 RAG 管道（3 位教授，1674 chunks）
- [x] 结构化输出、Gemini Embedding、Streamlit 前端
- [x] 全站摸底（35 位教授，survey.py）
- [x] professors_index.json 建立
- [x] deep_scraper.py 完整重写（Crawl4AI，两层架构）
- [x] 10 个 lab 验证 + 数据质量问题定位
- [x] 表格噪声规则 fix（空行 / `| --- |` / 图片格）
- [x] Content cap 设定（home=6000, research=10000, people/join/teaching 不截）
- [x] page_type metadata 写入 vector_db
- [x] backend 去重修复（k=12 raw → 按教授名去重 → 最多6人）
- [x] backend prompt 修复（动态 n_candidates，消除 "Analysis unavailable"）
- [x] 4 类查询初步测试，评分逻辑达标

---

## 2026-05-12 爬虫重写记录

### 35 lab 摸底结果

| 类别 | 数量 | 处理方式 |
|------|------|---------|
| 正常可抓 | ~20 | 两层架构直接跑 |
| 403 封锁 | 5 | fallback profile |
| JS 渲染 | ~10 | Crawl4AI 直接处理 |
| 无 lab URL | 3 | fallback profile |

### 10 lab 测试发现的数据质量问题（均已修复）

| 问题 | 影响 lab | 修复方式 |
|------|---------|---------|
| HTML 布局表格 → 大量空 `\|  \|` 行 | Mavrogiannis、Ozay | 正则过滤空表格行 |
| 同 URL 存两次（不同 page_type） | Ozay、Skinner | 过滤与 homepage 相同的子页 URL |
| 平台导航噪声（Google Sites / WordPress） | Robert、Du、Skinner | Crawl4AI DOM 解析天然过滤 |
| JS 渲染子页内容为空 | Panagou projects | Crawl4AI 直接处理 |
| Alumni / Grants 段落撑爆字符 | Berenson、Robert | research cap=10000 |

---

## 2026-05-12 Crawl4AI 迁移记录

迁移动因（requests 方案的瓶颈）：

| lab | requests 结果 | Crawl4AI 结果 |
|-----|-------------|--------------|
| CURLY（Ghaffari，Google Sites） | 36 chars（JS渲染失败） | 3562 chars ✅ |
| Mavrogiannis | 22368 chars（大量空表格） | 2985 chars 干净内容 ✅ |

决策：全量迁移 Crawl4AI，不保留 requests 路径。PruningContentFilter 阈值不稳定，不启用，保留手写规则清洗层。

---

## 2026-05-14 Backend 修复

**Bug 1: 同一教授重复出现**
- 原因：`similarity_search(k=6)` 直接用，热门教授多个 chunk 占满所有 slot
- 修法：`similarity_search(k=12)` → 按教授名去重 → 最多保留6个不同教授

**Bug 2: "Analysis unavailable"**
- 原因：prompt 写死 "following 3 candidate professors"，LLM 只返回3个 match
- 修法：动态传 `n_candidates`，prompt 明确 "You MUST provide exactly {n_candidates} entries"

### 初步测试结果

| 问题类型 | 结果数 | 质量评估 |
|---------|-------|---------|
| HRI / 导航 | 3个 | Mavrogiannis 10/10 正确；结果少因 DB 只有10个教授 |
| 哪些 lab 带本科生 | 5个 | Moore/Skinner/Gregg 前三，评分符合事实 |
| 哪些 lab 在招人 | 6个 | Moore 10/10 正确；Ozay/Skinner 低分符合实际 |
| 自主系统+本科机会 | 6个 | Panagou/Berenson 9/10，方向匹配 |

DB 只有10个教授，全35个进去后区分度会显著提升。

---

## 2026-05-16 Phase 1 完成 + Phase 2a 完成

**Phase 1 收尾：**
- [x] 全 35 个教授爬取完成（deep_scraped_professors.json）
- [x] vector_db 重建（500 chunks，35 个教授）
- [x] 全量测试通过（HRI / manipulation / 本科招生 / 自主系统 4 类查询）
- [x] crawl4ai-migration merge 到 main，推送 GitHub

**Phase 2a 完成（branch: phase2-agent）：**
- [x] `search_by_direction` 工具：向量检索，filter page_type in [research, home]，k=6，按教授名去重
- [x] `get_professor_details` 工具：直接从 JSON 取，返回所有 scraped_pages，每页 cap 3000 chars
- [x] `create_react_agent`（LangGraph）替换旧 Pydantic chain，原生 Gemini function calling
- [x] `trace_recommendations()` 调试函数，打印完整 Agent 推理链
- [x] 3 类查询全量测试通过，每次 ~10-20s

**Agent 决策行为分析（今日发现）：**

Agent 存在 "snowball search" 行为——读完教授详情页后，从内容里发现新教授名字（如合作者、co-advisor），追加第二次 search。

具体案例（HRI 查询）：
- 第一次 search → Kathuria、Mavrogiannis、Ghaffari
- 读 Kathuria/Ghaffari 详情时发现 "X. Jessie Yang"（两处 co-advisor 提及）
- 追加 search → 找到 Xi Jessie Yang、Lionel Robert
- 最终推荐：Xi Jessie Yang、Mavrogiannis、Lionel Robert

决策质量评估：
- 换入 Xi Jessie Yang：合理（ICRL = HRI 核心 lab，两处独立线索）
- 换入 Lionel Robert：有问题（信息系统视角的 HRI，非技术方向；其 research 页面内容几乎为空）
- 违反 system prompt "search ONCE" 约束：LLM 权衡"遵守规则 vs 更好答案"，选了后者

---

## 2026-05-17 断连根因分析 + 模型切换

**问题**：agent run 在 5-6 次工具调用后 `RemoteProtocolError: Server disconnected`

**根因**：`gemini-flash-latest` 实际指向 `gemini-3-flash-preview`（通过 response_metadata 确认）
- Preview 模型本身不稳定
- 同时是 thinking 模型（reasoning_tokens=40 for a simple query），多步 agent run 时每步都走内部推理，响应时间拉长，server 偶尔断连
- `gemini-2.0-flash` 已 404 下线；`gemini-2.5-flash-lite` 可用但太弱（无法完成 workflow）

**修复**：切换至 `gemini-2.5-flash`（稳定版，reasoning_tokens=16，两个 query 测试无断连）

**本次测试结果（gemini-2.5-flash）**

| Query | 消息数 | search次数 | 推荐结果 |
|-------|--------|-----------|---------|
| CV + manipulation | 8 | 1 | Fazeli、Berenson（只有2个，第三个 search 没召回到） |
| HRI + freshman | 10 | 1 | Mavrogiannis、Kathuria、Patricia ✅ |

**遗留问题**：
1. `get_professor_details` 每页 1000 char cap → join/people 内容被截，LLM 看不到招募信息，undergrad Y/N 全显示 N
2. CV query search k=6 中 manipulation 教授只有 Fazeli/Berenson 进 top，无法推荐第三个

---

---

## 2026-05-18 实验系统 + LangSmith + Thinking 调研

### 实验脚本

新增两个实验脚本：

- `experiment_compare.py`：两个模型（gemini-flash-latest vs gemini-2.5-flash）跑同一 prompt 对比
- `experiment_stress.py`：对 gemini-flash-latest 跑 P1-P5 五个 prompt，记录工具调用序列、EVAL 行、耗时、错误

### 代码修改

- `get_professor_details`：去掉全部 char cap，返回 JSON 全量内容（原 `[:1000]` → 无截断）
- `load_environment()`：重写，加入 LangSmith 三个环境变量的加载
- `.streamlit/secrets.toml`：加入 LangSmith API key / project name

### LangSmith 接入

- 每次 `agent.invoke()` 自动上传 trace
- `read_traces.py`：命令行读 trace，`python read_traces.py` 列最近10条，`python read_traces.py <id>` 看完整树

### 实验结论（两轮 stress test）

**Run 1（get_professor_details 有 [:3000] cap）**

| ID | 结果 | 关键发现 |
|----|------|---------|
| P1 HRI | ✅ | undergrad 显示 Y/N（内容被截，无法判断）|
| P2 CV | ✅ | 连搜3次（截断导致信息不足，回头补搜）|
| P3 自动驾驶 | ❌ GraphRecursionError | 根因未知（中间步骤丢失）|
| P4 ML+本科 | ❌ GraphRecursionError | 同上 |
| P5 HRI repeat | ✅ | 一致性 PARTIAL（第三个位置有随机性）|

**Run 2（去掉 cap，全量内容）**

| ID | 结果 | 关键发现 |
|----|------|---------|
| P1 HRI | ✅ | undergrad 全变 Y + 具体引用证据 ✅ |
| P2 CV | ❌ GraphRecursionError | 正常流程步数超 recursion_limit=15 |
| P3 自动驾驶 | ✅ | 修好，但无 EVAL 行 |
| P4 ML+本科 | ✅ | 修好 |
| P5 HRI repeat | ✅ | 稳定 |

**核心发现**：Run 1 的多次 search 是截断的副作用（内容不足 → 回头补搜），去掉截断后多次 search 消失。`recursion_limit=15` 对正常 6步 query 太紧。

### Run 3：开启 thinking_budget=2048（gemini-flash-latest）

| ID | 耗时 | 错误 | EVAL | 关键发现 |
|----|------|------|------|---------|
| P1 HRI | 9.0s | 无 | 3 ✅ | - |
| P2 CV | 12.0s | 无 | 3 ✅ | 仍然 2次 search（召回质量驱动，非截断副作用）|
| P3 自动驾驶 | **235.2s** | 无 | 3 ✅ | 不再崩，说明之前是被 limit 砍断，不是死循环 |
| P4 ML+本科 | 73.1s | 无 | 0⚠️ | EVAL 行被加了 markdown bold，解析失败 |
| P5 HRI repeat | 9.1s | 无 | 3 ✅ | 一致性首次 100%（完全相同三个教授）|

**Thinking 相关调研结论**：
- LangSmith 不暴露 Gemini thinking 文字，只存 token 数和加密签名（`__gemini_function_call_thought_signatures__`）
- 所有观测平台（Langfuse 等）都同样无法通过 LangChain 拿到 thinking 文字
- 要读 thinking 文字必须绕开 LangChain 用原生 Google SDK，只适合一次性诊断

---

## TODO

- [x] 实现 search_by_direction 工具
- [x] 实现 get_professor_details 工具
- [x] create_react_agent 替换 backend.py 的 chain
- [x] Agent trace 调试工具（trace_recommendations）
- [x] EVAL 行加入 system prompt（解决 Lionel Robert 问题 + snowball 停止信号）
- [x] 模型切换至 gemini-2.5-flash（解决断连问题）
- [x] get_professor_details 去掉 char cap（undergrad Y/N 修好）
- [x] LangSmith 接入（read_traces.py）
- [x] thinking_budget 实验（Run 3）

### 🔴 当前最重要的未解决问题：架构决策

**两个核心未知量，必须先解决再决定下一步架构：**

**未知量1：模型什么时候会自由调用工具**
P2 在有 thinking 的情况下仍然 search 了2次。假设是：thinking 让模型更准确判断"召回够不够"，多次 search 由召回质量驱动而非随机行为。但无法通过 LangSmith 验证，因为 thinking 文字不可见。

**未知量2：最适合的架构是什么**
核心问题：给模型自由度（free ReAct，自己决定搜几次）vs 固定架构（限定步骤，代码强制）哪个更好？
- 现有数据倾向于：free ReAct + thinking_budget + recursion_limit 调大 = 所有 query 都能跑完，行为更稳定
- 但没有看到 thinking 文字，无法确认模型的决策逻辑是否合理

**解决路径**：用原生 Google SDK 跑一次 P2（多次 search 的 case），读 thinking 文字，确认假设，然后做架构决定。

- [ ] 原生 SDK 诊断：读 P2 / P3 的 thinking 文字，验证多次 search 的根因
- [ ] 根据诊断结果决定：free ReAct + 调大 limit，还是自定义 LangGraph 节点
- [ ] recursion_limit 从 15 改到合适值（待架构决定后执行）
- [ ] Phase 2b：多轮追问

---

## 2026-05-21 RAG Debug + 架构反思

### 代码改动

**1. search 工具层加状态（硬限制 snowball）**
- 把 `search_by_direction` 改成工厂函数 `_make_search_tool()`，用闭包的 `called` 变量
- 第二次调用直接返回 "Search already performed"，代码层面强制，不依赖 prompt
- `get_recommendations` / `trace_recommendations` 每次调用前 `build_agent()`，保证每次 query 都有新的 `called=False` 状态
- 和 system prompt 的 "search ONCE" 的本质区别：prompt 是"告诉模型不要做"，工具层是"物理上做不到"

**2. k 从 6 → 50**
- 原来 k=6，Fazeli/Berenson 各有多个高分 chunk 把 top 6 全占满，其他教授根本进不来
- 改成 k=50 先取足够多 chunk，再按教授名去重，保证6个 slot 来自不同教授
- recursion_limit 同步从 15 → 25

---

### RAG 数据流 Debug 结论

**根因：chunk 粒度召回没有保证 document 粒度多样性**

对 query "CV + manipulation"，k=50 去重后的教授出现顺序：

| 首次出现位置 | 教授 | 相关性 |
|------------|------|--------|
| chunk #1 | Fazeli | 强相关 ✅ |
| chunk #3 | Berenson | 强相关 ✅ |
| chunk #15 | Ghaffari | 弱相关（perception/navigation）|
| chunk #21 | Mavrogiannis | 不相关（HRI）|
| chunk #35 | Jenkins | 相关（Perceptive Robotics）但被排到 #35 |
| k=60 里不出现 | Corso | 网站内容太少，chunk 质量差，embedding 无效 |

**手工 ground truth 对比**：做 CV/manipulation 的教授应该有 Fazeli、Berenson、Jenkins、Corso、Draelos（5个），RAG 实际召回进 top 6 的只有 Fazeli、Berenson、Ghaffari（3个，且 Ghaffari 方向偏）。Jenkins 在 #35，Corso 完全召不回。

**两个根因**：
1. Fazeli/Berenson 网站内容丰富、关键词密集，chunk 数量多且相似度高，把其他教授挤出去
2. Corso 网站在迁移（"site is a bit dated"），抓到的内容极少，embedding 质量差

---

### 架构层面反思

**核心问题**：现在是 ReAct-style Agentic RAG，但 RAG 不只是在"缩小范围"，而是在**控制信息边界**——agent 只能看到 RAG 给的教授，无法发现 RAG 遗漏的人。

**业界三种 Agentic RAG 模式**：
- **ReAct-style RAG**（当前）：agent 决定何时调 RAG，但调完直接用，没有质量评估
- **Self-RAG**：agent 主动判断召回是否足够，不够就重新召回
- **Corrective RAG（CRAG）**：加 Grader 节点评估召回质量，不合格触发纠正（换 query 或补搜）

当前缺的是 Grader——agent 无法判断"召回的6个教授够不够、漏没漏人"，Jenkins 被漏掉了也不知道。

---

### 评估方法调研结论

| 方法 | 评什么 | 适用场景 |
|------|--------|---------|
| 手工 ground truth + Recall@k | 教授层面的召回质量 | 召回 debug（当前最需要）|
| RAGAS（Context Precision/Recall）| chunk 层面的召回质量 | 精细调优 |
| LLM-as-Judge | 推荐理由质量（faithfulness、relevance）| 端到端输出质量 |
| Trajectory Eval（LangSmith）| 工具调用序列是否合理 | agent 行为审计 |

**MMR（Maximal Marginal Relevance）**：LangChain 内置，Chroma 支持，专门解决多样性问题，是手动去重的标准替代。待验证是否比 k=50 手动去重效果更好。

---

### 🔴 当前待决定的架构问题

1. **RAG 召回质量**：k=50 + 去重解决了部分多样性问题，但 Jenkins 仍然要排到 #35，Corso 完全失效。是继续优化 RAG（MMR、Hybrid Search），还是接受这个上限？
2. **Agentic RAG 升级**：要不要加 Grader 节点（走向 CRAG），让 agent 能评估召回是否足够？
3. **全量候选工具**：给 agent 加一个"列出所有教授+一句话摘要"工具，让 agent 自己决定要深查谁，RAG 变成可选加速手段而非信息边界
4. **eval 框架**：先建手工 ground truth（5-6个 query 标注），再系统跑 Recall@k 对比策略

---

## 2026-05-22 Ground Truth 建立 + MMR 评测

### Ground Truth（手工标注，按相关度排序）

**P1：HRI + human-robot collaboration**
1. Patricia Alves Oliveira（HRI核心，robotics+design+psychology）
2. Xi Jessie Yang（ICRL，HRI+human-autonomy teaming）
3. Christoforos Mavrogiannis（社交导航+人群中的机器人）
4. Tribhi Kathuria（HRI+LLM-guided learning）
5. Lionel Robert（HRI但偏社会/组织层面）

**P2：CV + manipulation**
1. Nima Fazeli（manipulation核心，vision+tactile全覆盖）
2. Dmitry Berenson（manipulation核心，motion planning+ML）
3. Chad Jenkins（Perceptive Robotics，robot perception+CV）
4. Bernadette Bucher（Generative AI for robotic inference，3D prediction）
5. Maani Ghaffari（perception+mapping，有CV成分但主要field robotics）
6. Mark Draelos（image-guided robotics，CV强但医学方向）

**P3：自动驾驶 + motion planning**
1. Ram Vasudevan（ROAHM Lab，safety-aware motion planning，自动驾驶核心）
2. Dimitra Panagou（DASC Lab，autonomous systems+multi-agent planning+safety）
3. Necmiye Ozay（dynamical systems+control，autonomous systems理论）
4. Maani Ghaffari（field robotics，autonomous navigation，mapping）
5. Xiaoxiao Du（pedestrian prediction，自动驾驶感知）
6. Katie Skinner（field robotics+perception，偏underwater）

**P5：soft robotics**
1. Xiaonan Sean Huang（Hybrid Dynamic Robotics Lab，soft.robotics.umich.edu，核心 soft robotics）
2. Cameron Aubin（Zoetic Robotics Lab，"Soft and Biologically-inspired Robots"，soft materials + compliant devices）
- 注：35人里仅有这2位做 soft robotics，Fazeli 做 tactile/manipulation 属边缘相关

**P6：multi-robot SLAM**
1. Yulun Tian（SSI Lab，distributed robot teams + SLAM，完全命中）
2. Maani Ghaffari（CURLY，field robotics + SLAM + mobile robotics，词汇 gap 导致召回困难）
- 注：35人里仅有这2位做 multi-robot SLAM 交叉方向；Gaskell 无 lab 网站，Ceron 做 swarm 非 SLAM，Panagou/Bucher 各命中一半但不是完整 GT

---

### MMR 评测结果（lambda_mult=0.5, k=12, fetch_k=80）

| Query | Retrieved Top 6 | GT Top3 命中 | Recall | Precision |
|-------|----------------|-------------|--------|-----------|
| P1 HRI | Mavrogiannis, Kathuria, Patricia, Yang, Robert, **Kira Barton** | 3/3 ✅ | 5/5 = 1.00 | 5/6 = 0.83 |
| P2 CV | Fazeli, Berenson, **Mavrogiannis**, **Skinner**, Bucher, Jenkins | 3/3 ✅ | 4/6 = 0.67 | 4/6 = 0.67 |
| P3 AUTO | **Kathuria**, **Ding**, **Berenson**, **Grizzle**, **Fazeli**, **Mavrogiannis** | 0/3 ❌ | 0/6 = 0.00 | 0/6 = 0.00 |

（**加粗**为 false positive）

### 问题分析

- **P1**：表现好，只多了 Kira Barton 一个 false positive
- **P2**：top3 全中，但 Ghaffari/Draelos 没进来，Mavrogiannis/Skinner 混入
- **P3**：完全失败，Vasudevan/Panagou/Ozay/Ghaffari 全部漏召，召回的6个全是 false positive

**P3 根因**：语义 gap——"autonomous driving motion planning" 这些词在这些教授的网站上描述方式不同（用 "safety-aware control", "autonomous systems", "provable guarantees" 等），embedding 对不上 query 的关键词，不是多样性问题。

---

## 2026-05-22 CRAG + Multi-Query 实验

### 今日做了什么

**1. 搜索工具改为 Multi-Query + MMR + RRF**

代码结构：
- `_mmr_search(query)`：单次 MMR 检索，返回 top k 教授
- `_generate_queries(query, llm)`：LLM 生成3个变体 query
- `_multi_query_search(query, llm)`：对原始+3个变体共4个 query 各跑 MMR，RRF 融合排序，返回 top 6
- `_grade_and_correct()`：CRAG grader，实验后发现不可靠，已从调用链移除（代码保留）
- search tool 硬限制 search 一次（`called=False` 闭包）

**2. CRAG grader 实验结论**

尝试在 MMR 之后加 LLM grader 评估召回质量，不够就 reformulate query 重搜。
- 失败原因：grader 和 retrieval 用同一个模型，对词汇的理解偏差一致——Mavrogiannis 因为 "road traffic" 被召回，grader 也因为 "road traffic" 认为他 relevant，纠错失效
- 调 prompt 无底洞，每次改都有新的误判
- 结论：CRAG 在同一模型做 retrieval + grading 时，无法纠正自身的语义偏差

**3. Multi-Query 评测结果**

| Query | Multi-Query Top 6 | GT Top3 命中 | vs 纯 MMR |
|-------|------------------|-------------|-----------|
| P1 HRI | Mavrogiannis, Kathuria, Yang, Patricia, Robert, Barton | 3/3 ✅ | 持平 |
| P2 CV | Fazeli, Ghaffari, Berenson, Mavrogiannis, Aubin, Bucher | 2/3 ✅ | Jenkins 没进来 |
| P3 AUTO | Mavrogiannis, Kathuria, **Panagou** ✅, Ghaffari, Du, Skinner | 1/3 | 从 0/3 提升 |

Multi-Query 对 P3 有改善（Panagou 出现），但不稳定——变体 query 随机生成，Panagou 进不进来是随机的。

**4. Agent 过滤层验证**

完整 agent trace 显示：agent **不会**主动过滤 false positive，会从全量内容里找理由 justify 召回的人（Mavrogiannis 的 road traffic 论文、Kathuria 的 Honda 实习）。Agent 是决策层，不是纠错层。

**5. Ozay / Vasudevan 根因确认**

| 教授 | 数据 | 根因 |
|------|------|------|
| Necmiye Ozay | research 页 10000 chars，内容充足 | 词汇 gap：用 "formal methods / dynamical systems"，和 "autonomous driving" embedding 距离远 |
| Ram Vasudevan | research 页仅 1708 chars，内容几乎是导航栏 | 数据质量：Squarespace JS 渲染，爬虫没抓到实质内容 |

---

### 当前架构（三层）

```
学生输入
    ↓
【第一层：Multi-Query + MMR 召回】
  LLM 生成3个变体 query → 各跑 MMR（fetch_k=80, k=10）→ RRF 融合 → top 6 snippet
    ↓
【第二层：Agent 决策】
  create_react_agent：读 snippet → 选3个调 get_professor_details → EVAL 打分 → 推荐3个
    ↓
【第三层：输出】
```

**约束**：search 硬限一次（闭包），agent 最多查3个详情，recursion_limit=25

---

### 🔴 未解决的核心问题

1. **Vasudevan**：数据质量差，重新爬可能有用，Squarespace 渲染问题
2. **Ozay**：词汇 gap，Multi-Query 生成的变体没有覆盖她的词汇，换 embedding 模型或 Hybrid Search 才能根本解决
3. **Multi-Query 不稳定**：变体 query 每次不同（temperature=0.3），Panagou 进不进来是随机的
4. **Agent justify 问题**：召回全错时 agent 会合理化错误结果，没有"这些都不对"的判断机制
5. **Mavrogiannis/Kathuria false positive**：每个 query 几乎都会出现，因为他们的词汇和很多方向都有重叠

---

## 2026-05-26 对 P3 "失败" 的重新理解 + 项目上限分析

### 核心洞察：P3 的召回结果大多数是 defensible 的

之前把 P3（autonomous driving + motion planning）的结果评为 "0/3 GT 命中" 并认定为召回失败，这个判断过于严格。重新审视：

| P3 召回的教授 | 实际可解释性 |
|-------------|------------|
| Ghaffari | field robotics + perception + mapping → 自动驾驶**感知层**，直接相关 ✅ |
| Du | pedestrian prediction → 自动驾驶感知/预测层，相关 ✅ |
| Skinner | field robotics + underwater perception → 边缘相关 ⚠️ |
| Mavrogiannis | 社交导航，人群中的机器人运动 → motion planning 子方向，可解释 ⚠️ |
| Kathuria | HRI + Honda 实习 → 牵强 ❌ |

**前两个是完全 defensible 的**，召回了"autonomous driving"的感知层研究者，只是没有命中控制理论/safety 层的研究者（Vasudevan/Ozay/Panagou）。

### 问题的重新定义

**错误框架**：RAG 对 P3 召回失败，漏掉了核心教授。

**准确框架**：`"autonomous driving + motion planning"` 是一个覆盖感知/规划/控制/ML 四个子方向的宽泛 query。RAG 召回了**感知/导航子方向**的教授，没有召回**控制理论/safety 子方向**的教授（Vasudevan/Ozay）。这是因为：

1. 手工 ground truth 预设了"控制理论"这一种解读，而 RAG 命中了另一种同样合法的解读
2. 对宽泛 query 来说，不存在唯一正确的召回结果

**本质**：这是**query 粒度问题**，不是 RAG 的根本性失败。如果用户把 query 收窄为 `"safety-aware motion planning for autonomous vehicles"`，Vasudevan/Ozay/Panagou 会自然提高召回率。

### 这个框架下真正不可解决的问题

在当前架构（semantic embedding + Multi-Query + MMR + RRF）下，以下问题是**结构性上限**，无法通过调参解决：

**1. 宽泛 query 的多义性**

embedding 模型把 query 压缩到一个向量，这个向量无法同时指向"感知方向"和"控制理论方向"两个语义聚类。宽泛 query 天然会命中 embedding 空间里距离最近的子聚类，而不是均匀覆盖所有子方向。

→ **解法只有一个：要求用户提供更具体的 query**（系统设计层面，不是 RAG 层面）

**2. 领域词汇 gap（Ozay 问题）**

Ozay 的研究和"autonomous driving"高度相关，但两者使用完全不同的词汇体系（"formal methods" vs "autonomous driving"），embedding 距离远。Multi-Query 理论上能绕过去，但 LLM 生成的变体 query 不能保证覆盖"formal methods"这个词——因为 LLM 本身也倾向于生成与 input 语义相近的变体。

→ **要根本解决需要 knowledge graph 或人工构建的领域同义词表**，超出当前项目范围

**3. CRAG 对同源偏差免疫**

实验已证明：用同一个模型做 retrieval 和 grading，对词汇的理解偏差是一致的，grader 无法纠正 retriever 的错误。Mavrogiannis 因为"road traffic"被召回，grader 也会认为他 relevant。

→ **这是信息论层面的限制**：用同一信息源纠错，等于让一个人既当裁判又当运动员

### 项目上限的清醒认知

当前三层架构（Multi-Query + MMR + RRF → ReAct Agent → 输出）在以下范围内工作良好：
- **具体方向的精确 query**（HRI、CV+manipulation）→ P1/P2 表现稳定
- **教授个人层面的深度查询**（get_professor_details）→ 全量内容，质量高

在以下范围内存在固有上限：
- **过于宽泛的 query** → 召回结果覆盖一个子方向，无法保证全面性
- **词汇体系差异极大的学科边界**（控制理论 ↔ 机器学习）→ embedding 天然处理不好
- **数据质量差的教授**（Vasudevan）→ 数据问题可修，但有其他教授也可能有类似问题

**结论**：这个项目的 RAG 质量在 portfolio 层面已经足够，当前的"失败案例"本质上反映的是 semantic search 的普遍上限，而非实现层面的缺陷。继续优化 RAG 的 ROI 很低。下一步重心应转向 Phase 2b（多轮追问），增加系统的功能深度。

---

## 2026-05-27 数据层系统性排查 + 修复 + 全量测试

### 今日工作内容

#### 1. 全量数据质量审计

对 35 位教授的 `deep_scraped_professors.json` 做系统性扫描，按严重程度分级：
- 检查维度：总字符数、是否有 research/home 页、是否仅 fallback profile、是否有 join/people 页
- 审计前：🔴 严重 8 位，🟡 轻微 11 位，✅ 正常 16 位

#### 2. 爬虫问题根因分类

排查出4类系统性问题：

| 问题 | 根因 | 受影响 |
|------|------|--------|
| `blocked_403` 直接跳过 Crawl4AI | `scrape_one()` 代码逻辑硬编码 | Gillespie、Rouse 等 |
| 路径深度过滤误杀 `/index.php/` URL | `filter_links()` `max_depth = +1` 太严 | 所有 WordPress `/index.php/` 站点（Yang）|
| lab_url 在 index 缺失 | survey 阶段遗漏 | Yulun Tian |
| `result.success=False` 无内容兜底 | 共享 crawler 偶发误报 / 302 redirect | Gillespie（偶发）、Rouse（域名迁移）|

#### 3. deep_scraper.py 代码修改（3处）

**Fix 1**：`filter_links()` 路径深度放宽
```python
# 修改前
max_depth = path_depth(homepage_url) + 1
# 修改后
max_depth = path_depth(homepage_url) + 2  # 兼容 /index.php/xxx/ 类 WordPress 路径
```

**Fix 2**：`scrape_one()` 移除 `blocked_403` 早退
```python
# 修改前
if status in ("blocked_403", "no_lab_url") or not prof.get("lab_url"):
# 修改后
if status == "no_lab_url" or not prof.get("lab_url"):
```

**Fix 3**：`scrape_lab_site()` 内容兜底判断（不完全依赖 result.success）
```python
raw_content = clean_markdown(get_markdown(result))
if not result.success and len(raw_content) < MIN_CONTENT_CHARS:
    return [], "fetch_failed"
# 有内容就继续，即使 success=False（302 redirect / 共享 crawler 偶发）
```

#### 4. professors_index.json 数据修复

- **Yulun Tian**：补充 `lab_url = https://ssi.robotics.umich.edu`，status 改为 `ok`
- **Elliott Rouse**：旧域名 `neurobionics.engin.umich.edu` → 新域名 `neurobionics.robotics.umich.edu`（域名迁移）
- **Xiaonan Sean Huang**：status 从 `blocked_403` 改为 `ok`（数据层补丁，代码修复后不再需要）

#### 5. 重爬 + 数据效果

| 教授 | 修复前 | 修复后 | 根因 |
|------|-------|-------|------|
| Xi Jessie Yang | 994 chars（home only） | 5736 chars（home+people+research）| WordPress `/index.php/` 路径深度问题 |
| Yulun Tian | 2565 chars（fallback profile）| 9441 chars（4页真实内容）| lab_url 缺失 |
| Leia Stirling | 5370 chars（fallback profile）| 21863 chars（3页真实内容）| blocked_403 早退 |
| Brent Gillespie | 1915 chars（fallback profile）| 13374 chars（home+people+research）| 共享 crawler 偶发 success=False |
| Elliott Rouse | 5854 chars（fallback profile）| 22879 chars（5页真实内容）| 域名迁移 + success=False 兜底 |
| Xiaonan Sean Huang | 3163 chars（fallback profile）| 14712 chars（4页真实内容）| blocked_403 早退 |

审计后：🔴 严重 3 位（Yeo/Formosa/Gaskell，无 lab 网站，真实上限），🟡 轻微 11 位，✅ 正常 21 位。

#### 6. 重新 ingest

500 chunks → **602 chunks**，vector_db 全量更新。

---

### 全量测试结果（2026-05-27）

| # | Query | GT（35人中相关者）| 系统推荐 | GT命中 | 根因 |
|---|-------|-----------------|---------|--------|------|
| P1 | HRI + collaboration | Patricia, Yang, Mavrogiannis, Kathuria, Robert | Patricia ✅, Yang ✅, Mavrogiannis ✅ | **3/3** | 完美 |
| P2 | CV + manipulation | Fazeli, Berenson, Jenkins, Bucher, Ghaffari, Draelos | Fazeli ✅, Berenson ✅, Mavrogiannis ❌ | **2/3** | Jenkins 漏召：lab 网站无 research 页，结构性数据缺失 |
| P3 | 自动驾驶 + motion planning | Vasudevan, Panagou, Ozay, Ghaffari, Du, Skinner | Ghaffari ✅, Mavrogiannis ❌, Kathuria ❌ | **1/3** | 词汇 gap（Vasudevan/Ozay/Panagou 用控制理论术语）；Ghaffari 感知子方向命中 |
| P4 | 本科生 + robot learning | Mavrogiannis, Kathuria, ... | Mavrogiannis ✅, Kathuria ✅, +FP | **2/3** | query 宽泛，多余召回 |
| P5 | soft robotics | **Sean Huang, Aubin**（35人中仅此2位）| Sean Huang ✅, Aubin ✅, Fazeli ❌ | **2/2** | GT全命中；Fazeli 是唯一 FP（tactile sensing，非 soft robotics）|
| P6 | multi-robot SLAM | **Tian, Ghaffari**（35人中仅此2位）| Tian ✅, Ceron ❌, Skinner ❌ | **1/2** | Ghaffari 词汇 gap 漏召；Ceron 做 swarm 非 SLAM |

**系统级 FP**：Mavrogiannis 在 P2/P3/P4 共出现3次，词汇覆盖面过广，是召回层结构性问题（词汇表里"social navigation"、"road traffic"与多个方向语义重叠）。已确认为 Accepted 上限，不再深入优化。

**数据修复验证**：P5 Sean Huang（blocked_403修复）、P6 Tian（lab_url补充）在修复后首次被召回。

---

### GT 排查与修正（2026-05-27 session）

重新审核所有 query 的 ground truth，修正如下：

- **P5**：Aubin 之前误标为 FP，实为 ✅（"Soft and Biologically-inspired Robots, compliant devices"）→ P5 GT 2/2 全命中
- **P6**：Ceron 之前标 ⚠️ 部分命中，实为 ❌（Ceron 做 swarm microrobotics，不是 SLAM；学生实际需求下是 FP）→ P6 = 1/2

P6 GT 仅有 Tian + Ghaffari（35人中仅2位做 multi-robot SLAM 交叉），Ghaffari 因词汇 gap（"state estimation/mapping"而非"SLAM/multi-robot"）漏召，是结构性限制。

---

### 当前状态（2026-05-27 end of session）

- [x] 数据层系统性排查完成
- [x] 爬虫代码4类问题修复
- [x] 35教授数据重爬 + 全量 ingest（602 chunks）
- [x] 6个 query 全量测试 + GT 全面修正
- [x] 改动1：system prompt 强制 agent 读全部候选（而非只读 top 3）
- [x] Agent 决策行为 vs RAG 层分析：EVAL reject 实际上是死码，agent 基本给 RAG 结果做解释而非做筛选
- [x] 粗筛架构讨论（RAG vs LLM summary，见下方）
- [x] 规模化扩展可行性调研（CSE/ME/Stats/UMSI 四个部门，见下方）
- [x] 项目真实价值定位（不只是简历项目，覆盖面+准确率+部署三件事构成 MVP）

---

## 架构讨论：粗筛阶段 RAG vs LLM Summary

### 背景

当前粗筛层：Multi-Query + MMR + RRF，返回 top 6 snippet 给 agent。

核心问题：RAG 的召回质量依赖 query 和教授文本的词汇对齐，对宽泛或跨领域 query（如 P3 自动驾驶）会漏召词汇体系不同的教授（Vasudevan/Ozay）。

### 两种粗筛方案对比

| 维度 | 当前：RAG（semantic search）| 替代：LLM Summary 全量读取 |
|------|---------------------------|--------------------------|
| **工作方式** | query → embedding → 向量距离最近的 chunks | LLM 读全部35个教授摘要（~10K tokens）直接判断 |
| **词汇 gap** | ❌ 是主要失败根因 | ✅ LLM 理解语义等价，不受词汇限制 |
| **全局视野** | ❌ 只看到 top k 教授 | ✅ 35人全看到，不会漏人 |
| **可规模化** | ✅ 教授数量×n 不影响延迟 | ❌ 教授增加到几百人时 context window 撑不住 |
| **query 独立性** | ✅ 摘要按 query 动态生成 | ❌ 需要预生成每个教授的通用摘要 |
| **适用场景** | 大量教授（100+），query 词汇精确 | 少量教授（35），词汇跨领域宽泛 |

### 当前结论

- 35人规模：LLM summary 方案理论上更优（无词汇 gap，全局视野）
- 但 RAG 已有 portfolio narrative value（展示了 RAG pipeline 完整链路）
- **当前优先级不是替换粗筛层，而是修复 agent 决策层**（粗筛已经够用，决策层几乎不过滤）
- LLM summary 方案作为 Phase 3 可选升级保留，待规模化到 CSE/UMSI 后再评估是否切换

---

## 🔴 当前最重要：Agent 决策层修复

### 问题定位

**改动前**：agent 只读 top 3 snippet 就推荐，RAG 召回谁就推荐谁，agent 不是决策层而是解释层。

**改动1（已做）**：system prompt 要求 agent 读全部6个 snippet 详情，对每个输出 EVAL 行（match 1-10、undergrad Y/N、keep/reject）。

**改动1 的问题**：
- prompt 层面的要求不稳定（P2 只读了2个，P1 EVAL 格式乱）
- EVAL reject 逻辑是死码：agent 找到任何理由都会 keep，基本不 reject
- P3 出现 snowball：agent 读 Kathuria 详情时发现 Ghaffari 提及，主动调用 get_professor_details(Ghaffari)（不在 RAG top 6 中）

### 下一步：改动2（待做）

**目标**：让 reject 逻辑真正生效，agent 能淘汰明显不相关的教授（如 P3 中的 Kathuria）。

**方案选项**：

| 方案 | 实现方式 | 优劣 |
|------|---------|------|
| A：强化 prompt reject 约束 | 加"如果主要方向不匹配必须 reject"指令 | 简单，但 prompt 层不稳定，存在"找理由 keep"风险 |
| B：代码层预加载全部详情 | agent 调用前代码自动 get_professor_details(all 6)，agent 直接拿完整内容做决策 | 稳定，但绕开了 tool calling 的 portfolio 价值 |
| C：两阶段架构 | RAG top 6 snippet → agent EVAL → 代码过滤 reject → 对 keep 的教授调 get_professor_details → 最终推荐 | 最清晰，但增加复杂度 |

**当前倾向**：先试方案 A（prompt 强化），在 system prompt 里加明确的 reject 条件，跑 P2/P3 验证 reject 是否真正生效。如果还是不稳定，走方案 C。

---

## 规模化扩展可行性

### 目标：覆盖更多 UMich 部门，从35人扩到150-200人

#### 各部门评估

| 部门 | 教授数 | 目录层信息 | 爬取难度 | AI相关性 | 优先级 |
|------|--------|-----------|---------|---------|--------|
| **CSE** (cse.engin.umich.edu) | 170 | ✅ Research Interests 内嵌卡片（113/170）| 最低 | ⭐⭐⭐⭐⭐ | 🔴 第一优先 |
| **UMSI** (si.umich.edu) | ~100 | ❌ 目录只有姓名+头衔，需逐页访问 | 中等 | ⭐⭐⭐⭐ HCI/AI/隐私 | 🟡 第二优先 |
| **ME** (me.engin.umich.edu) | ~120 | ✅ Research Interests 内嵌卡片 | 最低 | ⭐⭐⭐ 偏控制/机械 | 🟢 低优先 |
| **Statistics** | ~50 | ❌ 只有标签 | 高 | ⭐⭐ | 不做 |

**UMSI 特殊价值**：个人页有"Potential PhD Faculty Advisor: Yes/No"字段，对找导师的学生非常有用。

#### 结论

- **MVP 版本**（能给真实用户用）：Robotics(35) + CSE(170) → ~200人，部署到 Streamlit Cloud，有可分享 URL
- **扩展时间点**：agent 行为修好之后再做，当前 35人够测试
- **扩展工程量**：CSE 爬虫几乎零改动（目录结构与当前一致），UMSI 需加两步爬取逻辑
