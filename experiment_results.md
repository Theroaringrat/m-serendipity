# Experiment Results — gemini-flash-latest
**日期**：2026-05-18
**模型**：`gemini-flash-latest`（实际指向 `gemini-3-flash-preview`）
**temperature**：0.3
**recursion_limit**：15

---

## P1 — HRI freshman ✅

**Prompt**
```
I'm a freshman interested in HRI and human-robot collaboration. I know Python. Which labs should I contact?
```

**Tool calls（4次）**
| # | 工具 | 查询 |
|---|------|------|
| 1 | search_by_direction | `HRI and human-robot collaboration` |
| 2 | get_professor_details | `Christoforos Mavrogiannis` |
| 3 | get_professor_details | `Tribhi Kathuria` |
| 4 | get_professor_details | `Xi Jessie Yang` |

**EVAL lines**
```
EVAL: Christoforos Mavrogiannis | match 10 | undergrad Y | verdict: keep | reason: Research focuses on multi-agent coordination and human-robot collaboration, and the lab website lists undergraduate students.
EVAL: Tribhi Kathuria | match 9 | undergrad Y | verdict: keep | reason: Research covers social navigation and LLMs for robot supervision, which aligns well with HRI and Python skills.
EVAL: Xi Jessie Yang | match 10 | undergrad Y | verdict: keep | reason: The lab's mission is explicitly human-robot interaction and collaboration, and they provide a contact email for the lab.
```

**最终推荐**：Mavrogiannis、Kathuria、Xi Jessie Yang
**耗时**：22.9s | **断联**：无

---

## P2 — CV & manipulation ✅

**Prompt**
```
I have computer vision and manipulation experience, looking for a robotics lab.
```

**Tool calls（6次）**
| # | 工具 | 查询 |
|---|------|------|
| 1 | search_by_direction | `computer vision and manipulation robotics` |
| 2 | search_by_direction | `computer vision robotics manipulation` |
| 3 | search_by_direction | `computer vision and robotics perception` |
| 4 | get_professor_details | `Nima Fazeli` |
| 5 | get_professor_details | `Dmitry Berenson` |
| 6 | get_professor_details | `Bernadette Bucher` |

**备注**：违反 system prompt 的 `search ONCE` 约束，连续 search 了 3 次，每次换关键词扩大覆盖。Call 3 的关键词已从 "manipulation" 换成 "perception"，主动拓宽搜索范围。最终成功找到第三个教授 Bernadette Bucher（单次搜索时只有 2 个）。

**EVAL lines**
```
EVAL: Nima Fazeli | match 10 | undergrad Y/N | verdict: keep | reason: Focuses on contact-rich manipulation and visual cues for policies, directly matching the student's background.
EVAL: Dmitry Berenson | match 10 | undergrad Y/N | verdict: keep | reason: Leading lab for autonomous manipulation with significant focus on motion planning and vision-integrated control.
EVAL: Bernadette Bucher | match 9 | undergrad Y/N | verdict: keep | reason: Her lab (Mapping and Motion) explicitly combines computer vision and manipulation with a clear application form for UM students.
```

**最终推荐**：Fazeli、Berenson、Bernadette Bucher
**耗时**：17.8s | **断联**：无

---

## P3 — Autonomous vehicles ❌

**Prompt**
```
I'm interested in autonomous driving and motion planning. What labs work on this?
```

**Tool calls**：捕获到 0（错误在 invoke 内部抛出，中间步骤全部丢失）

**错误**
```
GraphRecursionError: Recursion limit of 15 reached without hitting a stop condition.
```

**备注**：中间行为未知，无法确认是搜索死循环还是其他原因。需要用 streaming 或提高 recursion_limit 重跑以确认根因。
**耗时**：17.9s | **断联**：否（逻辑超限，非网络问题）

---

## P4 — ML + undergrad ❌

**Prompt**
```
I want a lab that does machine learning applied to robotics and actively recruits undergraduates.
```

**Tool calls**：捕获到 0（同上，中间步骤丢失）

**错误**
```
GraphRecursionError: Recursion limit of 15 reached without hitting a stop condition.
```

**备注**：同 P3，根因未确认。"ML for robotics" 是宽泛词，vector DB 覆盖可能弱，但这只是推测。
**耗时**：10.5s | **断联**：否

---

## P5 — HRI freshman (repeat) ✅

**Prompt**
```
I'm a freshman interested in HRI and human-robot collaboration. I know Python. Which labs should I contact?
```
（与 P1 完全相同）

