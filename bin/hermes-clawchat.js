#!/usr/bin/env node
"use strict";

const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const PACKAGE_ROOT = path.resolve(__dirname, "..");

function usage() {
  console.log(`Usage:
  hermes-clawchat install [--dry-run]

Examples:
  npx -y @newbase-clawchat/hermes-clawchat@latest install
  HERMES_HOME=/opt/data HERMES_DIR=/opt/hermes npx -y @newbase-clawchat/hermes-clawchat@latest install

Environment:
  HERMES_HOME              Defaults to ~/.hermes
  HERMES_DIR               Defaults to $HERMES_HOME/hermes-agent
  HERMES_PYTHON            Defaults to $HERMES_DIR/.venv/bin/python
  CLAWCHAT_GATEWAY_SRC     Defaults to $HERMES_HOME/plugins/clawchat-gateway-src`);
}

function fail(message, code = 1) {
  console.error(`error: ${message}`);
  process.exit(code);
}

function isExecutable(file) {
  try {
    fs.accessSync(file, fs.constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function pathExists(file) {
  try {
    fs.accessSync(file);
    return true;
  } catch {
    return false;
  }
}

function removeIfExists(target) {
  fs.rmSync(target, { recursive: true, force: true });
}

function copyPackageDir(name, installSrc) {
  const from = path.join(PACKAGE_ROOT, name);
  const to = path.join(installSrc, name);
  if (!pathExists(from)) {
    fail(`package is missing required directory: ${from}`);
  }
  fs.cpSync(from, to, {
    recursive: true,
    filter: (src) => {
      const base = path.basename(src);
      return base !== "__pycache__" && base !== ".pytest_cache" && !base.endsWith(".pyc");
    },
  });
}

function copyPackageFile(name, installSrc) {
  const from = path.join(PACKAGE_ROOT, name);
  const to = path.join(installSrc, name);
  if (!pathExists(from)) {
    fail(`package is missing required file: ${from}`);
  }
  fs.copyFileSync(from, to);
}

function run(command, args, options = {}) {
  const result = childProcess.spawnSync(command, args, {
    stdio: "inherit",
    env: options.env || process.env,
  });
  if (result.error) {
    fail(result.error.message);
  }
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

function registerPythonPath(python, srcDir, env) {
  const script = `
import site
import sys
from pathlib import Path

src = Path(sys.argv[1]).resolve()
candidates = []
try:
    candidates.extend(site.getsitepackages())
except Exception:
    pass
try:
    candidates.append(site.getusersitepackages())
except Exception:
    pass

for raw in candidates:
    path = Path(raw)
    if path.exists():
        pth = path / "clawchat_gateway_src.pth"
        pth.write_text(
            "import sys; p = "
            + repr(str(src))
            + "; sys.path.remove(p) if p in sys.path else None; sys.path.insert(0, p)\\n",
            encoding="utf-8",
        )
        print(f"registered python path: {pth} -> {src}")
        break
else:
    raise SystemExit("error: no writable site-packages directory found")
`;
  run(python, ["-c", script, srcDir], { env });
}

function install(argv) {
  const dryRun = argv.includes("--dry-run");
  const hermesHome = process.env.HERMES_HOME || path.join(os.homedir(), ".hermes");
  const hermesDir = process.env.HERMES_DIR || path.join(hermesHome, "hermes-agent");
  const python =
    process.env.HERMES_PYTHON ||
    path.join(hermesDir, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  const installSrc =
    process.env.CLAWCHAT_GATEWAY_SRC || path.join(hermesHome, "plugins", "clawchat-gateway-src");

  const required = ["src", "skills", "pyproject.toml"];
  for (const name of required) {
    if (!pathExists(path.join(PACKAGE_ROOT, name))) {
      fail(`npm package is missing ${name}; reinstall @newbase-clawchat/hermes-clawchat`);
    }
  }

  console.log("ClawChat Hermes installer");
  console.log(`Hermes home: ${hermesHome}`);
  console.log(`Hermes dir:  ${hermesDir}`);
  console.log(`Python:      ${python}`);
  console.log(`Source dir:  ${installSrc}`);

  if (dryRun) {
    console.log("dry-run: package layout is valid; no files changed");
    return;
  }

  if (!isExecutable(python)) {
    fail(`Hermes Python not found or not executable: ${python}
set HERMES_DIR=/path/to/hermes or HERMES_PYTHON=/path/to/python`, 2);
  }
  if (!fs.existsSync(hermesDir) || !fs.statSync(hermesDir).isDirectory()) {
    fail(`Hermes directory not found: ${hermesDir}`, 2);
  }

  const env = { ...process.env, HERMES_HOME: hermesHome };
  removeIfExists(installSrc);
  fs.mkdirSync(installSrc, { recursive: true });
  copyPackageDir("src", installSrc);
  copyPackageDir("skills", installSrc);
  copyPackageFile("pyproject.toml", installSrc);

  registerPythonPath(python, path.join(installSrc, "src"), env);
  run(python, [path.join(installSrc, "src", "clawchat_gateway", "install.py"), "--hermes-dir", hermesDir], { env });

  console.log("");
  console.log("ClawChat gateway installed.");
  console.log(`Hermes home: ${hermesHome}`);
  console.log(`Hermes dir:  ${hermesDir}`);
  console.log(`Source dir:   ${installSrc}`);
  console.log("");
  console.log("Restart Hermes gateway/container for the patched platform and ClawChat skill to load.");
}

function main() {
  const args = process.argv.slice(2);
  if (args.length === 0 || args.includes("-h") || args.includes("--help")) {
    usage();
    return;
  }
  const command = args[0];
  if (command === "install") {
    install(args.slice(1));
    return;
  }
  fail(`unknown command: ${command}
run "hermes-clawchat --help" for usage`, 2);
}

main();
