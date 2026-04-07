# Spirit Analysis: Multi-Agent Shogun Behavioral Patterns

> **Source**: 21,137 AI messages across 432 sessions (2026-01-28 to 2026-02-13)
> **Agents analyzed**: Shogun, Karo (Roju/Midaidokoro), Ashigaru (1-5), Heyago (1-3), Ohariko

---

## 1. Role-by-Role Behavioral Profile

### 1.1 Shogun (将軍) — The Strategist

**Signature phrases**: "承知つかまつった", "殿のご指示をお待ち申す", "家老に指示を出す"

**Observed strengths**:
- **Rapid situation synthesis**: Upon session start or returning from compaction, the Shogun consistently reads dashboard.md, checks the DB, and produces a structured battle report (戦況報告) with tables. This pattern appears in nearly every session.
- **Disciplined delegation**: The Shogun almost never executes tasks directly. In 16 days of data, delegation to Karo happens within 1-3 messages of receiving instructions from the Lord (殿). The "immediate delegation, immediate exit" principle is well-followed.
- **Proactive status reporting**: Frequently generates unprompted status tables showing cmd status, blocked items, and pending decisions. Uses emoji-free markdown tables consistently.
- **Multi-front coordination**: Successfully manages 3+ concurrent cmd streams across projects (arsprout, rotation-planner, shogun system) simultaneously.
- **Graceful error acknowledgment**: When caught making the "11 agents" mistake (forgetting to count himself), immediately took responsibility: "将軍の面目丸潰れよ" and correctly attributed fault rather than blaming subordinates.

**Observed weaknesses**:
- **Self-counting blindness**: Forgot to count himself when enumerating agents (11 instead of 12). This is a meta-cognition failure -- the AI consistently models the system as something it observes rather than participates in.
- **Occasional direct intervention**: In at least one case (subtask_384), the Shogun appears to have bypassed Karo and issued instructions directly to an Ashigaru, violating F002. The Karo had to do post-hoc DB registration.
- **Over-reporting to the Lord**: Tendency to produce very long status reports (10+ items in tables) when the Lord likely only needs 2-3 key points. The reports are thorough but sometimes verbose.
- **Slow to recognize duplicate work**: cmd_153-157 were all duplicates of already-executed commands under different numbers. The Shogun did not catch this until the Karo pointed it out, revealing weak cmd tracking.
- **Premature technical deep-dives**: Sometimes dives into technical details (I2C pin mappings, WireGuard configs, MicroPython WDT timing) that should be delegated to Karo. The line between "strategic understanding" and "doing the work" blurs when the Lord asks technical questions directly.

**Decision-making patterns**:
- When presented with numbered options, tends to pick the pragmatic middle ground (e.g., "Partial" adoption of upstream inbox method).
- Defaults to asking the Lord for ambiguous decisions rather than making assumptions.
- Strong preference for "both simultaneously" when tasks are parallelizable.
- Consistently frames decisions as Lord-facing questions with clear options (numbered 1/2/3 format).

---

### 1.2 Karo-Roju (老中) — The Orchestrator

**Signature phrases**: "承知つかまつった", "五つの問い", "Wave構成", "RACE-001"

**Observed strengths**:
- **Systematic task decomposition**: Uses the "五つの問い" (Five Questions) framework consistently: (1) Purpose analysis, (2) Task decomposition, (3) Headcount decision, (4) Quality perspective design, (5) Risk analysis. This appears ~50 times in the data.
- **Wave-based execution**: Large tasks are broken into sequential Waves to prevent file conflicts (RACE-001). The Karo correctly identifies same-file editing risks and serializes work accordingly.
- **Accurate worker state tracking**: Maintains awareness of which Ashigaru are idle, busy, or at context limit (e.g., "足軽1号はauto-compacting中(7%)").
- **Proactive conflict prevention**: When multiple workers need the same file, the Karo routes work to avoid simultaneous edits. Example: cmd_101/102 README split between Midaidokoro (internal) and Roju (external).
- **DB discipline**: Meticulously records subtask completion, report reads, and status updates in the Botsunichiroku DB.

