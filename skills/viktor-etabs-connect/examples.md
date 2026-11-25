# ETABS Connect Examples

## Start a fresh model

```python
import viktor as vkt


def check(ret, operation):
    if ret != 0:
        raise vkt.UserError(f"ETABS failed: {operation} ({ret})")


def create_member():
    with vkt.etabs.connect(timeout=60) as sap:
        check(sap.InitializeNewModel(vkt.etabs.eUnits.kN_m_C), "InitializeNewModel")
        check(sap.File.NewBlank(), "File.NewBlank")
        [name, ret] = sap.FrameObj.AddByCoord(0, 0, 0, 6, 0, 0, "", "Default", "B1")
        check(ret, "FrameObj.AddByCoord")
        return str(name)
```

### Create a beam with database tables

Create a six-metre beam at the first story of a new grid model. Apply `Point Object Connectivity` first so both joints exist when you apply `Beam Object Connectivity`. Use `check()` from the example above and pass the table versions from the source import.

```python
from typing import Any


def import_table(
    sap: Any, key: str, version: int, fields: list[str], rows: list[tuple[str, ...]],
) -> None:
    database = sap.DatabaseTables
    check(database.CancelTableEditing(), "Clear table edits")
    cells = [cell for row in rows for cell in row]
    _, _, _, status = database.SetTableForEditingArray(key, version, fields, len(rows), cells)
    check(status, f"Stage {key}")
    fatal, errors, _, _, log, status = database.ApplyEditedTables(True, 0, 0, 0, 0, "")
    if status != 0 or fatal or errors:
        raise vkt.UserError(f"Import failed for {key} (status {status}). {str(log)[-500:]}")


def create_member_with_tables(point_table_version: int, beam_table_version: int) -> str:
    start, end, beam = "900001", "900002", "910001"
    with vkt.etabs.connect(timeout=60) as sap:
        check(sap.InitializeNewModel(vkt.etabs.eUnits.kN_m_C), "Initialize model")
        check(sap.File.NewGridOnly(1, 3, 3, 2, 2, 6, 4), "Create grid model")
        import_table(
            sap, "Point Object Connectivity", point_table_version,
            ["UniqueName", "X", "Y", "Z", "IsSpecial"],
            [(start, "0", "0", "3", "Yes"), (end, "6", "0", "3", "Yes")],
        )
        import_table(
            sap, "Beam Object Connectivity", beam_table_version,
            ["UniqueName", "UniquePtI", "UniquePtJ"], [(beam, start, end)],
        )
        point_i, point_j, status = sap.FrameObj.GetPoints(beam, "", "")
        check(status, "Read beam endpoints")
        if {str(point_i), str(point_j)} != {start, end}:
            raise vkt.UserError("ETABS imported the beam with unexpected endpoints.")
        return beam
```

## Work with an open model

```python
import viktor as vkt


def read_frame_points(frame_name: str) -> tuple[str, str]:
    try:
        with vkt.etabs.attach(timeout=60) as sap:
            point_i, point_j, ret = sap.FrameObj.GetPoints(frame_name, "", "")
            if ret != 0:
                raise vkt.UserError(f"ETABS could not read frame {frame_name} ({ret}).")
            return str(point_i), str(point_j)
    except vkt.errors.WorkerSessionAttachError as error:
        raise vkt.UserError("Open the ETABS model and start its personal worker, then try again.") from error
```

For a beam and column design app, read frame geometry and results in the attached session. Preserve load-case and unit labels for the design calculations. Do not assume the attached model is blank.

## Read support reactions and coordinates with `attach()`

The Footing Inputs app reads `Joint Reactions` and `Point Object Connectivity` in one session and joins them by `UniqueName`. This example selects one case or combination and returns the model's current unit code with the records. Use `check()` from the first example.

```python
from typing import Any


def read_table(sap: Any, key: str) -> list[dict[str, str]]:
    _, _, columns, count, cells, status = sap.DatabaseTables.GetTableForDisplayArray(
        key, [""], "", 0, [], 0, [],
    )
    check(status, f"Read {key}")
    fields = list(columns or [])
    values = ["" if cell is None else str(cell) for cell in cells or []]
    width = len(fields)
    if not width or len(values) != int(count) * width:
        raise vkt.UserError(f"ETABS returned incomplete data for {key}.")
    return [
        dict(zip(fields, values[start:start + width], strict=True))
        for start in range(0, len(values), width)
    ]


def read_support_reactions(output_name: str, *, combination: bool) -> tuple[int, list[dict[str, str]]]:
    with vkt.etabs.attach(timeout=120) as sap:
        database = sap.DatabaseTables
        _, status = database.SetLoadCasesSelectedForDisplay([] if combination else [output_name])
        check(status, "Select table load cases")
        _, status = database.SetLoadCombinationsSelectedForDisplay([output_name] if combination else [])
        check(status, "Select table combinations")
        units = int(sap.GetPresentUnits())
        coordinates = {
            row["UniqueName"]: {field: row[field] for field in ("X", "Y", "Z")}
            for row in read_table(sap, "Point Object Connectivity")
        }
        rows = []
        for reaction in read_table(sap, "Joint Reactions"):
            if reaction["OutputCase"] == output_name:
                point = coordinates.get(reaction["UniqueName"])
                if point is None:
                    raise vkt.UserError(f"Missing coordinates for point {reaction['UniqueName']}.")
                rows.append(reaction | point)
        return units, rows
```

