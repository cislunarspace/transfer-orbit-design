// Git prepare-commit-msg hook for Reasonix.
//
// Reads staged changes and generates a conventional commit message,
// then prepopulates the commit message file. The user can edit it freely
// before the commit completes.
//
// Installation: symlink or copy .git/hooks/prepare-commit-msg -> ../../.reasonix/hooks/prepare-commit-message.sh
// (or the .js version directly if running via `node`)

const fs = require("fs");
const { execSync } = require("child_process");

// ---- Configuration ----
const MAX_LINE_LENGTH = 72;
const MAX_BODY_WIDTH = 72;

// ---- Helpers ----

function run(cmd) {
  try {
    return execSync(cmd, { encoding: "utf8", maxBuffer: 10 * 1024 * 1024 }).trim();
  } catch {
    return "";
  }
}

function classifyType(files, diff) {
  // Try to infer the commit type from what changed
  const paths = files.join(" ");

  if (/test|__tests__|spec/.test(paths) && !/src|lib/.test(paths)) return "test";
  if (/\.md$|docs\//.test(paths)) return "docs";
  if (/ci|\.github|\.gitlab|Dockerfile/.test(paths)) return "ci";
  if (/package\.json|pyproject\.toml|Cargo\.toml|requirements|Gemfile|poetry|Pipfile/.test(paths)) return "chore";
  if (/refactor|cleanup|reorganize|rename/.test(diff.slice(0, 2000).toLowerCase())) return "refactor";
  if (/perf|performance|slow|fast|optimize/.test(diff.slice(0, 2000).toLowerCase())) return "perf";

  return "feat";
}

function classifyScope(files) {
  // Derive a scope from the top-level directory of the first changed file
  for (const f of files) {
    const parts = f.split("/");
    if (parts.length >= 2) return parts[0];
    if (parts.length === 1 && !f.includes(".")) return f;
  }
  return "";
}

function extractDescription(diff) {
  // Take the first few lines of the diff summary and condense into a description
  const lines = diff.split("\n").filter(Boolean);
  for (const line of lines) {
    // Look for added/changed function names or key phrases
    const addMatch = line.match(/^\+{0,3}\s*(?:pub\s+)?(?:fn|def|function|async\s+fn)\s+(\w+)/);
    if (addMatch) return addMatch[1];

    const classMatch = line.match(/^\+{0,3}\s*(?:pub\s+)?(?:class|struct|trait|interface)\s+(\w+)/);
    if (classMatch) return classMatch[1];

    // Import changes
    const importMatch = line.match(/^[+-]\s*(?:import|from)\s+['"]?(.+?)['"]?;?$/);
    if (importMatch) return importMatch[1];
  }

  // Fall back to file-level summary
  const filesChanged = run("git diff --cached --name-only").split("\n").filter(Boolean);
  if (filesChanged.length === 1) {
    const name = filesChanged[0].split("/").pop();
    return name.replace(/\.(py|ts|js|rs|go|md)$/, "");
  }

  return "";
}

function generateCommitMessage(files, diff) {
  const type = classifyType(files, diff);
  const scope = classifyScope(files);
  const desc = extractDescription(diff);

  // Build subject line
  const scopePart = scope ? `(${scope})` : "";
  let subject = desc ? `${type}${scopePart}: ${desc}` : `${type}${scopePart}: `;

  // Truncate subject
  if (subject.length > MAX_LINE_LENGTH) {
    subject = subject.slice(0, MAX_LINE_LENGTH - 3) + "...";
  }

  // Build body — explain what and why
  const bodyParts = [];

  // File summary
  const fileList = files.join(", ");
  bodyParts.push(`Files: ${fileList}`);

  // Staged diff stat
  const stat = run("git diff --cached --stat").split("\n").filter(Boolean).slice(0, 5).join("\n");
  if (stat) bodyParts.push(`\n${stat}`);

  // Key changes extracted from diff
  const additions = (diff.match(/^\+[^+]/gm) || []).length;
  const deletions = (diff.match(/^\-[^-]/gm) || []).length;
  bodyParts.push(`\n+${additions} / -${deletions} lines`);

  // Check for breaking changes
  if (/BREAKING|breaking\s+change/i.test(diff)) {
    bodyParts.unshift("\nBREAKING CHANGE: ");
  }

  return subject + "\n\n" + bodyParts.join("\n") + "\n";
}

// ---- Main ----

// Git passes: $1 = commit message file path, $2 = source (message/merge/squash/commit), $3 = SHA (for amend)
const [,, commitMsgPath, source] = process.argv;

// Only intervene for normal commits (not merge, not amend with -m)
if (source === "merge" || source === "squash") {
  process.exit(0);
}

if (!commitMsgPath) {
  process.exit(0);
}

// Check if there are staged changes
const diff = run("git diff --cached");
if (!diff) {
  process.exit(0);
}

// Check if a message was already provided via -m
const existingMessage = fs.existsSync(commitMsgPath) ? fs.readFileSync(commitMsgPath, "utf8").trim() : "";
if (existingMessage && !existingMessage.startsWith("#")) {
  // User provided -m flag or there's already a real message — don't overwrite
  process.exit(0);
}

const files = run("git diff --cached --name-only").split("\n").filter(Boolean);
const message = generateCommitMessage(files, diff);

// Write the generated message; git will show it in the editor for the user to adjust
fs.writeFileSync(commitMsgPath, message);
