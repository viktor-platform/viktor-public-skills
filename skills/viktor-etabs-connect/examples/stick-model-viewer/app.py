import logging
from collections import defaultdict
from typing import Any, TypedDict

import plotly.graph_objects as go
import viktor as vkt
from viktor.errors import ExecutionError, InternalError

logger = logging.getLogger("viktor")

TableRow = dict[str, str]
PointCoordinates = dict[str, float]


class ModelTables(TypedDict):
    points: list[TableRow]
    beams: list[TableRow]
    columns: list[TableRow]
    releases: list[TableRow]


class ViewerData(TypedDict):
    node_map: dict[str, PointCoordinates]
    default_members: list[TableRow]
    torsion_members: list[TableRow]
    all_members: list[TableRow]
    flagged_joint_names: set[str]
    flagged_table_rows: list[TableRow]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check(ret: int, operation: str) -> None:
    """Raise a UserError when an ETABS OAPI call returns a non-zero status."""
    code = int(ret)
    if code:
        raise vkt.UserError(f"ETABS call failed [{operation}], return code={code}")


def _fetch_table(
    sap: Any, table_key: str, *, optional: bool = False
) -> tuple[list[str], list[list[str]]]:
    logger.info("📋 Reading ETABS table %s", table_key)
    _, _, raw_columns, raw_count, raw_cells, ret = (
        sap.DatabaseTables.GetTableForDisplayArray(
            table_key,
            [""],
            "",
            0,
            [],
            0,
            [],
        )
    )
    if optional and int(ret) == vkt.etabs.eReturnCode.TableDoesNotExist:
        return [], []
    _check(ret, f"Read {table_key}")

    columns = list(raw_columns or [])
    count = int(raw_count)
    if count == 0:
        return columns, []

    data = ["" if value is None else str(value) for value in raw_cells or []]
    n_cols = len(columns)
    if not n_cols or len(data) != count * n_cols:
        raise vkt.UserError(f"ETABS returned incomplete rows for {table_key}.")
    rows = [data[i : i + n_cols] for i in range(0, len(data), n_cols)]
    logger.info("✅ Read %s rows from %s", count, table_key)
    return columns, rows


def _to_records(columns: list[str], rows: list[list[str]]) -> list[TableRow]:
    """Convert parallel columns + rows into a list of dicts."""
    return [dict(zip(columns, row, strict=True)) for row in rows]


# ---------------------------------------------------------------------------
# Core data-retrieval function (runs inside the ETABS session)
# ---------------------------------------------------------------------------


def _retrieve_model_data(sap: Any) -> ModelTables:
    """
    Retrieve all required tables from the attached ETABS model and return a
    structured dict with points, beams, columns, and release data.
    """
    # --- Points ---
    pt_cols, pt_rows = _fetch_table(sap, "Point Object Connectivity")
    points = _to_records(pt_cols, pt_rows)
    logger.info(f"🔵 Points loaded: {len(points)}")

    # --- Beams ---
    bm_cols, bm_rows = _fetch_table(sap, "Beam Object Connectivity", optional=True)
    beams = _to_records(bm_cols, bm_rows)
    logger.info(f"🟢 Beams loaded: {len(beams)}")

    # --- Columns ---
    col_cols, col_rows = _fetch_table(sap, "Column Object Connectivity", optional=True)
    columns_data = _to_records(col_cols, col_rows)
    logger.info(f"🟡 Columns loaded: {len(columns_data)}")

    # --- Frame Assignments - Releases and Partial Fixity ---
    rel_cols, rel_rows = _fetch_table(
        sap,
        "Frame Assignments - Releases and Partial Fixity",
        optional=True,
    )
    releases = _to_records(rel_cols, rel_rows)
    logger.info(f"🔴 Release records loaded: {len(releases)}")

    return {
        "points": points,
        "beams": beams,
        "columns": columns_data,
        "releases": releases,
    }