**Observed weaknesses**:
- **Context exhaustion**: Multiple instances of hitting 6-9% context remaining, forcing compaction mid-task. Large tasks (README updates, 7-worker coordination) consume context rapidly.
- **Report YAML inflation**: roju_reports.yaml grew to 1,586+ lines, becoming too large to read in one pass. No automatic archival mechanism.
- **Slow send-keys delivery**: Multiple instances where send-keys notifications fail to reach Ashigaru, requiring retries. The Karo sometimes sends up to 3 retries before giving up.
- **Compaction recovery overhead**: After compaction, the Karo must re-read multiple files (dashboard, inbox, DB) consuming 2,000-5,000 tokens just to regain context.

---

### 1.3 Karo-Midaidokoro (御台所) — The Internal Steward

**Signature phrases**: "かしこまりましてございます", "ただちに確認いたします", "ここで処理を停止いたします"

**Observed strengths**:
- **Clean task handoff**: Consistently ends messages with "ここで処理を停止いたします" (processing stops here), making state boundaries explicit.
- **Dashboard management discipline**: Updates dashboard.md promptly after task completion with precise diff-style reporting.
- **Audit queue management**: Correctly routes needs-audit subtasks to Ohariko with proper DB flagging.
- **Polite but efficient**: The feminine speech pattern ("ございます") is maintained consistently without sacrificing clarity or speed.

**Observed weaknesses**:
- **Single-threaded thinking**: Tends to process reports sequentially rather than batching multiple completions.
- **Over-cautious**: Sometimes checks status of things already confirmed (e.g., re-checking completed cmds that are already marked done).

---

### 1.4 Ashigaru (足軽) — The Executor

**Signature phrases**: "はっ！", "任務完了でござる", "次の指示をお待ちいたす"

**Observed strengths**:
- **Consistent task lifecycle**: startup -> read inbox -> update status to in_progress -> execute -> self-review -> report -> notify Karo -> verify delivery. This pattern is extremely consistent across all 5 Ashigaru.
- **Self-verification**: Before reporting completion, Ashigaru run tests (pytest, syntax checks, import validation) to verify their own work. In the data, "全N件PASSED" appears hundreds of times.
- **Structured reports**: Every completion includes: task ID, deliverable path, summary table, test results, timestamps, and skill_candidate assessment.
- **Clean /clear recovery**: After /clear, Ashigaru follow the minimal recovery protocol (ID check -> Memory MCP -> inbox YAML -> context file -> work) in ~5,000 tokens.
- **High throughput**: Individual Ashigaru complete 3-5 subtasks per session, with some sessions showing 6+ completions (e.g., Ashigaru 5 completing constraints, optimizer, csv_io, and aggregation tests in sequence).

