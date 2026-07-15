import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");
const exists = (relative) => fs.existsSync(path.join(root, relative));
const failures = [];

function fail(message) {
  failures.push(message);
}

function walk(directory, extension, result = []) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory() && !["node_modules", "miniprogram_npm"].includes(entry.name)) {
      walk(target, extension, result);
    } else if (entry.isFile() && target.endsWith(extension)) {
      result.push(target);
    }
  }
  return result;
}

for (const file of walk(root, ".json")) {
  try {
    JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    fail(`${path.relative(root, file)} 不是有效 JSON: ${error.message}`);
  }
}

const app = JSON.parse(read("app.json"));
for (const page of app.pages || []) {
  for (const extension of [".json", ".ts", ".wxml", ".wxss"]) {
    if (!exists(`${page}${extension}`)) fail(`页面缺少文件: ${page}${extension}`);
  }
}

const allowedTags = new Set(["block", "button", "guess-history", "input", "scroll-view", "text", "view"]);
for (const file of walk(root, ".wxml")) {
  const relative = path.relative(root, file);
  const source = fs.readFileSync(file, "utf8");
  const stack = [];
  const tags = source.matchAll(/<\/?([a-z][a-z0-9-]*)(?:\s[^<>]*?)?\s*\/?>/g);
  for (const match of tags) {
    const full = match[0];
    const tag = match[1];
    if (!allowedTags.has(tag)) fail(`${relative} 使用了不支持的标签 <${tag}>`);
    if (full.startsWith("</")) {
      const opening = stack.pop();
      if (opening !== tag) fail(`${relative} 标签闭合错误: 期望 </${opening}>，实际 </${tag}>`);
    } else if (!full.endsWith("/>")) {
      stack.push(tag);
    }
  }
  if (stack.length) fail(`${relative} 存在未闭合标签: ${stack.join(", ")}`);

  const tsFile = file.replace(/\.wxml$/, ".ts");
  const script = fs.existsSync(tsFile) ? fs.readFileSync(tsFile, "utf8") : "";
  for (const binding of source.matchAll(/bind(?:tap|input|confirm|change|submit)="([A-Za-z_$][\w$]*)"/g)) {
    const handler = binding[1];
    if (!new RegExp(`\\b${handler}\\s*\\(`).test(script)) {
      fail(`${relative} 绑定了不存在的方法 ${handler}`);
    }
  }
}

for (const file of walk(root, ".wxss")) {
  const source = fs.readFileSync(file, "utf8");
  const open = (source.match(/{/g) || []).length;
  const close = (source.match(/}/g) || []).length;
  if (open !== close) fail(`${path.relative(root, file)} 花括号数量不匹配 (${open}/${close})`);
}

for (const file of walk(path.join(root, "pages"), ".json")) {
  const config = JSON.parse(fs.readFileSync(file, "utf8"));
  for (const componentPath of Object.values(config.usingComponents || {})) {
    const base = String(componentPath).replace(/^\//, "");
    for (const extension of [".json", ".ts", ".wxml", ".wxss"]) {
      if (!exists(`${base}${extension}`)) fail(`${path.relative(root, file)} 引用缺失组件: ${base}${extension}`);
    }
  }
}

if (failures.length) {
  console.error(failures.map((message) => `- ${message}`).join("\n"));
  process.exit(1);
}

console.log(JSON.stringify({
  pages: app.pages.length,
  wxml_files: walk(root, ".wxml").length,
  wxss_files: walk(root, ".wxss").length,
  json_valid: true,
  tags_balanced: true,
  event_handlers_present: true,
}, null, 2));
