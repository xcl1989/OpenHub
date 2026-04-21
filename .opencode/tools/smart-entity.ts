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
