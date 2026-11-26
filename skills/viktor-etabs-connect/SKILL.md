---
name: viktor-etabs-connect
description: Build or migrate a VIKTOR ETABS integration with vkt.etabs.connect() or attach(), including DatabaseTables reads and imports, beam force results by station, and migration from ETABSAnalysis or comtypes.
---

# VIKTOR ETABS Connect

Use this skill to build, read, or analyze ETABS models from VIKTOR and to migrate an existing app to Connect.

## Setup

- Declare `worker_integrations = ["etabsconnect"]` in `viktor.config.toml`.
- Use VIKTOR SDK 14.31.0 or later; `attach()` needs 14.33.0 or later.
- The connected Windows worker needs ETABS installed and ready for interactive use.
- Use a logged-in Windows session with an activated licence. Start the personal worker in VIKTOR Desktop and inspect its logs there. No Python environment is needed on the worker for direct calls.

## Session choice

- `vkt.etabs.connect()` starts a fresh ETABS model for the session.
- `vkt.etabs.attach()` binds to the ETABS model already open on the worker.
- Use a `with` block and read the data needed by the VIKTOR view before it closes.
- Keep one ETABS instance open for `attach()`. Use `connect()` when the app needs to start and initialize a new model.
- Live edits can remain after a failure. Read the results before the session ends; session files cannot currently be returned to the app. The engineer saves their attached model.

## OAPI calls

- `sap` is the ETABS model: call paths look like `sap.FrameObj.AddByCoord(...)`.
- Use the SDK enums. Use `eItemType` for object assignments and `eItemTypeElm` for result calls that take that enum.
- Check every CSI status code and use the return shape documented by the CSI signature.
- Use `vkt.testing.mock_ETABSConnection` for both session modes. Verify the actual model and worker behavior separately when available.

## Load when needed

- Read [reference.md](reference.md) for ETABS enums, C# call signatures, model details, database tables, and result extraction.
- See [the beam app](examples.md#build-and-analyze-a-beam-in-an-open-etabs-model) for a complete build, analysis, and results table. Read [examples.md](examples.md) for geometry imports, beam forces by station, and the 3D stick model viewer.
- Read [units-and-worker.md](units-and-worker.md) for present units, file limits, and session timeouts.
- Read [migration.md](migration.md) first when porting a standalone `comtypes` app or `ETABSAnalysis` script. It shows how to choose a session and preserve the source workflow.
