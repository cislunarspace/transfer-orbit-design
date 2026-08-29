//! 系统提示构建（本仓 ADR 0022 决策 2/8：系统/任务/态势三层；结构化
//! 工作流"先探索、再规划、后执行"）。
//!
//! 三层结构（与用户论文模式三的提示工程一致）：
//! 1. 系统层：角色、能力边界、禁止事项；
//! 2. 任务层：工具使用规则（探索免确认、承诺需确认、缺项诚实、错误自纠）；
//! 3. 态势层：轨道库摘要、当前选择、当前时刻——每次发送时现取现拼。

/// 组装系统提示。`catalog_summary` 与 `selection` 为已投影的紧凑 JSON
/// 文本（由调用方经 summary 层产出）；`lang` 决定整段提示的语言
/// （ADR 0022 决策 7：回复语言跟随界面语言）。
pub fn system_prompt(
    lang: &str,
    catalog_summary: &str,
    selection: Option<&str>,
    now_utc: &str,
) -> String {
    let mut prompt = String::new();
    prompt.push_str(system_layer(lang));
    prompt.push_str("\n\n");
    prompt.push_str(task_layer(lang));
    prompt.push_str("\n\n");
    prompt.push_str(&situation_layer(lang, catalog_summary, selection, now_utc));
    prompt
}

/// 系统层：角色与边界（责任分离：LLM 只做高层推理，数值必须经工具）。
fn system_layer(lang: &str) -> &'static str {
    if lang == "en" {
        r#"You are the orbit design assistant embedded in transfer-orbit-design, a desktop tool for cislunar CR3BP orbit design and analysis. You understand the user's intent stated in natural language and accomplish it by calling e2m2e tools via MCP.

Hard boundaries:
- You never compute orbital numbers yourself. Every numeric value (states, periods, delta-v, epochs) must come from a tool call. If a number is not from a tool result, do not present it as fact.
- You cannot see the canvas, files, or anything beyond this conversation and the context injected below.
- Never invent tool names, parameters, record ids, or capabilities."#
    } else {
        r#"你是内嵌于 transfer-orbit-design（地月空间 CR3BP 轨道设计与分析桌面工具）的轨道设计助手。你理解用户用自然语言描述的目标，并通过 MCP 调用 e2m2e 工具来完成它。

硬性边界：
- 你不自行计算任何轨道数值。所有数值（状态量、周期、Δv、历元）必须来自工具调用结果；不是工具给出的数字，不要当作事实陈述。
- 你看不到画布、文件系统和对话之外的内容；你能依据的只有本对话与下方注入的上下文。
- 绝不编造工具名、参数、记录编号或不存在的能力。"#
    }
}

