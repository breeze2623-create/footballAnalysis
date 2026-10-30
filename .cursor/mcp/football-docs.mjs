// Starts the football-docs MCP server (provider docs and metric cards used by the nutmeg skills)
// the same way on every OS. On Windows `npx` is `npx.cmd`, which Node can only start through a shell,
// so `"command": "npx"` in mcp.json fails there with `spawn npx ENOENT`; `"command": "node"` does not.
import { spawn } from "node:child_process";

const PACKAGE = "football-docs@0.17.4";
const NODE_MIN = [22, 13];

const [major, minor] = process.versions.node.split(".").map(Number);
if (major < NODE_MIN[0] || (major === NODE_MIN[0] && minor < NODE_MIN[1])) {
  console.error(`football-docs needs Node.js >= ${NODE_MIN.join(".")}; this is ${process.version}. Install a newer Node.js and restart Cursor.`);
  process.exit(1);
}

const child = process.platform === "win32"
  ? spawn(`npx -y ${PACKAGE}`, { stdio: "inherit", shell: true, windowsHide: true })
  : spawn("npx", ["-y", PACKAGE], { stdio: "inherit" });

child.on("error", (err) => {
  console.error(`football-docs: could not start npx (${err.message}). Is Node.js (with npm) on PATH?`);
  process.exit(1);
});
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => child.kill(sig));
}
