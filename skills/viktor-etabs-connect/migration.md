# Migrate an ETABS app to Connect or Attach

Use this guide for a standalone `comtypes` app or an existing VIKTOR app that sends a script to `ETABSAnalysis`. Preserve the source call order, inputs, units, checks, and results. The APIs are beta. Check the installed SDK and worker versions.

## Port an existing ETABS workflow

1. Trace the source workflow. Identify the model it needs, the calls it makes, and the data it returns. Keep the model requirements the user specified and the checks the source already performs.
2. Choose the session for that model. Use `attach()` to work with the model the engineer opened. Use `connect()` when the app starts a new model. Replace the source COM startup and shutdown with the selected context manager.
3. Pass the session's `sap` to the existing helpers. Adapt their arguments and outputs to the wrapper signature. Keep the source units, call order, and status checks for the work the app performs.
4. Adapt file operations when the workflow uses them. Use the worker's supported paths and preserve any save step required before analysis.
5. Read the values the app needs before the session closes. Keep the input and result formats the app expects.

See the examples for [reading an open model](examples.md#work-with-an-open-model), [creating a fresh model](examples.md#start-a-fresh-model), or [porting a build-and-analyze workflow](examples.md#build-and-analyze-a-beam-in-an-open-etabs-model).

Sources: [VIKTOR ETABS integration](https://docs.viktor.ai/docs/create-apps/software-integrations/etabs-and-sap2000/) and [ETABS SDK reference](https://docs.viktor.ai/sdk/api/external/etabs/).

## 1. Inventory the existing behavior

- Identify where the source gets its COM model, what it reads or changes, and how the app uses the results. For `ETABSAnalysis`, also trace the script and file handoff.
- Record whether the script starts ETABS or attaches to an existing model, whether it initializes or clears a model, and whether the engineer must keep the model open.
- Record units, geometry, materials, loads, combinations, analysis steps, result rows, and error messages. Save representative inputs and expected outputs for comparison.
- Identify model files, external files, worker-only packages, and operations that require the ETABS instance or session files to survive the job. Direct sessions cannot currently return the worker's model file. Keep the script integration if a required workflow cannot be reproduced.

## 2. Select the session and configure the worker

| Existing intent | Direct session | Behavior |
| --- | --- | --- |
| Start a fresh app-owned model | `vkt.etabs.connect()` | Opens a new empty instance for the session. |
| Work on an engineer's open model | `vkt.etabs.attach()` | Attaches to an existing instance; fails if none is running and leaves it open after detach. |

For attach, use a personal worker on the engineer's machine, open the intended model, and keep only one ETABS instance open. Keep `InitializeNewModel`, `File.NewBlank`, and `File.NewGridOnly` in the fresh `connect()` path. A failed write can leave partial changes. Inspect the model before retrying.

Use SDK 14.31.0 or later for `connect()` and 14.33.0 or later for `attach()`. Add `"etabsconnect"` to `worker_integrations` in `viktor.config.toml`; keep other required entries. Start the ETABS personal worker in VIKTOR Desktop on a licensed, interactive Windows session. Direct sessions do not require `comtypes` or Python on the worker. Keep the legacy `"etabs"` integration while a script path still needs it; remove it only after migration and verification.

## 3. Move the OAPI work into the app

The context manager returns the ETABS `SapModel`. Put input preparation and result formatting in app-side functions. Keep ETABS calls and result reads inside the session. For a standalone app, pass the session model to the existing ETABS helpers. For an `ETABSAnalysis` app, the controller-side session replaces the script upload and file handoff.

For a new model, use `with vkt.etabs.connect(timeout=60) as sap:` and initialize that new model with the appropriate product-specific unit enum. Reuse model-building and extraction functions after adapting each call and result shape. Copy all needed values into ordinary Python data while the session is open; return data in the same schema the views expect. Replace JSON serialization only when no consumer needs that contract.

## 4. Translate calls and validate outputs

- Compare each call to the installed ETABS OAPI signature. Direct calls return a status code or output parameters followed by a status code; supply required `ref` and `out` placeholders. Do not assume a legacy `comtypes` tuple has the same order or shape. Check every returned status.
- Use `vkt.etabs` enums and explicit units. Preserve load case and combination labels, object and station IDs, step information, and every result row. Validate `NumberResults` and array lengths before building output records.
- In SDK 14.37.0 and later, calls can return deferred values. Read each status where the source checks it. Convert result values inside the open session. See [worker limits](units-and-worker.md#worker-limits) for timeouts and deferred calls.
- For table operations, keep the source keys, table versions, row preparation, and stage and apply order. See the [table reference](reference.md#database-tables).
- Use relative filenames for supported session file arguments. If the workflow runs analysis on an untitled model, save it with `File.Save("model.edb")` before `RunAnalysis()`. If the workflow uses an already-saved model and keeps its path, ETABS can use that path for analysis. Wrapper saves go to a temporary worker directory. The engineer saves a permanent copy in ETABS. [CSI analysis file requirement](https://docs.csiamerica.com/help-files/etabs-api-2015/html/ca865c06-25c7-d478-1fd8-45cc11891e5b.htm) · [VIKTOR file limits](https://docs.viktor.ai/sdk/api/external/etabs/#attach)

## 5. Test and complete the migration

Use an interactive Windows worker for a live comparison on a known disposable model. Compare geometry, loads, combinations, analysis completion, all relevant results, and tolerances. The box culvert sample builds a model and extracts results inside one `connect()` session; the beam and column sample reads an open model with `attach()`. Neither example proves that another project's engineering results are correct.

Remove the old script, input/output file handoff, `comtypes` dependency, or legacy worker configuration only after confirming that no other app path needs it. Report any feature that remains on the legacy integration.
