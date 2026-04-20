import { tool } from "@opencode-ai/plugin"

const API_BASE = "http://127.0.0.1:8000/api/internal"
const INTERNAL_SECRET = process.env.OPENCODE_INTERNAL_SECRET || ""

async function callAPI(
  path: string,
  method: string,
  body: Record<string, unknown> | null,
  directory: string,
): Promise<string> {
  const sep = path.includes("?") ? "&" : "?"
  const url = `${API_BASE}${path}${sep}directory=${encodeURIComponent(directory)}`
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

export const memory_save = tool({
  description:
    "保存跨会话记忆。将重要信息（如项目背景、用户偏好、工作进展）写入长期记忆，供后续会话使用。参数: memory_type(facts=事实记忆|preferences=用户偏好), content(要保存的记忆内容，markdown格式)。AI 应该在认为重要信息值得记住时主动调用此工具。",
  args: {
    memory_type: tool.schema
      .enum(["facts", "preferences"])
      .describe("记忆类型: facts(项目事实、工作进展、上下文) 或 preferences(用户偏好、沟通习惯、工作方式)"),
    content: tool.schema
      .string()
      .describe("要保存的记忆内容，使用 markdown 格式。注意：如果要更新现有内容，需要包含完整的新内容（不是只传差异部分）。"),
  },
  async execute(args, context) {
    const body: Record<string, unknown> = {
      memory_type: args.memory_type,
      content: args.content,
    }
    const result = await callAPI("/memory/save", "POST", body, context.directory)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        const typeLabel = args.memory_type === "facts" ? "事实记忆" : "用户偏好"
        return `${typeLabel}保存成功。\n类型: ${args.memory_type}\n路径: ${parsed.path}`
      }
      return `保存失败: ${parsed.detail || result}`
    } catch {
      return `保存失败: ${result}`
    }
  },
})

export const memory_recall = tool({
  description:
    "读取当前用户的跨会话记忆。返回事实记忆(MEMORY.md)和用户偏好(USER.md)的内容。如需搜索特定关键词，可传入 query 参数进行关键词匹配。",
  args: {
    query: tool.schema
      .string()
      .optional()
      .describe("可选，关键词搜索。如果不传则返回全部记忆内容。"),
  },
  async execute(args, context) {
    let result: string
    let parsed: Record<string, unknown>

    if (args.query) {
      const path = `/memory/search?query=${encodeURIComponent(args.query)}`
      result = await callAPI(path, "GET", null, context.directory)
      try {
        parsed = JSON.parse(result)
        if (parsed.ok) {
          const matches = parsed.matches as Record<string, Array<{line_number: number; matched_line: string; context: string}>>
          const total = parsed.total as number
          if (total === 0) {
            return `在记忆中未找到关键词 "${args.query}"`
          }
          let summary = `在记忆中找到 ${total} 处匹配 "${args.query}":\n\n`
          for (const [type, items] of Object.entries(matches)) {
            if (items.length > 0) {
              const typeLabel = type === "facts" ? "事实记忆" : "用户偏好"
              summary += `【${typeLabel}】\n`
              for (const item of items) {
                summary += `  行 ${item.line_number}: ${item.matched_line}\n`
              }
              summary += "\n"
            }
          }
          return summary.trim()
        }
        return `搜索失败: ${parsed.detail || result}`
      } catch {
        return `搜索失败: ${result}`
      }
    } else {
      result = await callAPI("/memory/read", "GET", null, context.directory)
      try {
        parsed = JSON.parse(result)
        if (parsed.ok) {
          const mem = parsed.memory as { facts: string; preferences: string }
          let output = ""
          if (mem.facts) {
            output += `# 事实记忆 (MEMORY.md)\n${mem.facts}\n`
          }
          if (mem.preferences) {
            if (output) output += "\n\n"
            output += `# 用户偏好 (USER.md)\n${mem.preferences}`
          }
          if (!output) {
            return "当前没有任何记忆。可以通过 memory_save 工具来保存重要信息。"
          }
          return output
        }
        return `读取失败: ${parsed.detail || result}`
      } catch {
        return `读取失败: ${result}`
      }
    }
  },
})
