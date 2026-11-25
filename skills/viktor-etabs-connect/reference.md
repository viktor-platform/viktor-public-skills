# ETABS Connect Reference

Source: <https://docs.viktor.ai/docs/create-apps/software-integrations/etabs-and-sap2000/>

## Configuration

```toml
worker_integrations = ["etabsconnect"]
```

`connect()` requires VIKTOR SDK 14.31.0 or later. `attach()` requires 14.33.0 or later. Both use an
`etabsconnect` worker on a Windows machine with ETABS.

## Sessions

Use `connect()` when the app creates a model for the current calculation. Use `attach()` when the
app works with the model an engineer already has open. The context manager owns the session boundary.

```python
with vkt.etabs.connect(timeout=60) as sap:
    # Build and query a fresh model.
    pass

with vkt.etabs.attach(timeout=60) as sap:
    # Query or update the model currently open in ETABS.
    pass
```

## Calling CSI methods

ETABS API signatures are C#. Translate them directly:

- For methods that return a CSI status, `0` means success. Some getters return the value directly. For example, `PointObj.Count()` returns a count and `GetPresentUnits()` returns a unit code.
- Pass a placeholder for every `ref` or `out` parameter. Match the type with `0` for an `int`, `0.0` for a `double`, `""` for a string, `False` for a Boolean, or `[]` for an array. The values return in signature order, followed by the status code.
- Pass optional C# arguments by position. You can omit optional arguments from the end of the call.
- CSI arrays use Python lists, and SDK enums are available under `vkt.etabs`.

```python
def check(ret, operation):
    if ret != 0:
        raise vkt.UserError(f"ETABS failed: {operation} ({ret})")

[frame_name, ret] = sap.FrameObj.AddByCoord(
    0, 0, 0, 6, 0, 0, "", "Default", "Beam", "Global"
)
check(ret, "FrameObj.AddByCoord")
```

