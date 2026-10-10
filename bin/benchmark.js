#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const yaml = require("js-yaml");

function parseArgs(argv) {
  const args = { force: false, help: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--skill") args.skill = argv[++i];
    else if (arg === "--pipeline") args.pipeline = argv[++i];
    else if (arg === "--challenge") args.challenge = argv[++i];
    else if (arg === "--force") args.force = true;
    else if (arg === "--help" || arg === "-h") args.help = true;
  }
  return args;
}

function printHelp() {
  console.log(`
Usage: npm run benchmark -- --skill <path> --challenge <name> [options]
       npm run benchmark -- --pipeline <team-folder> --challenge <name> [options]

Runs your skill.md (or, for challenge_1b, your pipeline folder) against a
challenge's practice cases locally, so you can iterate freely before making
an official submission. Doesn't touch or affect the real leaderboard.

Options:
  --skill <path>      Path to your skill.md (challenge_1)
  --pipeline <path>   Path to your team folder with pipeline.yaml (challenge_1b)
  --challenge <name>  Challenge to practice against, e.g. challenge_1 (required)
  --force             Re-grade even if nothing changed since your last local run
  --help              Show this message

Requires OPENROUTER_API_KEY to be set in your environment.
`);
}

function repoRoot() {
  return path.resolve(__dirname, "..");
}

function findPracticeCaseFiles(root, challenge) {
  const casesDir = path.join(root, "test_cases", challenge);
  if (!fs.existsSync(casesDir)) {
    console.error(`No test cases found for challenge "${challenge}" at ${casesDir}`);
    process.exit(1);
  }
  return fs
    .readdirSync(casesDir)
    .filter((f) => f.endsWith(".yaml"))
    .map((f) => path.join(casesDir, f))
    .filter((filePath) => {
      const doc = yaml.load(fs.readFileSync(filePath, "utf8"));
      return doc && doc.practice === true;
    });
}

function stagePracticeCases(root, challenge, caseFiles) {
  // score_submission.py already skips `practice: true` cases when scoring
  // for real — that's exactly what an official submission should do, but
  // the opposite of what local practice needs. Rather than adding a
  // practice-specific flag to the core scorer, stage copies with that field
  // stripped, so the existing scorer runs them normally.
  const stagingDir = path.join(root, ".benchmark-cache", challenge, "practice-cases");
  fs.mkdirSync(stagingDir, { recursive: true });
  for (const existing of fs.readdirSync(stagingDir)) {
    fs.unlinkSync(path.join(stagingDir, existing));
  }
  for (const filePath of caseFiles) {
    const doc = yaml.load(fs.readFileSync(filePath, "utf8"));
    delete doc.practice;
    fs.writeFileSync(path.join(stagingDir, path.basename(filePath)), yaml.dump(doc));
  }
  return stagingDir;
}

function findPython() {
  for (const candidate of ["python3", "python"]) {
    const check = spawnSync(candidate, ["--version"]);
    if (check.status === 0) return candidate;
  }
  console.error("Could not find a Python 3 interpreter (tried python3, python). Please install Python 3.");
  process.exit(1);
}

function venvPythonPath(venvDir) {
  return process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");
}

function ensureDeps(root) {
  const venvDir = path.join(root, ".benchmark-venv");
  const marker = path.join(venvDir, ".deps-installed");
  const reqPath = path.join(root, "requirements.txt");
  const reqContent = fs.readFileSync(reqPath, "utf8");

  if (!fs.existsSync(venvDir)) {
    console.log("Setting up a local Python environment (first run only)...");
    const created = spawnSync(findPython(), ["-m", "venv", venvDir], { stdio: "inherit" });
    if (created.status !== 0) {
      console.error("Failed to create a Python virtual environment.");
      process.exit(1);
    }
  }

  const venvPython = venvPythonPath(venvDir);
  const alreadyInstalled = fs.existsSync(marker) && fs.readFileSync(marker, "utf8") === reqContent;

  if (!alreadyInstalled) {
    console.log("Installing Python dependencies (first run only)...");
    const installed = spawnSync(venvPython, ["-m", "pip", "install", "-q", "-r", reqPath], { stdio: "inherit" });
    if (installed.status !== 0) {
      console.error("Failed to install Python dependencies.");
      process.exit(1);
    }
    fs.writeFileSync(marker, reqContent);
  }

  return venvPython;
}

