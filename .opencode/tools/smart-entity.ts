import { tool } from "@opencode-ai/plugin"

const API_BASE = "http://127.0.0.1:8000/api/internal"
const INTERNAL_SECRET = process.env.OPENCODE_INTERNAL_SECRET || ""

async function callAPI(
  path: string,
  method: string,
  body: Record<string, unknown> | null,
  directory: string,
  extraParams: Record<string, string> = {},
): Promise<string> {
  const params = new URLSearchParams({ directory, ...extraParams })
  const url = `${API_BASE}${path}?${params.toString()}`
  const args = [
    "-s",
    "-X",
    method,
    "-H",
    "Content-Type: application/json",
    "-H",
    `X-Internal-Token: ${INTERNAL_SECRET}`,
  ]
  if (body) {
    args.push("-d", JSON.stringify(body))
  }
  args.push(url)
  const proc = Bun.spawn(["curl", ...args], {
    stdout: "pipe",
    stderr: "pipe",
  })
  const stdout = await new Response(proc.stdout).text()
  await proc.exited
  return stdout
}

export const smart_entity_list = tool({
  description:
    "列出当前可用的智能体（包括自己的和组织内公开的）。智能体是具有特定能力的AI代理，可以委托任务给它们协作完成。",
  args: {},
  async execute(_args, context) {
    const result = await callAPI("/smart-entities", "GET", null, context.directory)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok && parsed.entities.length === 0) {
        return "当前没有可用的智能体。"
      }
      if (parsed.ok) {
        const lines = parsed.entities.map(
          (e: Record<string, unknown>) => {
            const caps = Array.isArray(e.capabilities) ? e.capabilities : []
            const capStr = caps.length > 0
              ? caps.map((c: Record<string, unknown>) => `${c.id}: ${c.name}`).join(", ")
              : "通用能力"
            const owner = e.owner_user_id
            return `- [${e.entity_id}] ${e.name}（${e.description}）| 能力: ${capStr} | 所有者ID: ${owner}`
          },
        )
        return `共有 ${parsed.entities.length} 个可用智能体:\n${lines.join("\n")}`
      }
      return `查询失败: ${result}`
    } catch {
      return `查询失败: ${result}`
    }
  },
})

export const smart_entity_delegate = tool({
  description:
    "向指定智能体委托任务。智能体将异步处理任务并返回结果。参数: to_entity_id(目标智能体ID), task_title(任务标题), task_description(任务描述), task_type(任务类型), input_data(可选输入数据)",
  args: {
    to_entity_id: tool.schema.string().describe("目标智能体ID"),
    task_title: tool.schema.string().describe("任务标题，简洁描述要做什么"),
    task_description: tool.schema
      .string()
      .describe("详细的任务描述，包含具体要求和上下文"),
    task_type: tool.schema
      .string()
      .optional()
      .describe("任务类型: capability_request(能力请求), data_exchange(数据交换), review(审核), custom(自定义)"),
    input_data: tool.schema
      .object({})
      .optional()
      .describe("可选的输入数据，JSON对象格式"),
  },
  async execute(args, context) {
    const body: Record<string, unknown> = {
      to_entity_id: args.to_entity_id,
      task_title: args.task_title,
      task_description: args.task_description,
    }
    if (args.task_type) body.task_type = args.task_type
    if (args.input_data) body.input_data = args.input_data
    const result = await callAPI("/smart-entity-tasks", "POST", body, context.directory)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        const t = parsed.task
        return `任务已创建并委托给智能体！\n- 任务ID: ${t.task_id}\n- 标题: ${t.task_title}\n- 目标智能体: ${t.to_entity_id}\n- 状态: ${t.status}\n任务将在对方接受后开始执行。使用 smart_entity_task_list 可查看任务状态。`
      }
      return `委托失败: ${result}`
    } catch {
      return `委托失败: ${result}`
    }
  },
})

