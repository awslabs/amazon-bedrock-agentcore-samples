const http = require("http");
const { spawn } = require("child_process");

const PORT = process.env.PORT || 8080;

function runCodex(prompt, sessionId) {
  return new Promise((resolve, reject) => {
    let args;
    if (sessionId) {
      args = ["exec", "resume", sessionId, prompt, "--json", "--sandbox", "danger-full-access", "--skip-git-repo-check"];
    } else {
      args = ["exec", prompt, "--json", "--sandbox", "danger-full-access", "--skip-git-repo-check"];
    }

    console.log(`[runCodex] sessionId=${sessionId || "(none)"} prompt="${prompt}"`);
    console.log(`[runCodex] args: ${JSON.stringify(args)}`);

    const proc = spawn("codex", args, {
      env: { ...process.env, HOME: "/home/agent" },
      cwd: "/home/agent",
      timeout: 300_000,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (d) => (stdout += d));
    proc.stderr.on("data", (d) => (stderr += d));

    proc.on("close", (code) => {
      console.log(`[runCodex] exited code=${code} stderr="${stderr}" stdout="${stdout.slice(0, 200)}"`);
      if (code !== 0) {
        reject(new Error(`codex exited ${code}: ${stderr}`));
        return;
      }
      // --json emits one JSON object per line, last one has the result
      const lines = stdout.trim().split("\n").filter(Boolean);
      try {
        const last = JSON.parse(lines[lines.length - 1]);
        resolve({
          response: last.result || last.message || stdout.trim(),
          sessionId: last.session_id || null,
        });
      } catch {
        resolve({ response: stdout.trim(), sessionId: null });
      }
    });
    proc.on("error", reject);
  });
}

function readBody(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (chunk) => (data += chunk));
    req.on("end", () => resolve(data));
  });
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "healthy" }));
    return;
  }

  if (req.method === "POST") {
    try {
      const body = await readBody(req);
      const { prompt, sessionId } = JSON.parse(body);
      const result = await runCodex(prompt, sessionId);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(result));
    } catch (err) {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: err.message }));
    }
    return;
  }

  res.writeHead(405);
  res.end();
});

server.listen(PORT, () => {
  console.log(`Codex agent listening on port ${PORT}`);
});
