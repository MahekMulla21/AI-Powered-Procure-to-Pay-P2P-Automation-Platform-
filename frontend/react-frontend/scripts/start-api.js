/**
 * scripts/start-api.js
 * Launches uvicorn from the parent `frontend/` directory where app.py lives.
 * Called by `npm start` via concurrently — works on Windows, Mac, and Linux.
 */

const { spawn } = require("child_process");
const path = require("path");

// app.py is one level up from react-frontend/
const apiDir = path.resolve(__dirname, "..", "..");

console.log(`[API] Starting uvicorn from: ${apiDir}`);

const proc = spawn("uvicorn", ["app:app", "--reload", "--port", "8000"], {
    cwd: apiDir,       // ← run from frontend/ where app.py lives
    stdio: "inherit",  // ← pipe output directly to this terminal
    shell: true,       // ← required on Windows for PATH resolution
});

proc.on("error", (err) => {
    console.error("[API] Failed to start uvicorn:", err.message);
    console.error("[API] Make sure uvicorn is installed: pip install uvicorn");
    process.exit(1);
});

proc.on("close", (code) => {
    if (code !== 0) {
        console.error(`[API] uvicorn exited with code ${code}`);
    }
});