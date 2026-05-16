# M-Serendipity 项目计划
**最后更新：2026-05-16**

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

## TODO

- [x] 实现 search_by_direction 工具
- [x] 实现 get_professor_details 工具
- [x] create_react_agent 替换 backend.py 的 chain
- [x] Agent trace 调试工具（trace_recommendations）
- [ ] 更深入测试 Agent 决策逻辑（snowball search 行为，Lionel Robert 质量问题，prompt 约束有效性）
- [ ] Phase 2b：多轮追问