# ---------------------------------------------------------------------------
# Analysis / post-processing (pure Python, no ETABS session needed)
# ---------------------------------------------------------------------------


def _build_node_map(points: list[TableRow]) -> dict[str, PointCoordinates]:
    """Build a dict keyed by UniqueName → point record (with X, Y, Z as floats)."""
    node_map: dict[str, PointCoordinates] = {}
    for p in points:
        try:
            node_map[str(p["UniqueName"])] = {
                "X": float(p["X"]),
                "Y": float(p["Y"]),
                "Z": float(p["Z"]),
            }
        except (KeyError, ValueError):
            logger.warning("⚠️ Skipping point with missing or invalid coordinates")
    return node_map


def _build_release_map(releases: list[TableRow]) -> dict[str, TableRow]:
    """Build a dict keyed by member UniqueName → release flags dict."""
    return {str(r["UniqueName"]): r for r in releases if "UniqueName" in r}


def _is_yes(value: str) -> bool:
    """Return True when an ETABS Yes/No flag is affirmative."""
    return str(value).strip().lower() in ("yes", "true", "1")


def _classify_members(
    beams: list[TableRow],
    columns_data: list[TableRow],
    release_map: dict[str, TableRow],
) -> tuple[list[TableRow], list[TableRow], list[TableRow]]:
    """Join beam and column records to their release flags."""
    all_members = [dict(member) for member in [*beams, *columns_data]]
    default_members: list[TableRow] = []
    torsion_members: list[TableRow] = []

    for m in all_members:
        uid = str(m.get("UniqueName", ""))
        rel = release_map.get(uid, {})

        # Attach release flags to the member record for hover tooltips
        m["TI"] = rel.get("TI", "No")
        m["TJ"] = rel.get("TJ", "No")
        m["M2I"] = rel.get("M2I", "No")
        m["M2J"] = rel.get("M2J", "No")
        m["M3I"] = rel.get("M3I", "No")
        m["M3J"] = rel.get("M3J", "No")

        has_torsion = _is_yes(m["TI"]) or _is_yes(m["TJ"])
        if has_torsion:
            torsion_members.append(m)
        else:
            default_members.append(m)

    logger.info(
        f"📊 Member classification — default: {len(default_members)}, "
        f"torsion-released: {len(torsion_members)}"
    )
    return default_members, torsion_members, all_members


def _find_flagged_joints(
    all_members: list[TableRow],
) -> tuple[set[str], list[TableRow]]:
    """
    Identify joints where all connected beam and column ends have T, M2, and M3 releases.

    A joint qualifies when:
      1. It has ≥ 2 member ends connected to it.
      2. Every single end connected to it has TI/TJ, M2I/M2J, M3I/M3J all "Yes".

    Returns:
      flagged_joint_names : set of joint UniqueName strings
      flagged_table_rows  : list of dicts for the output table
    """
    # Map joint → list of (member_uid, end_label, T, M2, M3)
    joint_ends: dict[str, list[TableRow]] = defaultdict(list)

    for m in all_members:
        uid = str(m.get("UniqueName", ""))
        pt_i = str(m.get("UniquePtI", ""))
        pt_j = str(m.get("UniquePtJ", ""))

        if pt_i:
            joint_ends[pt_i].append(
                {
                    "member": uid,
                    "end": "I",
                    "T": m.get("TI", "No"),
                    "M2": m.get("M2I", "No"),
                    "M3": m.get("M3I", "No"),
                }
            )
        if pt_j:
            joint_ends[pt_j].append(
                {
                    "member": uid,
                    "end": "J",
                    "T": m.get("TJ", "No"),
                    "M2": m.get("M2J", "No"),
                    "M3": m.get("M3J", "No"),
                }
            )

    flagged_joint_names: set[str] = set()
    flagged_table_rows: list[TableRow] = []

    for joint_name, ends in joint_ends.items():
        if len(ends) < 2:
            continue  # need at least 2 ends

        # Every end must be fully released in T, M2, M3
        all_fully_released = all(
            _is_yes(e["T"]) and _is_yes(e["M2"]) and _is_yes(e["M3"]) for e in ends
        )
        if all_fully_released:
            flagged_joint_names.add(joint_name)
            for e in ends:
                flagged_table_rows.append(
                    {
                        "Joint": joint_name,
                        "Member": e["member"],
                        "End": e["end"],
                        "Releases": "T, M2, M3",
                    }
                )

    logger.info(f"🚨 Flagged joints (fully released): {len(flagged_joint_names)}")
    return flagged_joint_names, flagged_table_rows


