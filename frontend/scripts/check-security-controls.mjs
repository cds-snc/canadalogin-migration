import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const FRONTEND_SRC_DIR = path.join(ROOT, "src");
const INDEX_HTML_PATH = path.join(ROOT, "index.html");
const CODE_EXTENSIONS = new Set([".js", ".jsx", ".ts", ".tsx"]);

const blockedPatterns = [
  { name: "eval", regex: /\beval\s*\(/g },
  { name: "new Function", regex: /\bnew\s+Function\s*\(/g },
  {
    name: "string-based setTimeout",
    regex: /\bsetTimeout\s*\(\s*["'`]/g,
  },
  {
    name: "string-based setInterval",
    regex: /\bsetInterval\s*\(\s*["'`]/g,
  },
  {
    name: "dangerouslySetInnerHTML",
    regex: /\bdangerouslySetInnerHTML\b/g,
  },
  { name: "document.write", regex: /\bdocument\.write\s*\(/g },
];

function walk(directoryPath) {
  const entries = fs.readdirSync(directoryPath, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(directoryPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...walk(fullPath));
      continue;
    }

    if (CODE_EXTENSIONS.has(path.extname(entry.name))) {
      files.push(fullPath);
    }
  }

  return files;
}

function getLineNumber(text, index) {
  return text.slice(0, index).split("\n").length;
}

function findBlockedCodePatterns() {
  const failures = [];

  for (const filePath of walk(FRONTEND_SRC_DIR)) {
    const content = fs.readFileSync(filePath, "utf8");

    for (const pattern of blockedPatterns) {
      for (const match of content.matchAll(pattern.regex)) {
        failures.push({
          filePath,
          line: getLineNumber(content, match.index ?? 0),
          rule: pattern.name,
        });
      }
    }
  }

  return failures;
}

function findRemoteTemplateAssets() {
  const content = fs.readFileSync(INDEX_HTML_PATH, "utf8");
  const failures = [];
  const remoteScriptPattern =
    /<script\b[^>]*src\s*=\s*["']https?:\/\/[^"']+["'][^>]*>/gi;
  const remoteStylesheetPattern =
    /<link\b[^>]*rel\s*=\s*["'][^"']*stylesheet[^"']*["'][^>]*href\s*=\s*["']https?:\/\/[^"']+["'][^>]*>/gi;

  for (const pattern of [remoteScriptPattern, remoteStylesheetPattern]) {
    for (const match of content.matchAll(pattern)) {
      failures.push({
        filePath: INDEX_HTML_PATH,
        line: getLineNumber(content, match.index ?? 0),
        rule: "remote script or stylesheet in frontend template",
      });
    }
  }

  return failures;
}

const failures = [...findBlockedCodePatterns(), ...findRemoteTemplateAssets()];

if (failures.length > 0) {
  console.error("Frontend security control check failed:");
  for (const failure of failures) {
    console.error(
      `- ${path.relative(ROOT, failure.filePath)}:${failure.line} blocked ${failure.rule}`,
    );
  }
  process.exit(1);
}

console.log("Frontend security control check passed.");
