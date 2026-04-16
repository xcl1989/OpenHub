import { tool } from "@opencode-ai/plugin"

const API_BASE = "http://127.0.0.1:8000/api/internal"
const INTERNAL_SECRET = process.env.OPENCODE_INTERNAL_SECRET || ""

async function callAPI(
  path: string,
  method: string,
  body: Record<string, unknown> | null,
  directory: string,
): Promise<string> {
  const url = `${API_BASE}${path}?directory=${encodeURIComponent(directory)}`
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

export const scheduled_task_create = tool({
  description:
    "创建定时任务。将一个问题按 cron 表达式定时发送给 AI 执行。参数: name(任务名称), question(要发送给AI的问题), cron_expression(APScheduler标准cron，5段空格分隔：分 时 日 月 周，*表示任意值，如 '0 9 * * *' 表示每天9点，'0 5 16 4 *' 表示4月16日5点，'*/30 * * * *' 表示每30分钟), model(可选，指定模型ID)",
  args: {
    name: tool.schema.string().describe("任务名称，如'每日在建项目查询'"),
    question: tool.schema
      .string()
      .describe("要发送给 AI 的完整问题，如'查询在建项目数量并汇总'"),
    cron_expression: tool.schema
      .string()
      .describe(
        "APScheduler cron 表达式，5个字段用空格分隔：分(0-59) 时(0-23) 日(1-31) 月(1-12) 周(0-6)。例如 '0 9 * * *' 每天9点，'0 5 1 * *' 每月1日5点，'0 9 * * 1-5' 工作日9点，'*/30 * * * *' 每30分钟。必须是5个字段，多填或少填都会导致任务无法执行。",
      ),
    model: tool.schema
      .string()
      .optional()
      .describe("可选，指定模型ID。不填使用默认模型"),
  },
  async execute(args, context) {
    const body: Record<string, unknown> = {
      name: args.name,
      question: args.question,
      cron_expression: args.cron_expression,
    }
    if (args.model) body.model_id = args.model
    const result = await callAPI("/tasks", "POST", body, context.directory)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        const t = parsed.task
        return `定时任务创建成功！\n- 任务ID: ${t.id}\n- 名称: ${t.name}\n- 问题: ${t.question}\n- Cron: ${t.cron_expression}\n- 状态: 已启用\n下次执行时间将按 cron 表达式自动计算。`
      }
      return `创建失败: ${result}`
    } catch {
      return `创建失败: ${result}`
    }
  },
})

export const scheduled_task_list = tool({
  description: "列出当前用户的所有定时任务，包括启用状态、cron表达式、上次执行时间等",
  args: {},
  async execute(_args, context) {
    const result = await callAPI("/tasks", "GET", null, context.directory)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok && parsed.tasks.length === 0) {
        return "当前没有定时任务。"
      }
      if (parsed.ok) {
        const lines = parsed.tasks.map(
          (t: Record<string, unknown>) =>
            `- [${t.enabled ? "启用" : "暂停"}] ID:${t.id} | ${t.name} | Cron: ${t.cron_expression} | 执行次数: ${t.run_count} | 上次执行: ${t.last_run_at || "未执行"}`,
        )
        return `共有 ${parsed.tasks.length} 个定时任务:\n${lines.join("\n")}`
      }
      return `查询失败: ${result}`
    } catch {
      return `查询失败: ${result}`
    }
  },
})

export const scheduled_task_update = tool({
  description:
    "修改已有定时任务的名称、问题或执行时间。只需传入要修改的字段。参数: task_id(任务ID), name(可选), question(可选), cron_expression(可选)",
  args: {
    task_id: tool.schema.number().describe("要修改的任务ID"),
    name: tool.schema.string().optional().describe("新的任务名称"),
    question: tool.schema.string().optional().describe("新的问题内容"),
    cron_expression: tool.schema
      .string()
      .optional()
      .describe("新的 cron 表达式"),
  },
  async execute(args, context) {
    const body: Record<string, unknown> = {}
    if (args.name) body.name = args.name
    if (args.question) body.question = args.question
    if (args.cron_expression) body.cron_expression = args.cron_expression
    if (Object.keys(body).length === 0) {
      return "没有指定要修改的字段，请至少提供 name、question 或 cron_expression 之一。"
    }
    const result = await callAPI(
      `/tasks/${args.task_id}`,
      "PUT",
      body,
      context.directory,
    )
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        return `任务更新成功: ${JSON.stringify(parsed.task)}`
      }
      return `更新失败: ${result}`
    } catch {
      return `更新失败: ${result}`
    }
  },
})

export const scheduled_task_delete = tool({
  description: "删除一个定时任务。参数: task_id(要删除的任务ID)",
  args: {
    task_id: tool.schema.number().describe("要删除的任务ID"),
  },
  async execute(args, context) {
    const result = await callAPI(
      `/tasks/${args.task_id}`,
      "DELETE",
      null,
      context.directory,
    )
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        return `任务 ${args.task_id} 已删除。`
      }
      return `删除失败: ${result}`
    } catch {
      return `删除失败: ${result}`
    }
  },
})

export const scheduled_task_pause = tool({
  description: "暂停一个定时任务，暂停后不会自动执行，但可以随时恢复。参数: task_id(任务ID)",
  args: {
    task_id: tool.schema.number().describe("要暂停的任务ID"),
  },
  async execute(args, context) {
    const result = await callAPI(
      `/tasks/${args.task_id}/pause`,
      "POST",
      null,
      context.directory,
    )
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        return `任务 ${args.task_id} 已暂停。使用 scheduled_task_resume 可恢复。`
      }
      return `暂停失败: ${result}`
    } catch {
      return `暂停失败: ${result}`
    }
  },
})

export const scheduled_task_resume = tool({
  description: "恢复一个已暂停的定时任务。参数: task_id(任务ID)",
  args: {
    task_id: tool.schema.number().describe("要恢复的任务ID"),
  },
  async execute(args, context) {
    const result = await callAPI(
      `/tasks/${args.task_id}/resume`,
      "POST",
      null,
      context.directory,
    )
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        return `任务 ${args.task_id} 已恢复，将按 cron 表达式继续执行。`
      }
      return `恢复失败: ${result}`
    } catch {
      return `恢复失败: ${result}`
    }
  },
})