# ---------------------------------------------------------------------------
# Plotly figure builder
# ---------------------------------------------------------------------------

# Colour palette
_COL_DEFAULT = "rgb(100, 140, 200)"  # blue-grey  — normal members
_COL_TORSION = "rgb(230, 100, 30)"  # orange     — torsion-released members
_COL_FLAGGED = "rgb(200, 0, 200)"  # magenta    — members at flagged joints
_COL_NODE_DEF = "rgb(160, 160, 160)"  # grey       — normal joints
_COL_NODE_FLG = "rgb(255, 220, 0)"  # yellow     — flagged joints


def _member_traces(
    members: list[TableRow],
    node_map: dict[str, PointCoordinates],
    color: str,
    name: str,
    flagged_joint_names: set[str],
    show_flagged_override: bool = False,
) -> list[go.Scatter3d]:
    """
    Build one Scatter3d trace per member category.  Members that connect to a
    flagged joint are promoted to the magenta category when show_flagged_override
    is False (they are handled separately).

    Returns a list of Scatter3d traces (one per category).
    """
    xs, ys, zs, texts = [], [], [], []

    for m in members:
        uid = str(m.get("UniqueName", "?"))
        pt_i = str(m.get("UniquePtI", ""))
        pt_j = str(m.get("UniquePtJ", ""))

        if pt_i not in node_map or pt_j not in node_map:
            logger.warning(f"⚠️ Member {uid}: endpoint(s) not in node map — skipping")
            continue

        # Skip members that belong to the flagged-joint category unless we are
        # explicitly building that category.
        at_flagged = pt_i in flagged_joint_names or pt_j in flagged_joint_names
        if at_flagged and not show_flagged_override:
            continue

        ni, nj = node_map[pt_i], node_map[pt_j]
        # Plotly line segments: separate with None to avoid connecting them
        xs += [ni["X"], nj["X"], None]
        ys += [ni["Y"], nj["Y"], None]
        zs += [ni["Z"], nj["Z"], None]
        details = (
            f"<b>{uid}</b><br>"
            f"TI={m.get('TI', '?')} TJ={m.get('TJ', '?')}<br>"
            f"M2I={m.get('M2I', '?')} M2J={m.get('M2J', '?')}<br>"
            f"M3I={m.get('M3I', '?')} M3J={m.get('M3J', '?')}"
        )
        texts += [details, details, None]

    if not xs:
        return []

    return [
        go.Scatter3d(
            x=xs,
            y=ys,
            z=zs,
            mode="lines",
            line={"color": color, "width": 3},
            name=name,
            hovertext=texts,
            hoverinfo="text",
        )
    ]


def _flagged_member_traces(
    all_members: list[TableRow],
    node_map: dict[str, PointCoordinates],
    flagged_joint_names: set[str],
) -> list[go.Scatter3d]:
    """Build the magenta trace for members connected to flagged joints."""
    flagged_members = [
        m
        for m in all_members
        if str(m.get("UniquePtI", "")) in flagged_joint_names
        or str(m.get("UniquePtJ", "")) in flagged_joint_names
    ]
    return _member_traces(
        flagged_members,
        node_map,
        _COL_FLAGGED,
        "Members at flagged joints",
        flagged_joint_names,
        show_flagged_override=True,
    )