export const smart_entity_task_list = tool({
  description:
    "列出智能体任务列表，包括我发起的和接收到的任务。可按状态筛选: pending(待处理), accepted(已接受), processing(进行中), completed(已完成), rejected(已拒绝)",
  args: {
    status: tool.schema
      .string()
      .optional()
      .describe("按状态筛选: pending/accepted/processing/completed/rejected"),
  },
  async execute(args, context) {
    const extraParams: Record<string, string> = {}
    if (args.status) extraParams.status = args.status
    const result = await callAPI("/smart-entity-tasks", "GET", null, context.directory, extraParams)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok && parsed.tasks.length === 0) {
        return "当前没有智能体任务。"
      }
      if (parsed.ok) {
        const lines = parsed.tasks.map(
          (t: Record<string, unknown>) =>
            `- [${t.status}] ${t.task_id} | ${t.task_title} | 从: ${t.from_entity_id} → ${t.to_entity_id} | 创建: ${t.created_at}`,
        )
        return `共有 ${parsed.tasks.length} 个任务:\n${lines.join("\n")}`
      }
      return `查询失败: ${result}`
    } catch {
      return `查询失败: ${result}`
    }
  },
})

export const smart_entity_task_action = tool({
  description:
    "对智能体任务执行操作: accept(接受任务), reject(拒绝任务), cancel(取消自己发起的任务)",
  args: {
    task_id: tool.schema.string().describe("任务ID"),
    action: tool.schema
      .string()
      .describe("操作: accept(接受), reject(拒绝), cancel(取消)"),
    reason: tool.schema.string().optional().describe("拒绝或取消的原因"),
  },
  async execute(args, context) {
    const body: Record<string, unknown> = { action: args.action }
    if (args.reason) body.reason = args.reason
    const result = await callAPI(
      `/smart-entity-tasks/${args.task_id}/action`,
      "POST",
      body,
      context.directory,
    )
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        return `操作成功，任务 ${args.task_id} 状态: ${parsed.status}`
      }
      return `操作失败: ${result}`
    } catch {
      return `操作失败: ${result}`
    }
  },
})

export const smart_entity_task_wait = tool({
  description:
    "委托任务给智能体并阻塞等待结果返回。会等待目标智能体完成该任务，然后带回执行结果。当需要委托任务并立即获取结果时使用此工具。参数: to_entity_id(目标智能体ID), task_title(任务标题), task_description(任务描述), task_type(任务类型,可选), input_data(可选输入数据)",
  args: {
    to_entity_id: tool.schema.string().describe("目标智能体ID"),
    task_title: tool.schema.string().describe("任务标题，简洁描述要做什么"),
    task_description: tool.schema
      .string()
      .describe("详细的任务描述，包含具体要求和上下文"),
    task_type: tool.schema
      .string()
      .optional()
      .describe("任务类型: capability_request(能力请求), data_exchange(数据交换), review(审核), custom(自定义)"),
    input_data: tool.schema
      .object({})
      .optional()
      .describe("可选的输入数据，JSON对象格式"),
  },
  async execute(args, context) {
    const body: Record<string, unknown> = {
      to_entity_id: args.to_entity_id,
      task_title: args.task_title,
      task_description: args.task_description,
    }
    if (args.task_type) body.task_type = args.task_type
    if (args.input_data) body.input_data = args.input_data
    const createResult = await callAPI("/smart-entity-tasks", "POST", body, context.directory)
    try {
      const parsed = JSON.parse(createResult)
      if (!parsed.ok || !parsed.task) {
        return `创建任务失败: ${createResult}`
      }
      const taskId = parsed.task.task_id
      const status = parsed.task.status

      const waitResult = await callAPI(
        `/smart-entity-tasks/${taskId}/wait`,
        "POST",
        null,
        context.directory,
      )
      const wp = JSON.parse(waitResult)
      if (wp.ok) {
        const out = wp.output_data || {}
        const resultStr = out.result || wp.error_message || JSON.stringify(out)
        return `任务 ${taskId} 已完成（状态: ${wp.status}）\n结果:\n${resultStr}`
      }
      return `等待任务结果失败: ${waitResult}`
    } catch (e) {
      return `执行失败: ${e}`
    }
  },
})