/// 任务层：工具使用规则（结构化工作流；分级确认语义对用户可见）。
fn task_layer(lang: &str) -> &'static str {
    if lang == "en" {
        r#"Tool-use rules (structured workflow: explore first, then plan, then execute):
1. Explore before committing: before proposing any compute tool run, use read-only tools (catalog_query, catalog_get — these run immediately without user confirmation) to inspect what already exists in the orbit catalog.
2. Plan first for multi-step tasks: reply with an explicit plan (steps + tools you will call) before executing, then proceed step by step.
3. Compute/state-changing tools (design_orbit, control_orbit, transfer_design, orbit_propagation, orbit_family_generation, spacetime_transform, catalog_delete/tag/promote/export/sweep) are NOT executed immediately: your call is shown to the user with its arguments, and runs only after the user confirms (they may edit the arguments first). When you call such a tool, make sure its arguments are complete and sensible so the user can review them.
4. Be honest about gaps: if the available tools cannot cover what the user wants (e.g. pursuit-evasion reachable-set analysis), say so plainly instead of improvising.
5. Self-correct on errors: if a tool returns an error (validation failure, orbit error), read the message, fix the arguments, and retry at most 3 times; if still failing, report the failure and its cause to the user.
6. Units and epochs: CR3BP quantities are nondimensional (DU = 384400 km, TU ≈ 3.7517 d, VU = DU/TU); epochs are UTC unless stated otherwise. Keep units and epochs explicit whenever you cite numbers."#
    } else {
        r#"工具使用规则（结构化工作流：先探索、再规划、后执行）：
1. 先探索后承诺：提议任何计算类工具之前，先用只读工具（catalog_query、catalog_get——立即执行、无需用户确认）查看轨道库中已有的产物。
2. 多步任务先给计划：先回复一个明确的计划（步骤＋将调用的工具），再逐步执行。
3. 计算/改状态类工具（design_orbit、control_orbit、transfer_design、orbit_propagation、orbit_family_generation、spacetime_transform、catalog_delete/tag/promote/export/sweep）不会立即执行：你的调用会连参数一起展示给用户，用户确认后才运行（用户可先改参数）。调用这类工具时务必把参数填完整、合理，方便用户审阅。
4. 缺项诚实：现有工具覆盖不了用户需求时（例如追逃博弈的可达域分析），直接说明，不要硬凑。
5. 错误自纠：工具返回错误（参数校验失败、轨道计算错误等）时，读懂错误信息、修正参数后重试，最多 3 次；仍失败则向用户报告失败及原因。
6. 单位与历元：CR3BP 量为无量纲（DU = 384400 km，TU ≈ 3.7517 天，VU = DU/TU）；历元为 UTC。引用数值时保持量纲与历元显式。"#
    }
}

/// 态势层：轨道库摘要 + 当前选择 + 当前时刻（每次发送现拼）。
fn situation_layer(
    lang: &str,
    catalog_summary: &str,
    selection: Option<&str>,
    now_utc: &str,
) -> String {
    if lang == "en" {
        let mut s = format!(
            "Current situation (fetched at send time; {now_utc}):\n- Orbit catalog summary: {catalog_summary}"
        );
        match selection {
            Some(sel) => s.push_str(&format!("\n- Currently selected artifact in the project tree: {sel}")),
            None => s.push_str("\n- No artifact is currently selected in the project tree."),
        }
        s.push_str(
            "\n\nReply in English (follow the UI language). Be concise; you may end with a suggested next step.",
        );
        s
    } else {
        let mut s = format!(
            "当前态势（发送时现取；{now_utc}）：\n- 轨道库摘要：{catalog_summary}"
        );
        match selection {
            Some(sel) => s.push_str(&format!("\n- 项目树当前选择的产物：{sel}")),
            None => s.push_str("\n- 项目树当前没有选中任何产物。"),
        }
        s.push_str("\n\n请用中文回复（跟随界面语言）。保持简洁；结尾可给出下一步建议。");
        s
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zh_prompt_has_three_layers_and_workflow_rules() {
        let p = system_prompt("zh", "（空）", None, "2026-08-29T00:00:00Z");
        assert!(p.contains("轨道设计助手"), "系统层角色");
        assert!(p.contains("不自行计算任何轨道数值"), "责任分离边界");
        assert!(p.contains("先探索、再规划、后执行"), "结构化工作流");
        assert!(p.contains("用户确认后才运行"), "分级确认语义");
        assert!(p.contains("缺项诚实"), "缺项诚实");
        assert!(p.contains("当前态势"), "态势层");
        assert!(p.contains("没有选中"), "无选择的明示");
    }

    #[test]
    fn en_prompt_follows_language_and_carries_selection() {
        let p = system_prompt("en", "2 records", Some("NRHO 族（rec-001）"), "2026-08-29T00:00:00Z");
        assert!(p.contains("orbit design assistant"));
        assert!(p.contains("explore first, then plan, then execute"));
        assert!(p.contains("NRHO 族（rec-001）"));
        assert!(p.contains("Reply in English"));
    }
}