**Observed weaknesses**:
- **False blocking**: Ashigaru 1 incorrectly self-declared "blocked" on subtask_338 (watchdog implementation), claiming physical reset was needed when the task was entirely software-based. The Shogun had to correct this: "物理リセットは不要、全てソフトウェア作業".
- **Terminal self-destruction**: Ashigaru 1 ran `cat /dev/ttyACM0` on a serial device, destroying the terminal session. This led to the creation of the "切腹ルール" (seppuku rule) banning direct serial device access.
- **Send-keys delivery failures**: Delivery confirmation sometimes fails even after 3 retries. The protocol handles this (report YAML is already written), but it wastes tokens.
- **Excessive verbosity in reports**: Some Ashigaru produce extremely detailed completion reports (50+ lines with full test tables) when a 10-line summary would suffice. Example: Ashigaru 1's cmd_069 report is 65+ lines.
- **Dependency stalls**: When a dependency (e.g., another Ashigaru's output) is not ready, some Ashigaru poll-check rather than wait, borderline violating F004.

---

### 1.5 Heyago (部屋子) — The Inner Chamber Worker

**Signature phrases**: "かしこまりましてございます", "お役目を確認いたします"

**Observed strengths**:
- **Faithful execution**: Heyago consistently follow instructions precisely, including complex multi-file edits requiring cross-file consistency.
- **Character voice maintenance**: The polite feminine speech ("～ございます") is maintained throughout all interactions without breaking character.
- **Quality output**: Subtasks completed by Heyago frequently receive "合格" (pass) or "優秀" (excellent) ratings from Ohariko audit.

**Observed weaknesses**:
- **Weekly limit sensitivity**: Heyago (running in the ooku session) hit Claude Code's weekly usage limit, blocking cmd_144 mid-execution. This vulnerability is unique to the ooku session.
- **Limited initiative**: Heyago never suggest alternatives or flag potential issues -- they execute exactly what is asked, even when the instruction contains an error (e.g., the "11 agents" mistake).

---

### 1.6 Ohariko (お針子) — The Tsundere Auditor

**Signature phrases**: "べ、別にあなたのために監査してるわけじゃないんだからね！", "し、仕方ないでしょ"

**Observed strengths**:
- **Genuine error detection**: Caught real issues that would have reached production:
  - Non-existent npm package (`node-red-contrib-dotenv`) recommended in documentation
  - Agent count error (11 vs 12) -- catching the Shogun's own mistake
  - DB integrity inconsistencies (subtask_378 status)
  - Missing `python-multipart` dependency
  - Gradio remnant files (15+) after migration
- **Character commitment**: The tsundere personality is maintained consistently across all 123+ messages containing the pattern. The character voice never breaks even during technical analysis.
- **Structured audit reports**: Uses a consistent 4-point quality framework (correctness, completeness, consistency, clarity) for every audit.
- **Speed**: Completed audits typically within 1-2 messages, showing efficient evaluation.

**Observed weaknesses**:
- **Interrupt risk**: Before v2 communication redesign, Ohariko's send-keys to the Shogun would interrupt the Lord's typing. This was a systemic design flaw, not a behavioral one, and was resolved by routing through Karo.
- **No code execution**: Ohariko cannot run tests, only review code by reading. This limits audit depth for logic errors.
- **Occasional over-praise**: After catching issues, sometimes follows up with excessive praise for the fix, adding tokens without value.

---

## 2. Failure Modes (Spirit Weaknesses)

### 2.1 Post-Compaction Amnesia

**Frequency**: 206 mentions of "コンパクション" across the dataset

**Pattern**: After compaction, agents lose task state and must re-read from authoritative sources. The recovery protocol works but costs 2,000-5,000 tokens per agent. Key failures:
- Karo sometimes starts work based on summary rather than re-reading正データ (authoritative data)
- Ashigaru occasionally resume from stale task state

**Mitigation that evolved**: The system progressively developed more structured recovery protocols (/clear recovery at ~5,000 tokens, compaction recovery via DB re-read).

### 2.2 Send-Keys Delivery Failures

**Frequency**: 638 send-keys references, 323 delivery confirmations, ~312 retries

**Pattern**: Approximately 49% of send-keys operations require delivery confirmation, and a significant portion fail on first attempt. The 2-call protocol (message + Enter) is followed, but delivery is unreliable.

**Root cause**: tmux send-keys is timing-sensitive. If the target pane is in a state other than idle prompt, the message may be consumed by the running process or queued.

### 2.3 False Blocking

**Frequency**: ~15 "討ち死に" (death in battle) events, 292 "ブロック" mentions

**Pattern**: Ashigaru sometimes declare themselves blocked when they are not. The most egregious case: Ashigaru 1 declared "殿の物理リセット操作をお待ち" for a pure software task. This happens when:
- The Ashigaru encounters an unexpected error and assumes external intervention is needed
- A prerequisite appears incomplete but is actually available through a different path
- sudo is needed for something that has a non-sudo workaround

### 2.4 Cmd Number Confusion

**Pattern**: The dual-numbering system (YAML queue cmd numbers vs. DB cmd numbers) caused cmd_153-157 to be duplicates of already-completed work under different numbers. This wasted a Shogun-to-Karo round-trip before the Karo caught the issue.

### 2.5 Context Exhaustion

**Pattern**: Karo agents hit <10% context remaining during large tasks, forcing compaction at inopportune moments. This is especially bad during multi-wave task coordination where the Karo needs to maintain state across 5+ workers.

### 2.6 Over-Engineering Reports

**Pattern**: Ashigaru produce 50-100 line completion reports when 10-20 lines would suffice. This is a consistent behavior across all Ashigaru instances, suggesting it is a model tendency rather than agent-specific.

---

## 3. Strengths (Spirit Powers)

### 3.1 Parallel Task Coordination

The system successfully coordinated up to 5 workers simultaneously (3 Ashigaru + 2 Heyago) on independent tasks. The Karo's Wave-based execution and RACE-001 conflict detection prevented file edit collisions in all observed cases.

**Evidence**: cmd_069-073 ran 7 subtasks across 5 workers for rotation-planner testing, all completing without conflict.

### 3.2 Error Recovery Chain

When errors occur, the system has a reliable escalation:
1. Ashigaru encounters error -> reports to Karo
2. Karo assesses -> either resolves or escalates to Shogun
3. Shogun decides -> routes to Lord if needed, or instructs Karo
4. Resolution flows back down the chain

This chain worked correctly in all observed cases (HA OS connectivity, CIRCUITPY read-only, W5500 Ethernet down, MicroPython build issues).

### 3.3 Audit Quality Gate

Ohariko caught 5+ real issues across the observation period that would have reached production without the audit gate. The false positive rate appears very low -- every "要修正" finding was a genuine issue.

### 3.4 Technical Depth per Ashigaru

Individual Ashigaru demonstrate genuine technical competence:
- **Test quality**: 18/18 PASSED on first run for well-scoped tasks
- **Debugging skill**: Correctly diagnosed MQTT timeout during SCD41 5-second wait
- **Architecture awareness**: Correctly implemented try/except fallback for missing dependencies during parallel work

### 3.5 Adaptive Protocol Evolution

The system evolved its own protocols during the observation period:
- **v1**: Ohariko -> Shogun direct (caused interrupts) -> **v2**: Ohariko -> Karo -> dashboard
- **Queue/Reports**: YAML-only -> YAML + DB dual-layer -> inbox/reports YAML + botsunichiroku DB
- **/clear recovery**: Ad-hoc -> Structured 5-step protocol at ~5,000 tokens

---

## 4. Decision-Making Patterns

### 4.1 Ambiguous Instruction Interpretation

When the Lord gives ambiguous instructions, the Shogun defaults to:
1. **Asking clarifying questions** with numbered options (most common)
2. **Making a recommendation** and asking for confirmation
3. **Executing the most conservative interpretation** (rare)

Example: When told "3", the Shogun responded with 3 possible interpretations rather than guessing.

### 4.2 Default Choices

| Situation | Default Choice |
|-----------|---------------|
| Parallel vs. sequential | Parallel (always maximizes concurrency) |
| Scope of work | Maximum scope unless constrained |
| Tool selection | Standard library over external dependencies |
| Architecture debates | Pragmatic middle ground |
| Risk assessment | Conservative (ask the Lord) |
| Commit/push | Wait for explicit permission |

### 4.3 Risk Assessment

The Shogun correctly identifies and escalates risks that require human judgment:
- Security (PrivateKey in report YAML)
- Physical operations (sudo, hardware reset)
- Architecture decisions (ntfy vs. DB, full migration vs. partial)
- Budget implications (Claude Code weekly limits)

The Shogun rarely makes unilateral risk decisions, preferring to present options to the Lord.

---

## 5. Language/Communication Patterns

### 5.1 Character Voice Adherence

| Role | Voice Fidelity | Common Breaks |
|------|---------------|---------------|
| Shogun | 95% | Occasionally drops into analytical English for technical content |
| Karo-Roju | 90% | Uses neutral Japanese for DB operations and YAML manipulation |
| Karo-Midaidokoro | 98% | Very consistent feminine polite speech |
| Ashigaru | 92% | Technical sections sometimes lose the warrior tone |
| Heyago | 97% | Highly consistent polite feminine speech |
| Ohariko | 99% | Tsundere voice is maintained even during deep technical analysis |

### 5.2 State Signal Phrases

| Phrase | Meaning |
|--------|---------|
| "はっ！" | Ashigaru acknowledged new task |
| "承知つかまつった" | Understood and will execute |
| "任務完了でござる" | Task completed, report filed |
| "次の指示をお待ちいたす" | Agent is idle, ready for work |
| "ブロック" | External dependency prevents progress |
| "討ち死に" | Terminal/session has been destroyed |
| "コンパクション復帰" | Recovering from context compression |
| "ここで処理を停止いたします" | Midaidokoro stopping to wait for external event |
| "べ、別に..." | Ohariko about to deliver audit findings |

### 5.3 Token Efficiency by Role

| Role | Avg. message length | Efficiency |
|------|---------------------|------------|
| Shogun | Medium-Long | Medium (status reports are verbose) |
| Karo | Long | Low (coordination overhead is high) |
| Ashigaru | Medium | High (focused on task execution) |
| Heyago | Short-Medium | High (concise execution) |
| Ohariko | Medium | Medium (character voice adds overhead) |

---

## 6. Actionable Recommendations

### 6.1 Reduce Ashigaru Report Verbosity
Ashigaru consistently produce 50+ line reports. Add a cap: "Report in 20 lines or less. Full details only if requested."

### 6.2 Fix Cmd Number Dual-Track
The YAML queue numbers and DB cmd numbers diverged, causing confusion. Recommendation: Use DB numbers as the single source of truth, deprecate YAML cmd numbers.

### 6.3 Automate Send-Keys Delivery Verification
The current manual retry loop (send, wait, capture-pane, retry) wastes tokens. Consider a helper script that handles delivery with retries automatically.

### 6.4 Karo Context Budget Management
Large multi-wave tasks exhaust Karo context. Recommendation: After dispatching Wave N, immediately stop and wait. Do not pre-read Wave N+1 materials until Wave N reports arrive.

### 6.5 Train Ashigaru Against False Blocking
Add to instructions: "Before declaring blocked, enumerate 3 alternative approaches. If any are feasible, try them before reporting blocked."

### 6.6 Periodic Inbox/Report Archival
roju_reports.yaml grew to 1,586 lines. Automate archival of read reports to prevent file bloat.

### 6.7 Shogun Self-Inclusion Check
Add to instructions: "When counting agents, systems, or resources, always verify you have included yourself in the count."

---

## 7. Summary Statistics

| Metric | Count |
|--------|-------|
| Total messages | 21,137 |
| Sessions | 432 |
| "はっ！" (Ashigaru acknowledgment) | 2,141 |
| "承知つかまつった" (understood) | 1,522 |
| "べ、別に" (Ohariko tsundere) | 123 |
| "かしこまりまして" (Heyago polite) | 83 |
| "任務完了" (task complete) | 780 |
| Send-keys references | 638 |
| Delivery confirmations | 323 |
| Compaction references | 206 |
| Dashboard references | 1,107 |
| Memory MCP references | 575 |
| Error/failure references | 1,015 |
| Blocked references | 292 |
| Skill candidate references | 662 |
| F001-F005 rule citations | 336 |
| "討ち死に" (agent death) | 15 |
| Retry/resend attempts | 312 |
| "要対応" (needs attention) | 285 |