def _joint_traces(
    node_map: dict[str, PointCoordinates],
    flagged_joint_names: set[str],
) -> list[go.Scatter3d]:
    """Build two joint scatter traces: normal and flagged."""
    traces = []

    def _scatter(pts, color, size, name):
        if not pts:
            return
        xs = [p["X"] for p in pts]
        ys = [p["Y"] for p in pts]
        zs = [p["Z"] for p in pts]
        labels = [p["label"] for p in pts]
        traces.append(
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="markers",
                marker={"color": color, "size": size, "symbol": "circle"},
                name=name,
                hovertext=labels,
                hoverinfo="text",
            )
        )

    normal_pts, flagged_pts = [], []
    for uid, coords in node_map.items():
        entry = {
            **coords,
            "label": (
                f"<b>{uid}</b><br>"
                f"X={coords['X']:.3f}  Y={coords['Y']:.3f}  Z={coords['Z']:.3f}"
            ),
        }
        if uid in flagged_joint_names:
            flagged_pts.append(entry)
        else:
            normal_pts.append(entry)

    _scatter(normal_pts, _COL_NODE_DEF, 3, "Joints")
    _scatter(flagged_pts, _COL_NODE_FLG, 8, "Flagged joints (fully released)")
    return traces


def _build_figure(
    node_map: dict[str, PointCoordinates],
    default_members: list[TableRow],
    torsion_members: list[TableRow],
    all_members: list[TableRow],
    flagged_joint_names: set[str],
) -> go.Figure:
    """Assemble the complete 3D Plotly figure."""
    traces: list[go.Scatter3d] = []

    # 1. Default members (excluding those at flagged joints)
    traces += _member_traces(
        default_members,
        node_map,
        _COL_DEFAULT,
        "Default members",
        flagged_joint_names,
    )
    # 2. Torsion-released members (excluding those at flagged joints)
    traces += _member_traces(
        torsion_members,
        node_map,
        _COL_TORSION,
        "Torsion-released members",
        flagged_joint_names,
    )
    # 3. Members at flagged joints (magenta, highest priority)
    traces += _flagged_member_traces(all_members, node_map, flagged_joint_names)

    # 4. Joint markers
    traces += _joint_traces(node_map, flagged_joint_names)

    fig = go.Figure(data=traces)
    fig.update_layout(
        title="🏗️ ETABS 3D stick model and torsion releases",
        scene={
            "xaxis": {"title": {"text": "X"}},
            "yaxis": {"title": {"text": "Y"}},
            "zaxis": {"title": {"text": "Z"}},
            "aspectmode": "data",
        },
        legend={"x": 0.01, "y": 0.99, "bgcolor": "rgba(255,255,255,0.8)"},
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
        paper_bgcolor="white",
    )
    return fig


# ---------------------------------------------------------------------------
# Parametrization
# ---------------------------------------------------------------------------