## Import geometry tables with `connect()`

This migration example uses the steel shed's import fields and order with a fresh VIKTOR session. Reuse `import_table()` and `read_table()` from the examples above. Use the table versions from the source import. Keep each frame table in its own apply call. [Steel shed table code](https://github.com/viktor-platform/gh-copilot-sample-app-blog/blob/main/etabs_model.py)

```python
def import_portal(table_versions: dict[str, int]) -> list[dict[str, str]]:
    point_fields = ["UniqueName", "X", "Y", "Z", "IsSpecial"]
    frame_fields = ["UniqueName", "UniquePtI", "UniquePtJ"]
    points = [
        ("900001", "0", "0", "0", "Yes"),
        ("900002", "0", "0", "3", "Yes"),
        ("900003", "4", "0", "3", "Yes"),
        ("900004", "4", "0", "0", "Yes"),
    ]
    tables = [
        ("Point Object Connectivity", point_fields, points),
        ("Column Object Connectivity", frame_fields, [
            ("910001", "900001", "900002"), ("910002", "900004", "900003"),
        ]),
        ("Brace Object Connectivity", frame_fields, [("910003", "900001", "900003")]),
        ("Beam Object Connectivity", frame_fields, [("910004", "900002", "900003")]),
    ]
    with vkt.etabs.connect(timeout=120) as sap:
        check(sap.InitializeNewModel(vkt.etabs.eUnits.kN_m_C), "Initialize model")
        check(sap.File.NewGridOnly(1, 3, 3, 2, 2, 4, 4), "Create grid model")
        for key, fields, rows in tables:
            import_table(sap, key, table_versions[key], fields, rows)
        return read_table(sap, "Point Object Connectivity")
```

Read back the member IDs and endpoints before assigning sections, releases, or loads. This example shows the migration pattern and needs a live worker check for the target ETABS version.

## Read beam forces by station

The ETABS RC Beam and Column Designer calls `Results.FrameForce` in an ETABS `attach()` session. It keeps the object station (`ObjSta`) for the position along the beam and the element station (`ElmSta`) for the position along the analysis element. It keeps each station's force components, combination, and step together. The app can reduce displayed rows per beam and combination by prioritizing end stations and force extrema.

This example reads the force rows for one beam and combination. `beam_name` is the ETABS frame unique name. Station distances and force values use the returned model units.

```python
def read_beam_forces(beam_name: str, combination: str) -> tuple[int, list[dict[str, str | float]]]:
    fields = (
        "frame", "station", "element", "element_station", "combination", "step_type", "step_num",
        "P", "V2", "V3", "T", "M2", "M3",
    )
    with vkt.etabs.attach(timeout=120) as sap:
        units = int(sap.GetPresentUnits())
        setup = sap.Results.Setup
        check(setup.DeselectAllCasesAndCombosForOutput(), "Clear ETABS result selection")
        check(setup.SetComboSelectedForOutput(combination, True), "Select combination")
        count, *columns, status = sap.Results.FrameForce(
            beam_name, vkt.etabs.eItemTypeElm.ObjectElm, 0, *[[] for _ in fields],
        )
        check(status, "Read beam forces")
        if not int(count):
            raise vkt.UserError("Run the analysis in ETABS and check that the combination has results.")
        if len(columns) != len(fields) or any(len(column) != int(count) for column in columns):
            raise vkt.UserError("ETABS returned incomplete beam force data.")
        rows = [dict(zip(fields, row, strict=True)) for row in zip(*columns, strict=True)]
        return units, sorted(rows, key=lambda row: (row["station"], row["step_type"], row["step_num"]))
```

## 🏗️ 3D stick model and torsion releases

This complete editor app uses `vkt.etabs.attach()` to read an open model. It joins point, beam, column, and release tables by ETABS object ID and plots an interactive 3D stick model. Hover over a member to see the T, M2, and M3 release flags for both ends.

- 🟦 Blue-grey lines show members with neither torsion end released.
- 🟠 Orange lines show members with a torsion release at either end.
- 🟣 Magenta lines and 🟡 yellow joint markers identify joints where at least two beam or column ends meet and every such end has T, M2, and M3 releases. The **Flagged joints** tab lists these ends.

Copy [app.py](examples/stick-model-viewer/app.py), [requirements.txt](examples/stick-model-viewer/requirements.txt), and [viktor.config.toml](examples/stick-model-viewer/viktor.config.toml) into the same app folder. The config uses `app_type = "editor"`, `python_version = "3.12"`, and `worker_integrations = ["etabsconnect"]`.

Open the model in ETABS and start the ETABS personal worker in VIKTOR Desktop. If you need a new development app, create it from the app folder. Use the registered name the CLI returns in `viktor.config.toml`.

```bash
viktor-cli create-app "ETABS stick model viewer" --registered-name etabs-stick-model-viewer
viktor-cli install
viktor-cli start
```

Open the URL printed by the CLI. Update the **3D stick model** or **Flagged joints** view to read the current ETABS tables. Use the display options to control the highlighted members in the plot. Coordinates use the model's current units. See the [units and worker guide](units-and-worker.md).
