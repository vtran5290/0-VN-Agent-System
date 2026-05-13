import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const root = path.join(os.homedir(), ".cursor", "projects");
const outDir = path.join(process.cwd(), "cursor_chat_export", "recovered_from_agent_transcripts");
fs.mkdirSync(outDir, { recursive: true });

function cleanName(name, maxLen = 90) {
  const cleaned = name.replace(/[\\/:*?"<>|]+/g, "_").trim().replace(/\.+$/, "");
  return (cleaned || "untitled").slice(0, maxLen);
}

function extractText(content) {
  if (typeof content === "string") return content.trim();
  if (Array.isArray(content)) {
    const parts = [];
    for (const item of content) {
      if (typeof item === "string") parts.push(item);
      else if (item && typeof item === "object" && typeof item.text === "string") parts.push(item.text);
    }
    return parts.join("\n").trim();
  }
  if (content && typeof content === "object") {
    for (const k of ["text", "content", "message"]) {
      if (typeof content[k] === "string" && content[k].trim()) return content[k].trim();
    }
  }
  return "";
}

function bestTitle(firstUser, fallback) {
  if (!firstUser) return fallback;
  const firstLine = firstUser.split(/\r?\n/)[0] || "";
  const t = firstLine.replace("<user_query>", "").replace("</user_query>", "").trim();
  return t || fallback;
}

function renderMarkdown(records, transcriptId) {
  const messages = [];
  let firstUser = "";

  for (const rec of records) {
    const role = String(rec?.role || "").toLowerCase();
    const content = rec?.message?.content ?? [];
    let text = extractText(content);
    if (!text) continue;
    if (role === "assistant" && text.includes("[REDACTED]")) {
      text = text.replaceAll("[REDACTED]", "").trim();
      if (!text) continue;
    }
    if (role === "user" && !firstUser) firstUser = text;
    const label = role === "user" ? "User" : role === "assistant" ? "Assistant" : (role || "Message");
    messages.push({ label, text });
  }

  const title = bestTitle(firstUser, transcriptId.slice(0, 8));
  const lines = [`# ${title}`, "", `> transcript_id: \`${transcriptId}\``, "", "---", ""];
  for (const m of messages) lines.push(`### ${m.label}`, "", m.text, "", "---", "");
  return { title, markdown: `${lines.join("\n").trim()}\n` };
}

function walk(dir, out = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const ent of entries) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(full, out);
    else if (ent.isFile() && ent.name.endsWith(".jsonl") && !full.includes(`${path.sep}subagents${path.sep}`)) out.push(full);
  }
  return out;
}

let recovered = 0;
let skipped = 0;
const files = fs.existsSync(root) ? walk(root) : [];
for (const file of files) {
  const text = fs.readFileSync(file, "utf8");
  const rows = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      const obj = JSON.parse(line);
      if (obj && typeof obj === "object") rows.push(obj);
    } catch {}
  }
  if (rows.length === 0) {
    skipped += 1;
    continue;
  }
  const transcriptId = path.basename(file, ".jsonl");
  const { title, markdown } = renderMarkdown(rows, transcriptId);
  if (!markdown.includes("### ")) {
    skipped += 1;
    continue;
  }
  const outPath = path.join(outDir, `${cleanName(title)}__${transcriptId}.md`);
  fs.writeFileSync(outPath, markdown, "utf8");
  recovered += 1;
}

console.log(`Recovered: ${recovered}`);
console.log(`Skipped: ${skipped}`);
console.log(`Output: ${outDir}`);

