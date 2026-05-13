# M-Serendipity 项目计划
**最后更新：2026-05-14**

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
| Agent（Tool calling、ReAct） | ❌ | Phase 2 |
| 多轮对话 + 记忆 | ❌ | Phase 2 |
| 工程基础（数据管道） | ✅ | Phase 1 |
| LangGraph | ❌ | Phase 3（可选） |

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

**目标**：从单步 RAG 升级为有工具调用和记忆的 Agent。

- **2a. Tool Calling**：search_professors / get_professor_by_name / get_recent_publications
- **2b. ReAct Agent**：用 `create_react_agent` 替换现有 `prompt | structured_llm`
- **2c. 多轮记忆**：`st.session_state` + `ConversationBufferMemory`
- **2d. page_type 定向检索（备选）**：对学生 query 做分类（研究方向 / 本科机会 / 如何进入），
  再用 ChromaDB `where={"page_type": ...}` filter 定向召回对应类型的 chunks。
  依赖 query classifier + Agent tool routing 实现。

Publications 策略：不预先 ingest，由 Agent 在学生追问时实时抓取最近5篇。

**简历描述**：Implemented a multi-tool ReAct agent with conversation memory for academic advisor use case

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
Phase 1（爬虫 → ingest）→ Phase 2a（工具）→ Phase 2b（ReAct）→ Phase 2c（记忆）→ Phase 3（可选）
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

## TODO

- [ ] 深度测试：更多 query，边缘 case（跨学科、模糊描述），评分一致性
- [ ] 跑全 35 个教授 + 重建 vector_db
- [ ] Phase 2