**Tool calls（5次）**
| # | 工具 | 查询 |
|---|------|------|
| 1 | search_by_direction | `HRI human-robot collaboration` |
| 2 | get_professor_details | `Christoforos Mavrogiannis` |
| 3 | get_professor_details | `Patricia Alves Oliveira` |
| 4 | get_professor_details | `Xi Jessie Yang` |
| 5 | get_professor_details | `Tribhi Kathuria` |

**备注**：违反 system prompt 的 `get_professor_details for at most 3` 约束，调了 4 次。Kathuria 是第 4 次，调完后无 EVAL 行输出，也未进最终推荐——模型看完内容后静默排除，没有走 EVAL 流程。

**EVAL lines**
```
EVAL: Christoforos Mavrogiannis | match 10 | undergrad Y/N | verdict: keep | reason: Specializes in human-robot collaborative transport and implicit communication.
EVAL: Patricia Alves Oliveira | match 9 | undergrad Y/N | verdict: keep | reason: Focuses on the intersection of robotics, design, and psychology for HRI.
EVAL: Xi Jessie Yang | match 10 | undergrad Y/N | verdict: keep | reason: Direct focus on human-robot collaboration and interaction design.
(Tribhi Kathuria → 无 EVAL，静默排除)
```

**最终推荐**：Mavrogiannis、Patricia Alves Oliveira、Xi Jessie Yang
**耗时**：25.1s | **断联**：无

---

## 一致性对比（P1 vs P5，同一 prompt）

| 教授 | P1 | P5 |
|------|----|----|
| Christoforos Mavrogiannis | ✅ keep | ✅ keep |
| Xi Jessie Yang | ✅ keep | ✅ keep |
| Tribhi Kathuria | ✅ keep | 调了但静默排除 |
| Patricia Alves Oliveira | 未调 | ✅ keep |

**结论**：核心推荐（Mavrogiannis、Yang）稳定，第三个位置有随机性（temperature=0.3 的预期行为）。

---

## 已知的 system prompt 违规模式

| 规则 | 违规 case | 行为 |
|------|-----------|------|
| `search ONCE` | P2 | 搜了 3 次，每次换关键词 |
| `get_professor_details for at most 3` | P5 | 调了 4 次，第 4 次无 EVAL |
| `EVAL after EACH get_professor_details` | P5 | Kathuria 被静默排除，无 EVAL |

---

## 待确认问题

- [ ] P3/P4 GraphRecursionError 的具体原因：需要 streaming 重跑，看 15 步里实际发生了什么
- [x] undergrad Y/N 显示 "Y/N"：get_professor_details 的 char cap 导致 join/people 被截 → **Run 2 已修复**

---

---

# Run 2：去掉 get_professor_details char cap
**日期**：2026-05-18（同日）
**变更**：`content[:3000]` → 无截断（返回 JSON 全量内容）
**其余不变**：同模型、同 prompts、同 recursion_limit=15

## 对比汇总

| ID | Run 1（[:3000]） | Run 2（无截断） | 差异 |
|----|----------------|----------------|------|
| P1 | 4 calls, 22.9s ✅ | 5 calls, 28.7s ✅ | 多1次 details，undergrad 从 Y/N → **Y + 具体证据** |
| P2 | 6 calls, 17.8s ✅ | **GraphRecursionError** ❌ | 之前靠多次 search 补救，现在内容大撞上限 |
| P3 | GraphRecursionError ❌ | 5 calls, 21.0s ✅ | 修好，但无 EVAL 行 |
| P4 | GraphRecursionError ❌ | 4 calls, 10.0s ✅ | 修好，3 EVALs |
| P5 | 5 calls, 25.1s ✅ | 5 calls, 20.7s ✅ | 稳定，无变化 |

## 关键发现

**1. undergrad Y/N 修好了**
Run 1 里模型看不到 join/people 页完整内容，只能输出 "Y/N"（不确定）。Run 2 能引用具体证据，如 `"Tisha Jain listed on people page"`、`"lists several undergraduate researchers"`。

**2. 多次 search 行为消失了**
Run 1 的 P2 连搜3次是因为截断导致信息不足，模型回头补搜。Run 2 全量内容后，成功的 run 里最多2次 search（P3），其余全是1次。说明之前的多次 search 是截断的副作用，不是模型主动策略。

**3. P2 出现新的 recursion error**
Run 1 P2：3次 search + 3次 details = 6次工具调用，成功。
Run 2 P2：每次 details 内容大幅增加，模型处理步骤增多，在 recursion_limit=15 内没走完。
根因：`recursion_limit=15` 对 6次工具调用的 query 太紧。

## 待确认问题

- [ ] P2 GraphRecursionError：`recursion_limit` 从 15 改到 25 应能修复，待验证
- [ ] P3 成功但无 EVAL 行：模型跳过了 EVAL 步骤，原因未查
