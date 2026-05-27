// Session file tracker for Reasonix.
// Reads a PostToolUse payload from stdin and appends a log entry for
// write_file / edit_file / multi_edit operations.
//
// Log format (tab-separated): <session_marker>\t<unix_ts>\t<file_path>
//
// Reasonix doesn't expose a REASONIX_SESSION_ID env var, so we derive a
// session marker from the first write in a new session: a timestamp-based
// marker is written once and reused for subsequent writes within the same
// process tree (tracked via a marker file keyed by PID namespace).

const fs = require("fs");
const path = require("path");

const TRACKED = new Set(["write_file", "edit_file", "multi_edit"]);

function getProjectRoot(cwd) {
  // cwd from the hook payload is the project root
  return cwd || process.cwd();
}

function getSessionMarker(projectRoot) {
  const markerDir = path.join(projectRoot, ".reasonix");
  fs.mkdirSync(markerDir, { recursive: true });
  const markerFile = path.join(markerDir, ".session-marker");

  // Check if there's a recent marker (within last 6 hours)
  try {
    const stat = fs.statSync(markerFile);
    const ageSec = (Date.now() - stat.mtimeMs) / 1000;
    if (ageSec < 6 * 3600) {
      return fs.readFileSync(markerFile, "utf8").trim();
    }
  } catch (_) {
    // No marker yet — create one
  }

  // Create a new session marker
  const marker = `s${Math.floor(Date.now() / 1000)}-${Math.random().toString(36).slice(2, 8)}`;
  fs.writeFileSync(markerFile, marker, "utf8");
  return marker;
}

function extractFilePaths(toolName, toolArgs) {
  const paths = [];
  if (toolName === "write_file" || toolName === "edit_file") {
    if (toolArgs && toolArgs.path) {
      paths.push(toolArgs.path);
    }
  } else if (toolName === "multi_edit") {
    if (toolArgs && Array.isArray(toolArgs.edits)) {
      for (const edit of toolArgs.edits) {
        if (edit.path) paths.push(edit.path);
      }
    }
  }
  return paths;
}

let buf = "";
process.stdin.on("data", (chunk) => {
  buf += chunk;
});
process.stdin.on("end", () => {
  try {
    const payload = JSON.parse(buf);
    if (!TRACKED.has(payload.toolName)) return;

    const filePaths = extractFilePaths(payload.toolName, payload.toolArgs);
    if (filePaths.length === 0) return;

    const projectRoot = getProjectRoot(payload.cwd);
    const reasonixDir = path.join(projectRoot, ".reasonix");
    fs.mkdirSync(reasonixDir, { recursive: true });

    const sessionMarker = getSessionMarker(projectRoot);
    const now = Math.floor(Date.now() / 1000);

    const logPath = path.join(reasonixDir, "session-files.log");
    const lines = filePaths.map(
      (fp) => `${sessionMarker}\t${now}\t${fp}\n`
    );
    fs.appendFileSync(logPath, lines.join(""));
  } catch (_) {
    // Swallow errors so the hook never blocks tool execution.
  }
});