class Parametrization(vkt.Parametrization):
    """Controls for the ETABS stick model viewer."""

    connection = vkt.Section("🔌 ETABS connection")
    connection.timeout = vkt.IntegerField(
        "Timeout per call",
        default=60,
        min=10,
        max=300,
        suffix="s",
        description="Maximum seconds allowed for a single ETABS OAPI call.",
    )

    display = vkt.Section("🎨 Display options")
    display.show_default = vkt.BooleanField(
        "Show default members",
        default=True,
        description="Toggle visibility of members with no torsion release.",
    )
    display.show_torsion = vkt.BooleanField(
        "Show torsion-released members",
        default=True,
        description="Toggle visibility of members with TI or TJ released.",
    )
    display.show_flagged = vkt.BooleanField(
        "Show flagged-joint members",
        default=True,
        description="Toggle visibility of members connected to fully-released joints.",
    )


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class Controller(vkt.Controller):
    """ETABS 3D Stick Model Viewer with Torsion Release Highlighting."""

    parametrization = Parametrization

    # ------------------------------------------------------------------
    # Shared data-retrieval helper (called by both views)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_model_data(params: Any) -> ViewerData:
        """
        Attach to the running ETABS instance, fetch all required tables, and
        return a dict with processed model data ready for visualisation.
        """
        timeout = int(params.connection.timeout)

        try:
            with vkt.etabs.attach(timeout=timeout) as sap:
                raw = _retrieve_model_data(sap)
        except vkt.errors.WorkerSessionAttachError as exc:
            raise vkt.UserError(
                f"Could not attach to ETABS ({exc.reason}). "
                "Please open your model in ETABS and try again."
            ) from exc
        except vkt.errors.WorkerSessionError as exc:
            raise vkt.UserError(
                "The ETABS session was lost. Reopen your model and try again."
            ) from exc
        except (ConnectionError, ExecutionError, InternalError, TimeoutError) as exc:
            raise vkt.UserError(f"ETABS Connect failed: {exc}") from exc

        # Post-process outside the session
        node_map = _build_node_map(raw["points"])
        release_map = _build_release_map(raw["releases"])
        default_members, torsion_members, all_members = _classify_members(
            raw["beams"], raw["columns"], release_map
        )
        flagged_joint_names, flagged_table_rows = _find_flagged_joints(all_members)

        return {
            "node_map": node_map,
            "default_members": default_members,
            "torsion_members": torsion_members,
            "all_members": all_members,
            "flagged_joint_names": flagged_joint_names,
            "flagged_table_rows": flagged_table_rows,
        }

    # ------------------------------------------------------------------
    # View 1: 3D Plotly stick model
    # ------------------------------------------------------------------

    @vkt.PlotlyView("🏗️ 3D stick model", duration_guess=15)
    def view_3d_model(self, params, **kwargs):
        """
        Render the ETABS stick model as an interactive 3D Plotly figure.
        Members are colour-coded by release status; flagged joints are
        highlighted with large yellow markers.
        """
        data = self._get_model_data(params)

        node_map = data["node_map"]
        all_members = data["all_members"]
        flagged_joint_names = data["flagged_joint_names"]

        # Apply display toggles
        default_members = data["default_members"] if params.display.show_default else []
        torsion_members = data["torsion_members"] if params.display.show_torsion else []
        if not params.display.show_flagged:
            flagged_joint_names = set()  # suppress flagged rendering

        fig = _build_figure(
            node_map, default_members, torsion_members, all_members, flagged_joint_names
        )
        return vkt.PlotlyResult(fig)

    # ------------------------------------------------------------------
    # View 2: Flagged joints table
    # ------------------------------------------------------------------

    @vkt.TableView("⚠️ Flagged joints", duration_guess=15)
    def view_flagged_joints(self, params, **kwargs):
        """
        List joints where all connected beam and column ends have torsion (T),
        moment-2 (M2), and moment-3 (M3) releases.
        """
        data = self._get_model_data(params)
        rows = data["flagged_table_rows"]

        if not rows:
            # Return an informative single-row table when nothing is flagged
            return vkt.TableResult(
                [["—", "—", "—", "No fully-released joints found"]],
                column_headers=[
                    vkt.TableHeader("Joint", align="left"),
                    vkt.TableHeader("Member", align="left"),
                    vkt.TableHeader("End", align="left"),
                    vkt.TableHeader("Releases", align="left"),
                ],
            )

        table_data = [[r["Joint"], r["Member"], r["End"], r["Releases"]] for r in rows]
        return vkt.TableResult(
            table_data,
            column_headers=[
                vkt.TableHeader("Joint", align="left"),
                vkt.TableHeader("Member", align="left"),
                vkt.TableHeader("End", align="left"),
                vkt.TableHeader("Releases", align="left"),
            ],
        )
