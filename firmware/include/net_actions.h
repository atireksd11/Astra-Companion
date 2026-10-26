#pragma once

// Apply robot actions from a bridge {"type":"done", ...} text payload.
// Uses a lightweight scan of the "actions" array only (no JSON library).
void netApplyDoneActions(const char *doneJson);
