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

export const knowledge_search = tool({
  description:
    "搜索知识库。在企业知识库和用户知识库中搜索与查询相关的知识内容。使用场景：(1) 上下文中的信息不足以回答用户问题时，主动搜索补充；(2) 用户明确要求查询知识库；(3) 需要补充背景信息来完整回答问题。请主动使用此工具，不要等用户要求。参数: query(搜索关键词), scope(可选: enterprise=仅企业知识库, user=仅用户知识库)",
  args: {
    query: tool.schema
      .string()
      .describe("搜索关键词，用于在知识库标题和内容中查找匹配项"),
    scope: tool.schema
      .string()
      .optional()
      .describe("可选范围过滤: enterprise(企业知识库) 或 user(用户知识库)。不传则搜索所有知识库"),
  },
  async execute(args, context) {
    let path = `/knowledge/search?query=${encodeURIComponent(args.query)}`
    if (args.scope) {
      path += `&scope=${encodeURIComponent(args.scope)}`
    }
    const result = await callAPI(path, "GET", null, context.directory)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        const results = parsed.results as Array<{title: string; content: string; scope: string; source_type: string; char_count: number}>
        if (!results || results.length === 0) {
          return `在知识库中未找到与 "${args.query}" 相关的内容`
        }
        let output = `找到 ${results.length} 条知识匹配 "${args.query}":\n\n`
        for (const r of results) {
          const scopeLabel = r.scope === "enterprise" ? "企业" : "用户"
          output += `### [${scopeLabel}] ${r.title}\n`
          output += `${r.content?.substring(0, 800) || ""}\n\n`
        }
        return output.trim() + "\n\n[以上内容已完整返回，无需再用 read 工具读取文件]"
      }
      return `搜索失败: ${parsed.detail || result}`
    } catch {
      return `搜索失败: ${result}`
    }
  },
})

export const knowledge_list = tool({
  description:
    "列出当前用户可用的所有知识库内容。包括用户个人知识库和企业知识库的知识源列表。",
  args: {},
  async execute(_args, context) {
    const result = await callAPI("/knowledge/list", "GET", null, context.directory)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        const userSources = parsed.user_sources as Array<{title: string; source_type: string; char_count: number; tags: string[]}> || []
        const enterpriseSources = parsed.enterprise_sources as Array<{title: string; source_type: string; char_count: number; tags: string[]}> || []

        let output = ""
        if (userSources.length > 0) {
          output += `## 个人知识库 (${userSources.length} 条)\n`
          for (const s of userSources) {
            output += `- ${s.title} (${s.source_type}, ${s.char_count}字)`
            if (s.tags?.length) output += ` [${s.tags.join(", ")}]`
            output += "\n"
          }
        }
        if (enterpriseSources.length > 0) {
          if (output) output += "\n"
          output += `## 企业知识库 (${enterpriseSources.length} 条)\n`
          for (const s of enterpriseSources) {
            output += `- ${s.title} (${s.source_type}, ${s.char_count}字)`
            if (s.tags?.length) output += ` [${s.tags.join(", ")}]`
            output += "\n"
          }
        }
        if (!output) {
          return "当前知识库为空。用户可以通过前端界面添加知识内容。"
        }
        return output.trim()
      }
      return `获取失败: ${parsed.detail || result}`
    } catch {
      return `获取失败: ${result}`
    }
  },
})

export const knowledge_info = tool({
  description:
    "获取当前用户的知识库概览信息，包括知识库是否存在、知识条目数量、总字符数等统计信息。",
  args: {},
  async execute(_args, context) {
    const result = await callAPI("/knowledge/info", "GET", null, context.directory)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        const userKb = parsed.user_kb as {exists: boolean; total_sources: number; total_chars: number}
        const enterpriseKb = parsed.enterprise_kb as {total_bases: number; total_sources: number}
        let output = "## 知识库概览\n\n"
        output += `**个人知识库**: ${userKb.exists ? `${userKb.total_sources} 条知识, ${userKb.total_chars} 字符` : "未创建"}\n`
        output += `**企业知识库**: ${enterpriseKb.total_bases} 个知识库, ${enterpriseKb.total_sources} 条知识\n`
        return output.trim()
      }
      return `获取失败: ${parsed.detail || result}`
    } catch {
      return `获取失败: ${result}`
    }
  },
})

export const knowledge_save = tool({
  description:
    "保存知识到用户的个人知识库。将重要文档、技术规范、项目经验等内容持久化存储，供后续查询使用。AI 应该在用户明确要求保存知识，或在对话中发现值得长期保留的重要信息时主动使用此工具。",
  args: {
    title: tool.schema
      .string()
      .describe("知识标题，简洁明了地概括内容主题，如 'API 接口规范'、'Python 编码规范'"),
    content: tool.schema
      .string()
      .describe("知识内容，支持 Markdown 格式。应包含完整、结构化的信息，便于后续检索和理解"),
    tags: tool.schema
      .string()
      .optional()
      .describe("可选标签，用逗号分隔，如 'API,规范,Python'。有助于分类和检索"),
  },
  async execute(args, context) {
    const body: Record<string, unknown> = {
      title: args.title,
      content: args.content,
    }
    if (args.tags) {
      body.tags = args.tags.split(",").map((t: string) => t.trim()).filter(Boolean)
    }
    const result = await callAPI("/knowledge/save", "POST", body, context.directory)
    try {
      const parsed = JSON.parse(result)
      if (parsed.ok) {
        return `知识保存成功。\n标题: ${args.title}\n字符数: ${args.content.length}${args.tags ? `\n标签: ${args.tags}` : ""}`
      }
      return `保存失败: ${parsed.detail || result}`
    } catch {
      return `保存失败: ${result}`
    }
  },
})