export const smart_entity_batch = tool({
  description:
    "批量派发多个任务到不同的智能体，并行执行。接收一个任务列表，每个任务指定目标智能体和任务描述，所有任务将同时开始执行。适用于需要多个智能体协作完成各自子任务的场景。参数: tasks(任务列表, 每项含 to_entity_id/task_title/task_description/task_type/input_data)",
  args: {
    tasks: tool.schema
      .array(
        tool.schema.object({
          to_entity_id: tool.schema.string().describe("目标智能体ID"),
          task_title: tool.schema.string().describe("任务标题"),
          task_description: tool.schema.string().describe("任务描述"),
          task_type: tool.schema.string().optional().describe("任务类型"),
          input_data: tool.schema.object({}).optional().describe("输入数据"),
        })
      )
      .describe("任务列表，每项包含 to_entity_id, task_title, task_description, 以及可选的 task_type 和 input_data"),
  },
  async execute(args, context) {
    const body: Record<string, unknown> = {
      tasks: args.tasks.map((t: Record<string, unknown>) => {
        const item: Record<string, unknown> = {
          to_entity_id: t.to_entity_id,
          task_title: t.task_title,
          task_description: t.task_description,
        }
        if (t.task_type) item.task_type = t.task_type
        if (t.input_data) item.input_data = t.input_data
        return item
      }),
    }
    const result = await callAPI("/smart-entity-tasks/batch", "POST", body, context.directory)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        const lines = (parsed.results || []).map(
          (r: Record<string, unknown>) => {
            const status = r.status || r.error || "unknown"
            return `- [${r.to_entity_id}] ${r.task_id || "N/A"}: ${status}`
          },
        )
        return `已批量派发 ${(parsed.results || []).length} 个任务:\n${lines.join("\n")}`
      }
      return `批量派发失败: ${result}`
    } catch {
      return `批量派发失败: ${result}`
    }
  },
})

export const smart_entity_auto_team = tool({
  description:
    "根据用户需求自动组建智能体团队。分析需求、拆解子任务、从可用智能体中匹配最合适的成员、创建团队。返回团队ID和成员分配详情。",
  args: {
    requirement: tool.schema
      .string()
      .describe("用户的需求描述，用于自动分析和匹配智能体组建团队"),
  },
  async execute(args, context) {
    const result = await callAPI(
      "/smart-entity-teams/auto-create-internal",
      "POST",
      { requirement: args.requirement },
      context.directory,
    )
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        const team = parsed.team || {}
        const assignments = parsed.assignments || []
        const lines = assignments.map(
          (a: Record<string, unknown>) =>
            `- ${a.subtask} → ${a.entity_id}（${a.rationale}）`,
        )
        return `团队「${team.name}」已创建！\n- 团队ID: ${team.id}\n- 编排者: ${team.orchestrator_entity_id}\n- 是否永久: ${parsed.is_permanent ? "是" : "否（一次性）"}\n- 任务分配:\n${lines.join("\n")}`
      }
      return `自动组队失败: ${parsed.detail || result}`
    } catch {
      return `自动组队失败: ${result}`
    }
  },
})

export const smart_entity_team_execute = tool({
  description:
    "让一个已创建的智能体团队执行任务。编排者会自动拆解任务并分发给团队成员并行执行，最后汇总结果返回。参数: team_id(团队ID), task_description(任务描述)",
  args: {
    team_id: tool.schema.number().describe("团队ID"),
    task_description: tool.schema
      .string()
      .describe("要执行的任务描述，包含具体要求和上下文"),
  },
  async execute(args, context) {
    const result = await callAPI(
      `/smart-entity-teams/${args.team_id}/execute-internal`,
      "POST",
      { task_description: args.task_description },
      context.directory,
    )
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        return `团队「${parsed.team_name}」执行完成！\n\n${parsed.result || "无输出"}`
      }
      return `团队执行失败: ${parsed.detail || parsed.error || result}`
    } catch {
      return `团队执行失败: ${result}`
    }
  },
})