// Minimal RFC4180-style CSV parser (handles quoted fields with embedded
// commas/newlines) — score_submission.py's `response` column can contain
// both, so a naive split(',')/split('\n') would misparse real output.
function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (inQuotes) {
      if (char === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => !(r.length === 1 && r[0] === ""));
}

function printResults(outDir, teamName) {
  const csvPath = path.join(outDir, `${teamName}.csv`);
  const invalidPath = path.join(outDir, `${teamName}.invalid`);

  if (fs.existsSync(invalidPath)) {
    console.log(`\nYour submission is invalid: ${fs.readFileSync(invalidPath, "utf8")}`);
    return;
  }

  if (!fs.existsSync(csvPath)) {
    console.log("\nNo results were produced.");
    return;
  }

  const [header, ...rows] = parseCsv(fs.readFileSync(csvPath, "utf8"));
  // Pipeline results (challenge_1b) carry per-component columns after the
  // first four; show them so teams can see which part of the score moved.
  const extraColumns = header.slice(4);
  let totalScore = 0;
  let totalMax = 0;

  console.log("\n=== Results (practice — does not count toward the real leaderboard) ===");
  for (const row of rows) {
    const [caseId, score, maxPoints] = row;
    const s = Number(score);
    const m = Number(maxPoints);
    totalScore += s;
    totalMax += m;
    const pct = m > 0 ? ((s / m) * 100).toFixed(1) : "0.0";
    console.log(`  ${caseId}: ${s}/${m} (${pct}%)`);
    const details = extraColumns
      .map((name, i) => {
        const value = row[4 + i];
        if (value === undefined || value === "") return null;
        return name === "calls" ? `${name} ${value}` : `${name} ${(Number(value) * 100).toFixed(1)}%`;
      })
      .filter(Boolean);
    if (details.length) console.log(`    ${details.join(" · ")}`);
    if (extraColumns.length && row[3]) console.log(`\n${row[3].replace(/^/gm, "    ")}\n`);
  }
  const totalPct = totalMax > 0 ? ((totalScore / totalMax) * 100).toFixed(1) : "0.0";
  console.log("  ------------------------");
  console.log(`  Total: ${totalScore}/${totalMax} (${totalPct}%)\n`);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !(args.skill || args.pipeline) || (args.skill && args.pipeline) || !args.challenge) {
    printHelp();
    process.exit(args.help ? 0 : 1);
  }

  if (!process.env.GEMINI_API_KEY && !process.env.OPENROUTER_API_KEY) {
    console.error("GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com and set it before running the benchmark.");
    process.exit(1);
  }

  const root = repoRoot();
  const submissionPath = path.resolve(args.skill || args.pipeline);
  if (!fs.existsSync(submissionPath)) {
    console.error(`${args.skill ? "Skill file" : "Pipeline folder"} not found: ${submissionPath}`);
    process.exit(1);
  }

  // Practice runs default to the free Gemini Flash model; Pro isn't on the free tier.
  if (process.env.GEMINI_API_KEY && !process.env.BENCHMARK_MODEL) {
    process.env.BENCHMARK_MODEL = "gemini-3.5-flash";
  }
  const practiceCaseFiles = findPracticeCaseFiles(root, args.challenge);
  if (practiceCaseFiles.length === 0) {
    console.error(`No practice cases found for challenge "${args.challenge}".`);
    process.exit(1);
  }

  const stagingDir = stagePracticeCases(root, args.challenge, practiceCaseFiles);
  const venvPython = ensureDeps(root);
  const outDir = path.join(root, ".benchmark-cache", args.challenge, "results");

  const scorerArgs = [
    path.join(root, "score_submission.py"),
    args.skill ? "--skill" : "--pipeline", submissionPath,
    "--cases", stagingDir,
    "--out", outDir,
  ];
  if (args.force) scorerArgs.push("--force");

  console.log(`\nRunning your ${args.skill ? "skill" : "pipeline"} against the ${args.challenge} practice cases...\n`);
  const result = spawnSync(venvPython, scorerArgs, { cwd: root, stdio: "inherit" });
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }

  const teamName = args.skill ? path.basename(path.dirname(submissionPath)) : path.basename(submissionPath);
  printResults(outDir, teamName);
  const traceDir = path.join(outDir, `${teamName}.traces`);
  if (args.pipeline && fs.existsSync(traceDir)) {
    console.log(`Traces (read these, not just the score): ${path.relative(process.cwd(), traceDir)}/\n`);
  }
}

main();