Use the model properties `sap.PointObj` and `sap.FrameObj` for objects, `sap.Analyze` to run cases, `sap.Results` to read analysis results, and `sap.RespCombo` for response combinations. The CSI interface behind `sap.RespCombo` is named `cCombo`. [CSI model properties](https://docs.csiamerica.com/help-files/etabs-api-2016/html/15293a27-a035-e64b-a4b4-78356479aa98.htm)

If `ExecutionError` includes `0x80070057`, check the argument count, position, and type against the C# signature. For example, `NumberResults` in `FrameForce` takes `0`, while the station and force arrays take `[]`. [CSI frame force signature](https://docs.csiamerica.com/help-files/etabs-api-2016/html/87689f3e-4175-1627-618b-c4ebae5e89b5.htm)

## ETABS enums

Pass the named `IntEnum` member from `vkt.etabs`. The wrapper sends its integer value to ETABS. The enum class and member names follow the ETABS SDK. [VIKTOR ETABS enums](https://docs.viktor.ai/sdk/api/external/etabs/#eitemtype)

| Call or purpose | Enum members |
| --- | --- |
| Set model units | `eUnits.kN_m_C`, `eUnits.kN_mm_C` |
| Define a material | `eMatType.Steel`, `eMatType.Concrete` |
| Define a load pattern | `eLoadPatternType.Dead`, `eLoadPatternType.Live`, `eLoadPatternType.Rooflive`, `eLoadPatternType.Wind` |
| Define a shell property | `eShellType.ShellThin`, `eShellType.ShellThick`, `eShellType.Membrane` |
| Assign properties to model objects | `eItemType.Objects`, `eItemType.Group`, `eItemType.SelectedObjects` |
| Read results by object, element, group, or selection | `eItemTypeElm.ObjectElm`, `eItemTypeElm.Element`, `eItemTypeElm.GroupElm`, `eItemTypeElm.SelectionElm` |
| Interpret a database table status | `eReturnCode.TableDoesNotExist` has value `-96`. |

```python
# In a new model, add a roof live pattern and its static case.
status = sap.LoadPatterns.Add("ROOF_LIVE", vkt.etabs.eLoadPatternType.Rooflive, 0.0, True)
check(status, "Add ROOF_LIVE pattern")
```

Match the name to the result scope. For `Results.FrameForce`, use the frame object's unique name with `ObjectElm`, an analysis element ID with `Element`, or a group name with `GroupElm`. For `Results.JointDispl`, use a point object name or a point element ID according to the same scope. See [Read beam forces by station](examples.md#read-beam-forces-by-station).

## ETABS model details

- Use `File.NewGridOnly` when the model needs a defined story and grid layout. Keep the actual ID returned by `FrameObj.AddByCoord` or `AddByPoint` for later loads, assignments, and results. [CSI grid model API](https://docs.csiamerica.com/help-files/etabs-api-2016/html/cb79539c-729f-7231-1625-b8f15e018e1f.htm) · [CSI frame object API](https://docs.csiamerica.com/help-files/etabs-api-2016/html/ffa344c1-9d71-810f-15a9-cc0e44cee05f.htm)
- `PropFrame.SetRectangle(name, material, t3, t2)` takes depth before width. `FrameObj.SetReleases` takes four `ref` arrays for the I-end and J-end release flags and partial fixity values. The six flags at each end follow the order `U1, U2, U3, R1, R2, R3`. Check the CSI remarks for unstable release combinations. [Rectangular section API](https://docs.csiamerica.com/help-files/etabs-api-2016/html/5cd12822-51cc-7148-0807-ccafcadb78e9.htm) · [Frame releases API](https://docs.csiamerica.com/help-files/etabs-api-2016/html/967eb7da-6e42-0708-a4e9-00a61d506575.htm)
- A shell area object can produce several analysis elements. For the generated mesh, use `AreaObj.GetElm` for the element IDs and `AreaElm.GetPoints` for each element's connectivity. Use `PointElm.GetCoordCartesian` for generated joint coordinates. A generated point can have no matching point object. [CSI area elements](https://docs.csiamerica.com/help-files/etabs-api-2016/html/8a8cb947-c9bc-dc13-81e8-3964cc6f113b.htm) · [CSI element connectivity](https://docs.csiamerica.com/help-files/etabs-api-2016/html/259fd727-f33d-7889-6ee6-20db022a41d7.htm) · [CSI point element coordinates](https://docs.csiamerica.com/help-files/etabs-api-2016/html/85b95e53-65e4-8ae3-c7b6-7226832f9dde.htm)
- A load pattern holds load assignments and a self-weight multiplier. A case defines the analysis. A response combination combines case results. Set the self-weight multiplier explicitly. Pass `True` as the fourth argument to `LoadPatterns.Add` when you also need a matching linear static case. Keep the actual case names from the model for result queries. [CSI load pattern API](https://docs.csiamerica.com/help-files/etabs-api-2016/html/6197136d-8dbe-5c6d-5482-3187e859d726.htm)

## Analysis and result extraction

1. For a new model, set the units, build the geometry and loads, save to a relative session filename such as `model.edb`, and check `sap.Analyze.RunAnalysis()`. Before reading results, use `Analyze.GetCaseStatus(0, [], [])` and confirm that the required load cases have status `4` for finished. For an attached model, read the current units and use existing results for a read-only task. [CSI case status API](https://docs.csiamerica.com/help-files/etabs-api-2015/html/000caa8e-7ee1-dd75-efdf-db5e5a7d4250.htm)
2. For result methods, select the output with `sap.Results.Setup`. Use `DeselectAllCasesAndCombosForOutput()` followed by `SetCaseSelectedForOutput()` or `SetComboSelectedForOutput()`. Case selection changes the active output settings on an attached model.
3. Use `Results.BaseReact` for total base reactions, `Results.JointReact` for a joint reaction, `Results.JointDispl` for displacements, and `Results.FrameForce` for forces along a frame. Check the method signature in the ETABS OAPI help. Check the status and compare each returned array length with `NumberResults`.
4. Copy the selected units and all returned rows into Python values before the session closes. Keep the case or combination, step, object ID, and station where present. Treat zero rows as missing results when the view expects results. `FrameForce` can return more than two stations for one frame. The minimum-stations option in `SetOutputStations` sets a lower limit. Use the returned `NumberResults` when you read station rows. [CSI output stations API](https://docs.csiamerica.com/help-files/etabs-api-2016/html/12f2d632-8142-82b8-dc77-c0888935aa9f.htm)

[CSI result setup reference](https://docs.csiamerica.com/help-files/etabs-api-2016/html/8bbbf004-5565-5351-8009-d19f6bec5866.htm) · [CSI base reaction reference](https://docs.csiamerica.com/help-files/etabs-api-2016/html/b1b7816f-970b-afe9-c188-1b528722134a.htm)

## Database tables

- `GetTableForDisplayArray` returns `field_list, version, columns, count, cells, status`. Convert the flat cells into records using the returned columns. For results, use the database table case and combination selectors. Keep `OutputCase`, station, and step when present.
- For existing edits, `GetTableForEditingArray` returns `version, columns, count, cells, status`. Keep the rows and writable values that must remain. Stage the full set of rows in scope using the table version from the existing import or the editable read.
- Stage rows with `SetTableForEditingArray` and apply them with `ApplyEditedTables`. Pass the row count and a flat list of strings in field order. Check the CSI status and the import error counts. See the [table examples](examples.md).

### Steel shed geometry imports

The steel shed app imports point coordinates first, then applies each frame table separately. [Steel shed table code](https://github.com/viktor-platform/gh-copilot-sample-app-blog/blob/main/etabs_model.py)

| Table key | Fields used by the import |
| --- | --- |
| `Point Object Connectivity` | `UniqueName`, `X`, `Y`, `Z`, `IsSpecial` |
| `Column Object Connectivity` | `UniqueName`, `UniquePtI`, `UniquePtJ` |
| `Brace Object Connectivity` | `UniqueName`, `UniquePtI`, `UniquePtJ` |
| `Beam Object Connectivity` | `UniqueName`, `UniquePtI`, `UniquePtJ` |

For connectivity reads, match `UniquePtI` and `UniquePtJ` to `UniqueName` in the point table.

### Display tables in the ETABS Connect guide

| Table key | Common fields or results |
| --- | --- |
| `Frame Assignments - Summary` | `UniqueName`, `Type`, `AnalysisSect`, `DesignSect` |
| `Frame Assignments - Releases and Partial Fixity` | `UniqueName`, `PI`, `PJ`, `M2I`, `M2J`, `M3I`, `M3J` |
| `Joint Reactions` | `UniqueName`, `OutputCase`, `StepType`, `FX`, `FY`, `FZ`, `MX`, `MY`, `MZ` |
| `Joint Displacements` | `UniqueName`, `OutputCase`, `StepType`, `Ux`, `Uy`, `Uz`, `Rx`, `Ry`, `Rz` |
| `Element Forces - Beams` | `UniqueName`, `OutputCase`, `StepType`, `Station`, `P`, `V2`, `V3`, `T`, `M2`, `M3` |
| `Element Forces - Columns` | Column force results |
| `Element Forces - Braces` | Brace force results |

## Attached models, performance, and testing

See [units-and-worker.md](units-and-worker.md) for model units, attached sessions, timeouts, deferred calls, and file handling. Check the model state and units before writing to an open model. Catch `vkt.errors.WorkerSessionAttachError` before `vkt.errors.WorkerSessionError` and report how to reconnect.

Use `vkt.testing.mock_ETABSConnection` for both modes. Mock expected OAPI return shapes, status failures, and attach failures; a mock does not verify an actual CSI model.
