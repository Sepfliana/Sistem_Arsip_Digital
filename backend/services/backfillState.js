/**
 * Shared concurrency guard for AI backfill operations.
 * Both the automatic worker and the manual endpoint check this flag
 * to prevent parallel backfill runs.
 */
module.exports = { isBackfillRunning: false };
