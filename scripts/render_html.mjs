// The renderer version is fixed by this skill. Keep page generation local.
process.env.AM_NO_UPDATE_CHECK = "1";
await import("./vendor/answer-me-with-html/am.mjs");
