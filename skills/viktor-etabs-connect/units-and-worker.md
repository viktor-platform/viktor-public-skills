# ETABS Units and Worker Limits

## Use the present units

ETABS stores data in its database units. The API converts values to the model's present units as needed. Use `GetPresentUnits()` for the unit code to carry with coordinates and results. Use `GetDatabaseUnits()` only when you need the internal storage units. [CSI model API](https://docs.csiamerica.com/help-files/etabs-api-2016/html/15293a27-a035-e64b-a4b4-78356479aa98.htm)

- **New model with `connect()`**. Pass an explicit unit enum to `InitializeNewModel`, such as `vkt.etabs.eUnits.kN_m_C`. Use that unit system for coordinates, section dimensions, loads, and numeric geometry table cells. With `kN_mm_C`, enter a 6 m span as `6000`.
- **Open model with `attach()`**. For a viewer, read the present units and keep them with the data returned to the app. For a port, preserve the source app's unit setup. A source call to `SetPresentUnits` also changes the units shown in the attached ETABS window. [CSI present units](https://docs.csiamerica.com/help-files/etabs-api-2016/html/c4cad3c9-d648-a353-d37c-2bb4f57b4d71.htm) · [ETABS SDK unit enums](https://docs.viktor.ai/sdk/api/external/etabs/#eunits)

| Quantity | With `kN_m_C` | With `kN_mm_C` |
| --- | --- | --- |
| Point coordinates, section sizes, and frame stations | m | mm |
| Axial force `P` and shears `V2`, `V3` | kN | kN |
| Torsion `T` and bending moments `M2`, `M3` | kN·m | kN·mm |

Use object station `ObjSta` for distance from the beam object's I-end. Use element station `ElmSta` for distance from the analysis element's I-end. Label the plot, table, or export with the units of the returned values. Convert to the display units in one place before rendering. [CSI frame force results](https://docs.csiamerica.com/help-files/etabs-api-2016/html/87689f3e-4175-1627-618b-c4ebae5e89b5.htm)

```python
import viktor as vkt


def read_joint_coordinates(name: str) -> tuple[str, tuple[float, float, float]]:
    with vkt.etabs.attach(timeout=60) as sap:
        unit_code = int(sap.GetPresentUnits())
        if unit_code == 0:
            raise vkt.UserError("ETABS did not return the present units.")
        units = vkt.etabs.eUnits(unit_code)
        x, y, z, status = sap.PointObj.GetCoordCartesian(name, 0.0, 0.0, 0.0, "Global")
        if status != 0:
            raise vkt.UserError(f"ETABS could not read joint {name} (status {status}).")
        return units.name, (float(x), float(y), float(z))
```

## Worker limits

Declare `worker_integrations = ["etabsconnect"]` in `viktor.config.toml`. Use a Windows worker with ETABS installed and the license activated. Use VIKTOR Desktop on the engineer's machine for a personal worker.

| Operation | Worker behavior |
| --- | --- |
| `connect()` | Starts a fresh ETABS instance for the session. Use this mode to initialize or build a model. |
| `attach()` | Uses ETABS on the same Windows machine as the personal worker. Keep one ETABS instance open. The app cannot select among several windows. The instance stays open when the session ends. |
| Save a session model | Use a relative filename such as `model.edb`. The worker rejects absolute paths and writes within a temporary session folder, which it removes after the session. The wrapper cannot return the `.edb` to the app. |
| Analyze an attached untitled model | Call `File.Save` with a relative filename before `RunAnalysis`. ETABS uses that temporary file path for the analysis. The engineer can save a permanent copy in ETABS. |
| Read results | Read geometry, tables, and results while the `with` block is open. Copy the values into plain Python data before using them in views, calculations, or downloads. |
| Timeouts | `timeout` applies to each call or group of deferred calls. In `attach()` it also bounds the bind. Allow at least 30 seconds for the full bind window. |

In SDK 14.37.0 and later, deferred calls are enabled by default. Read a returned value to resolve it. Keep the source order of calls and status checks during a port. If a session is lost, open a new one and check the model state before retrying a write. [VIKTOR ETABS SDK](https://docs.viktor.ai/sdk/api/external/etabs/) · [VIKTOR worker setup and file limits](https://docs.viktor.ai/docs/create-apps/software-integrations/etabs-and-sap2000/)

### Attach errors

Catch `WorkerSessionAttachError` around the `with` block and read `error.reason`. For `error_attach_no_instance`, ask the engineer to open the model. For `no_worker_online`, check VIKTOR Desktop. For `error_session_mode_not_supported`, check for a worker update. Use a general attach error message for other reasons. [VIKTOR worker errors](https://docs.viktor.ai/sdk/api/errors/#workersessionattacherror)
