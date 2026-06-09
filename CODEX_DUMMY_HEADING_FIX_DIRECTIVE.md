# Antigravity Directive for Codex (Cursor): Dummy Heading Fix Policy

**Status:** Antigravity Analysis Complete & Approved
**Target Phase:** Execution (Codex to implement)

## 1. Classification & Approval
- **Classification:** Dummy-client heading policy bug (Dual-packet conflict).
- **Approval:** Cursor's hypothesis (Cause B) is **100% confirmed** and approved. The dual transmission of `0xBA` (target facing) and `0xA9` (travel direction) in the same tick causes the server to broadcast conflicting headings, resulting in the follow-camera dizziness and reverse-facing symptoms.
- **Server State:** Server tuning is **NOT** required. The server's `PlayerPositionUpdateHandler` and `PlayerHeadingUpdateHandler` correctly broadcast what they receive. The flaw is entirely client-side.

## 2. Approved Fix Policy (Minimal & Safe)

Please implement the following changes in the Python dummy client:

### A. Single Heading Source While Moving (Crucial)
Suppress `send_heading` (0xBA) while the dummy is actively moving outside of melee range. 
- In `tools/behavior-dummy-client.py`, modify `face_target_for_attack` (or the combat chase loop) so that it **skips** sending `client.send_heading(...)` if the dummy is currently traveling to catch up to the target.
- The `0xA9` position packet implicitly carries the travel heading, and this must be the single source of truth while moving.
- **Exception:** Only send `0xBA` if the dummy is stationary (e.g., within melee stop distance) and needs to pivot to face the target.

### B. No Dual-Packet Conflict
Ensure that `client.send_heading` (0xBA) and `client.send_position_update` (0xA9) with conflicting headings are **never** fired in the same logical tick window.

### C. Gradual Turn / Stepwise Rotation (Optional but Recommended)
To fix the instant "snap" (Cause A) and emulate a real 1.124+ client:
- In `tools/headless-daoc-client.py` (`move_towards_position`), if the difference between the current `self.heading` and the new travel heading is exceptionally large (e.g., > 90 degrees), do not snap instantly.
- Instead, step the heading by a maximum delta per tick (e.g., 60-90 degrees) and send intermediate position updates over 2-3 ticks until facing the correct vector. 
- *Note: Keep this logic simple. Do not overcomplicate pathfinding; just interpolate the heading property.*

## 3. Verification & Testing
- Continue using `--trace-movement-log` to verify that 0xBA and 0xA9 are no longer interleaved during movement.
- Do **not** re-enable `/facegloc` for these tests.
- Maintain `PrivLevel=1` (no GM stealth) and preserve current `191` world speed logic.

**Next Step for Cursor:** Implement the approved heading policy in `behavior-dummy-client.py` and `headless-daoc-client.py`, add necessary unit tests, and re-run the `solohunt` observation session to verify visual stability.
