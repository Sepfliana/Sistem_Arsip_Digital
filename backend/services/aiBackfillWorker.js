const axios = require("axios");
const backfillState = require("./backfillState");

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";
const AI_HEALTH_URL = `${AI_SERVICE_URL}/health`;
const AI_BACKFILL_INTERVAL_MS = Number(process.env.AI_BACKFILL_INTERVAL_MS) || 10000;

let intervalId = null;

/**
 * Check if the AI service is reachable and model is loaded.
 * @returns {Promise<boolean>}
 */
async function checkAiHealth() {
    try {
        const response = await axios.get(AI_HEALTH_URL, { timeout: 5000 });
        return response.data?.model === "FINAL_READY";
    } catch {
        return false;
    }
}

/**
 * Single backfill cycle. Runs the shared runBackfillAnalysis logic
 * from the controller, guarded by the shared concurrency flag.
 */
async function runCycle() {
    if (backfillState.isBackfillRunning) {
        console.log("[AI-BACKFILL] Previous cycle still running, skipping.");
        return;
    }

    backfillState.isBackfillRunning = true;
    try {
        console.log("[AI-BACKFILL] Checking AI service...");
        const available = await checkAiHealth();

        if (!available) {
            console.log("[AI-BACKFILL] AI service unavailable, retrying later.");
            return;
        }

        console.log("[AI-BACKFILL] AI service available.");

        // Lazy import to avoid circular dependency at module-load time.
        // By the time this runs, the controller is fully loaded.
        const { runBackfillAnalysis } = require("../controllers/auditLogController");
        const result = await runBackfillAnalysis();

        console.log(
            `[AI-BACKFILL] Completed: ${result.processed} analyzed, ${result.errors} failed.`
        );
    } catch (error) {
        console.error("[AI-BACKFILL] Cycle error:", error.message);
    } finally {
        backfillState.isBackfillRunning = false;
    }
}

/**
 * Start the background worker. Runs one cycle immediately (after a short
 * startup delay), then repeats every AI_BACKFILL_INTERVAL_MS.
 */
function startWorker() {
    if (intervalId) return;

    console.log(
        `[AI-BACKFILL] Worker started (interval: ${AI_BACKFILL_INTERVAL_MS}ms)`
    );

    // First cycle after 5 seconds, to let the server finish booting.
    setTimeout(runCycle, 5000);

    intervalId = setInterval(runCycle, AI_BACKFILL_INTERVAL_MS);
}

/**
 * Stop the background worker.
 */
function stopWorker() {
    if (intervalId) {
        clearInterval(intervalId);
        intervalId = null;
        console.log("[AI-BACKFILL] Worker stopped.");
    }
}

module.exports = { startWorker, stopWorker };
