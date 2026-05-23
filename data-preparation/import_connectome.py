from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


CHEMICAL_SEND_TYPES = {"S", "Sp"}
CHEMICAL_RECEIVE_TYPES = {"R", "Rp"}
VENTRAL_CORD_CLASS_SEGMENTS = {
    "AS": 11,
    "DA": 9,
    "DB": 7,
    "DD": 6,
    "VA": 12,
    "VB": 11,
    "VC": 6,
    "VD": 13,
}
HEAD_CLASSES = {
    "ADA",
    "ADE",
    "ADF",
    "ADL",
    "AFD",
    "AIA",
    "AIB",
    "AIM",
    "AIN",
    "AIY",
    "AIZ",
    "ALA",
    "AQR",
    "ASE",
    "ASG",
    "ASH",
    "ASI",
    "ASJ",
    "ASK",
    "AUA",
    "AVA",
    "AVB",
    "AVD",
    "AVE",
    "AVF",
    "AVG",
    "AVH",
    "AVJ",
    "AVK",
    "AVL",
    "AWA",
    "AWB",
    "AWC",
    "BAG",
    "BDU",
    "CEP",
    "FLP",
    "IL1",
    "IL2",
    "OLL",
    "OLQ",
    "RIA",
    "RIB",
    "RIC",
    "RID",
    "RIF",
    "RIG",
    "RIH",
    "RIM",
    "RIP",
    "RIR",
    "RIS",
    "RIV",
    "RMD",
    "RME",
    "RMF",
    "RMG",
    "RMH",
    "SAA",
    "SAB",
    "SIA",
    "SIB",
    "SMB",
    "SMD",
    "URA",
    "URB",
    "URX",
    "URY",
}
TAIL_CLASSES = {
    "DVA",
    "DVB",
    "DVC",
    "LUA",
    "PDA",
    "PDB",
    "PDE",
    "PHA",
    "PHB",
    "PHC",
    "PLM",
    "PLN",
    "PQR",
    "PVC",
    "PVD",
    "PVM",
    "PVN",
    "PVP",
    "PVQ",
    "PVR",
    "PVT",
    "PVW",
}


@dataclass(frozen=True)
class CellMetadata:
    cell_type: str = ""
    cell_category: str = ""
    notes: str = ""
    source: str = ""


@dataclass(frozen=True)
class RawConnection:
    row_number: int
    neuron1: str
    neuron2: str
    connection_type: str
    weight: int
    normalized_neuron1: str
    normalized_neuron2: str


@dataclass
class EdgeAccumulator:
    source: str
    target: str
    kind: str
    directed: bool
    components: Counter[str] = field(default_factory=Counter)
    receive_components: Counter[str] = field(default_factory=Counter)
    row_numbers: list[int] = field(default_factory=list)
    receive_row_numbers: list[int] = field(default_factory=list)

    @property
    def weight(self) -> int:
        return int(sum(self.components.values()))

    @property
    def row_count(self) -> int:
        return len(self.row_numbers) + len(self.receive_row_numbers)


def normalize_cell_id(value: str) -> str:
    return value.strip().upper()


def parse_weight(value: str) -> int:
    weight = int(float(str(value).strip()))
    if weight < 0:
        raise ValueError(f"connection weight cannot be negative: {value}")
    return weight


def read_csv(path: Path) -> list[RawConnection]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required_fields = {"Neuron 1", "Neuron 2", "Type", "Nbr"}
        missing = required_fields - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is missing required columns: {sorted(missing)}")

        rows = []
        for row_number, row in enumerate(reader, start=2):
            neuron1 = str(row["Neuron 1"]).strip()
            neuron2 = str(row["Neuron 2"]).strip()
            connection_type = str(row["Type"]).strip()
            weight = parse_weight(str(row["Nbr"]))
            if not neuron1 or not neuron2 or not connection_type:
                raise ValueError(f"blank cell in row {row_number}: {row}")

            rows.append(
                RawConnection(
                    row_number=row_number,
                    neuron1=neuron1,
                    neuron2=neuron2,
                    connection_type=connection_type,
                    weight=weight,
                    normalized_neuron1=normalize_cell_id(neuron1),
                    normalized_neuron2=normalize_cell_id(neuron2),
                )
            )

    return rows


def infer_neuron_class(cell_id: str) -> str:
    if cell_id == "NMJ":
        return "NMJ"
    if re.search(r"\d+$", cell_id):
        return re.sub(r"\d+$", "", cell_id)
    if cell_id.endswith(("L", "R", "D", "V")) and len(cell_id) > 3:
        return cell_id[:-1]
    return cell_id


def infer_side(cell_id: str) -> str:
    if cell_id.endswith("L"):
        return "L"
    if cell_id.endswith("R"):
        return "R"
    if cell_id.endswith("D"):
        return "D"
    if cell_id.endswith("V"):
        return "V"
    return ""


def infer_segment(cell_id: str) -> int:
    match = re.search(r"(\d+)$", cell_id)
    if not match:
        return -1
    return int(match.group(1))


def node_kind(cell_id: str) -> str:
    if cell_id == "NMJ":
        return "muscle_output"
    return "neuron"


def load_cell_metadata(directory: Path | None) -> dict[str, CellMetadata]:
    if directory is None or not directory.exists():
        return {}

    metadata: dict[str, CellMetadata] = {}
    for csv_path in sorted(directory.glob("*.csv")):
        with csv_path.open(newline="", encoding="utf-8-sig") as file:
            for row in csv.reader(file):
                if not row:
                    continue

                cell_id = normalize_cell_id(row[0])
                if not cell_id or cell_id in {"CELL", "CELL NAME"}:
                    continue

                cell_type = row[1].strip() if len(row) > 1 and row[1] else ""
                if cell_type.lower() == "cell type":
                    continue

                metadata[cell_id] = CellMetadata(
                    cell_type=cell_type,
                    cell_category=row[2].strip() if len(row) > 2 and row[2] else "",
                    notes=row[3].strip() if len(row) > 3 and row[3] else "",
                    source=csv_path.name,
                )

    return metadata


def side_offsets(cell_id: str, neuron_class: str) -> tuple[float, float]:
    y = 0.0
    z = 0.0

    if "DD" in cell_id or neuron_class in {"DA", "DB", "DD", "AS"}:
        y = 0.22
    if "VD" in cell_id or neuron_class in {"VA", "VB", "VC", "VD"}:
        y = -0.22

    if cell_id.endswith("DL") or cell_id.endswith("DR"):
        y = 0.32
    elif cell_id.endswith("VL") or cell_id.endswith("VR"):
        y = -0.32
    elif cell_id.endswith("D"):
        y = 0.32
    elif cell_id.endswith("V"):
        y = -0.32

    if cell_id.endswith("L"):
        z = -0.34
    elif cell_id.endswith("R"):
        z = 0.34

    return y, z


def ventral_cord_fraction(neuron_class: str, segment: int) -> float:
    max_segment = VENTRAL_CORD_CLASS_SEGMENTS.get(neuron_class, max(segment, 1))
    clamped_segment = min(max(segment, 1), max_segment)
    return 0.14 + 0.78 * ((clamped_segment - 0.5) / max_segment)


def infer_body_fraction(cell_id: str, neuron_class: str, segment: int, metadata: CellMetadata) -> float:
    if cell_id == "NMJ":
        return 0.55

    if neuron_class in VENTRAL_CORD_CLASS_SEGMENTS and segment > 0:
        return ventral_cord_fraction(neuron_class, segment)

    if neuron_class in {"HSN"}:
        return 0.48

    if neuron_class == "AVM":
        return 0.38

    if neuron_class == "ALM":
        return 0.34

    if neuron_class == "PVM":
        return 0.66

    if neuron_class == "PVD":
        return 0.62

    if neuron_class == "PLM":
        return 0.9

    if neuron_class in TAIL_CLASSES:
        return 0.88

    if neuron_class in HEAD_CLASSES:
        if metadata.cell_type == "motorneuron":
            return 0.16
        if metadata.cell_type == "interneuron":
            return 0.12
        return 0.08

    if cell_id.startswith(("I", "M", "MC", "MI", "NSM")):
        return 0.05

    if "tail" in metadata.notes.lower():
        return 0.9

    if metadata.cell_type == "sensory":
        return 0.1

    if metadata.cell_type == "interneuron":
        return 0.14

    if metadata.cell_type == "motorneuron":
        return 0.22

    return 0.5


def body_position(
    cell_id: str,
    index: int,
    metadata: CellMetadata,
    body_length: float = 10.0,
) -> tuple[float, float, float, float]:
    if cell_id == "NMJ":
        return (0.5, 0.0, -0.62, 0.0)

    neuron_class = infer_neuron_class(cell_id)
    segment = infer_segment(cell_id)
    fraction = infer_body_fraction(cell_id, neuron_class, segment, metadata)
    x = (fraction - 0.5) * body_length
    y, z = side_offsets(cell_id, neuron_class)

    is_ventral_cord = neuron_class in VENTRAL_CORD_CLASS_SEGMENTS
    if not is_ventral_cord and (neuron_class in HEAD_CLASSES or fraction < 0.2):
        angle = index * 2.399963229728653
        ring_radius = 0.42
        y = y if abs(y) > 0.01 else math.sin(angle) * ring_radius
        z = z if abs(z) > 0.01 else math.cos(angle) * ring_radius
    elif abs(y) < 0.01 and abs(z) < 0.01:
        angle = index * 1.61803398875
        y = math.sin(angle) * 0.18
        z = math.cos(angle) * 0.18

    return (fraction, round(x, 4), round(y, 4), round(z, 4))


def deterministic_position(index: int, total: int, kind: str) -> tuple[float, float, float]:
    if total <= 1:
        return (0.0, 0.0, 0.0)

    if kind == "muscle_output":
        return (6.0, 0.0, 0.0)

    t = index / (total - 1)
    angle = index * 2.399963229728653
    radius = 0.85 + 0.25 * math.sin(index * 0.37)
    x = (t - 0.5) * 10.0
    y = math.sin(angle) * radius
    z = math.cos(angle) * radius
    return (round(x, 4), round(y, 4), round(z, 4))


def make_nodes(
    raw_connections: Iterable[RawConnection],
    cell_metadata: dict[str, CellMetadata],
) -> list[dict]:
    cell_ids = sorted(
        {
            raw.normalized_neuron1
            for raw in raw_connections
        }
        | {
            raw.normalized_neuron2
            for raw in raw_connections
        }
    )

    biological_nodes = [cell_id for cell_id in cell_ids if node_kind(cell_id) == "neuron"]
    total_biological_nodes = len(biological_nodes)
    biological_index = {cell_id: index for index, cell_id in enumerate(biological_nodes)}

    nodes = []
    for export_index, cell_id in enumerate(cell_ids):
        kind = node_kind(cell_id)
        metadata = cell_metadata.get(cell_id, CellMetadata())
        layout_index = biological_index.get(cell_id, total_biological_nodes)
        body_fraction, x, y, z = body_position(cell_id, layout_index, metadata)
        fallback_x, fallback_y, fallback_z = deterministic_position(
            layout_index, total_biological_nodes, kind
        )
        nodes.append(
            {
                "id": cell_id,
                "kind": kind,
                "neuronClass": infer_neuron_class(cell_id),
                "side": infer_side(cell_id),
                "segment": infer_segment(cell_id),
                "cellType": metadata.cell_type,
                "cellCategory": metadata.cell_category,
                "notes": metadata.notes,
                "metadataSource": metadata.source,
                "bodyFraction": round(body_fraction, 5),
                "index": export_index,
                "x": x,
                "y": y,
                "z": z,
                "fallbackX": fallback_x,
                "fallbackY": fallback_y,
                "fallbackZ": fallback_z,
            }
        )
    return nodes


def add_component(
    edges: dict[tuple[str, str, str], EdgeAccumulator],
    source: str,
    target: str,
    kind: str,
    directed: bool,
    component_type: str,
    weight: int,
    row_number: int,
) -> None:
    key = (source, target, kind)
    if key not in edges:
        edges[key] = EdgeAccumulator(
            source=source,
            target=target,
            kind=kind,
            directed=directed,
        )
    edges[key].components[component_type] += weight
    edges[key].row_numbers.append(row_number)


def add_receive_component(
    edges: dict[tuple[str, str, str], EdgeAccumulator],
    source: str,
    target: str,
    component_type: str,
    weight: int,
    row_number: int,
) -> None:
    key = (source, target, "chemical")
    if key not in edges:
        edges[key] = EdgeAccumulator(
            source=source,
            target=target,
            kind="chemical",
            directed=True,
        )
    edges[key].receive_components[component_type] += weight
    edges[key].receive_row_numbers.append(row_number)


def make_edges(raw_connections: Iterable[RawConnection]) -> tuple[list[dict], dict]:
    edges: dict[tuple[str, str, str], EdgeAccumulator] = {}
    electrical_directed: dict[tuple[str, str], EdgeAccumulator] = {}

    raw_connections = list(raw_connections)
    for raw in raw_connections:
        n1 = raw.normalized_neuron1
        n2 = raw.normalized_neuron2
        connection_type = raw.connection_type

        if connection_type in CHEMICAL_SEND_TYPES:
            add_component(
                edges,
                source=n1,
                target=n2,
                kind="chemical",
                directed=True,
                component_type=connection_type,
                weight=raw.weight,
                row_number=raw.row_number,
            )
        elif connection_type in CHEMICAL_RECEIVE_TYPES:
            add_receive_component(
                edges,
                source=n2,
                target=n1,
                component_type=connection_type,
                weight=raw.weight,
                row_number=raw.row_number,
            )
        elif connection_type == "EJ":
            directed_key = (n1, n2)
            if directed_key not in electrical_directed:
                electrical_directed[directed_key] = EdgeAccumulator(
                    source=n1,
                    target=n2,
                    kind="electrical",
                    directed=False,
                )
            electrical_directed[directed_key].components[connection_type] += raw.weight
            electrical_directed[directed_key].row_numbers.append(raw.row_number)
        elif connection_type == "NMJ":
            add_component(
                edges,
                source=n1,
                target=n2,
                kind="neuromuscular",
                directed=True,
                component_type=connection_type,
                weight=raw.weight,
                row_number=raw.row_number,
            )
        else:
            raise ValueError(
                f"unsupported connection type {connection_type!r} in row {raw.row_number}"
            )

    for (source, target), forward_edge in sorted(electrical_directed.items()):
        pair_source, pair_target = sorted((source, target))
        if source != pair_source:
            continue

        reverse_edge = electrical_directed.get((target, source))
        if reverse_edge is None:
            weight = forward_edge.weight
            row_numbers = forward_edge.row_numbers
        elif source == target:
            weight = forward_edge.weight
            row_numbers = forward_edge.row_numbers
        else:
            weight = max(forward_edge.weight, reverse_edge.weight)
            row_numbers = forward_edge.row_numbers + reverse_edge.row_numbers

        key = (pair_source, pair_target, "electrical")
        edges[key] = EdgeAccumulator(
            source=pair_source,
            target=pair_target,
            kind="electrical",
            directed=False,
            components=Counter({"EJ": weight}),
            row_numbers=sorted(row_numbers),
        )

    exported_edges = []
    validation = {
        "chemicalMismatches": [],
        "electricalMismatches": [],
        "missingElectricalReciprocals": [],
    }

    for edge in edges.values():
        if edge.kind == "chemical":
            send_weight = edge.weight
            receive_weight = int(sum(edge.receive_components.values()))
            if send_weight != receive_weight:
                validation["chemicalMismatches"].append(
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "sendWeight": send_weight,
                        "receiveWeight": receive_weight,
                    }
                )

        exported_edges.append(edge_to_export(edge))

    for (source, target), edge in electrical_directed.items():
        reverse = electrical_directed.get((target, source))
        if reverse is None and source != target:
            validation["missingElectricalReciprocals"].append(
                {"source": source, "target": target, "weight": edge.weight}
            )
        elif reverse is not None and edge.weight != reverse.weight:
            validation["electricalMismatches"].append(
                {
                    "source": source,
                    "target": target,
                    "weight": edge.weight,
                    "reverseWeight": reverse.weight,
                }
            )

    exported_edges.sort(key=lambda edge: (edge["kind"], edge["source"], edge["target"]))
    return exported_edges, validation


def edge_to_export(edge: EdgeAccumulator) -> dict:
    arrow = "->" if edge.directed else "--"
    edge_id = f"{edge.kind}:{edge.source}{arrow}{edge.target}"
    components = [
        {"type": component_type, "weight": int(weight)}
        for component_type, weight in sorted(edge.components.items())
    ]
    receive_components = [
        {"type": component_type, "weight": int(weight)}
        for component_type, weight in sorted(edge.receive_components.items())
    ]
    return {
        "id": edge_id,
        "source": edge.source,
        "target": edge.target,
        "kind": edge.kind,
        "directed": edge.directed,
        "weight": edge.weight,
        "rowCount": edge.row_count,
        "components": components,
        "receiveComponents": receive_components,
    }


def make_summary(raw_connections: list[RawConnection], nodes: list[dict], edges: list[dict]) -> dict:
    raw_type_counts = Counter(raw.connection_type for raw in raw_connections)
    edge_kind_counts = Counter(edge["kind"] for edge in edges)
    weight_by_kind = defaultdict(int)
    for edge in edges:
        weight_by_kind[edge["kind"]] += int(edge["weight"])

    return {
        "rawRows": len(raw_connections),
        "nodes": len(nodes),
        "neurons": sum(1 for node in nodes if node["kind"] == "neuron"),
        "endOrgans": sum(1 for node in nodes if node["kind"] != "neuron"),
        "edges": len(edges),
        "rawTypeCounts": dict(sorted(raw_type_counts.items())),
        "edgeKindCounts": dict(sorted(edge_kind_counts.items())),
        "weightByKind": dict(sorted(weight_by_kind.items())),
    }


def write_sqlite(
    db_path: Path,
    source_csv: Path,
    raw_connections: list[RawConnection],
    nodes: list[dict],
    edges: list[dict],
    summary: dict,
    validation: dict,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE nodes (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                neuron_class TEXT NOT NULL,
                side TEXT NOT NULL,
                segment INTEGER NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                z REAL NOT NULL,
                properties_json TEXT NOT NULL
            );

            CREATE TABLE edges (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                kind TEXT NOT NULL,
                directed INTEGER NOT NULL,
                weight REAL NOT NULL,
                row_count INTEGER NOT NULL,
                properties_json TEXT NOT NULL,
                FOREIGN KEY(source) REFERENCES nodes(id),
                FOREIGN KEY(target) REFERENCES nodes(id)
            );

            CREATE TABLE raw_connections (
                row_number INTEGER PRIMARY KEY,
                neuron1 TEXT NOT NULL,
                neuron2 TEXT NOT NULL,
                normalized_neuron1 TEXT NOT NULL,
                normalized_neuron2 TEXT NOT NULL,
                type TEXT NOT NULL,
                weight INTEGER NOT NULL
            );

            CREATE INDEX idx_edges_source ON edges(source);
            CREATE INDEX idx_edges_target ON edges(target);
            CREATE INDEX idx_edges_kind ON edges(kind);
            """
        )

        metadata = {
            "schema_version": "1.0.0",
            "source_csv": str(source_csv),
            "summary": json.dumps(summary, sort_keys=True),
            "validation": json.dumps(validation, sort_keys=True),
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            sorted(metadata.items()),
        )

        connection.executemany(
            """
            INSERT INTO nodes(
                id, kind, neuron_class, side, segment, x, y, z, properties_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    node["id"],
                    node["kind"],
                    node["neuronClass"],
                    node["side"],
                    node["segment"],
                    node["x"],
                    node["y"],
                    node["z"],
                    json.dumps(node, sort_keys=True),
                )
                for node in nodes
            ],
        )

        connection.executemany(
            """
            INSERT INTO edges(
                id, source, target, kind, directed, weight, row_count, properties_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    edge["id"],
                    edge["source"],
                    edge["target"],
                    edge["kind"],
                    1 if edge["directed"] else 0,
                    edge["weight"],
                    edge["rowCount"],
                    json.dumps(edge, sort_keys=True),
                )
                for edge in edges
            ],
        )

        connection.executemany(
            """
            INSERT INTO raw_connections(
                row_number, neuron1, neuron2, normalized_neuron1, normalized_neuron2,
                type, weight
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    raw.row_number,
                    raw.neuron1,
                    raw.neuron2,
                    raw.normalized_neuron1,
                    raw.normalized_neuron2,
                    raw.connection_type,
                    raw.weight,
                )
                for raw in raw_connections
            ],
        )


def write_unity_json(
    json_path: Path,
    source_csv: Path,
    nodes: list[dict],
    edges: list[dict],
    summary: dict,
    validation: dict,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": "1.0.0",
        "source": {
            "name": "WormAtlas NeuronConnect",
            "sourceFile": str(source_csv),
            "normalization": "Cell IDs are uppercased; chemical receive rows validate send rows; electrical rows are collapsed to undirected pairs.",
            "layout": "Body-axis layout enriched with WormWiring SI 4 cell type/category metadata where available. Positions are anatomical approximations from class, segment, side, and AP body region, not measured 3D nuclei coordinates.",
        },
        "summary": summary,
        "validation": validation,
        "nodes": nodes,
        "edges": edges,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import WormAtlas NeuronConnect CSV into SQLite and Unity JSON."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/NeuronConnect.csv"),
        help="NeuronConnect CSV exported from the WormAtlas .xls workbook.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/connectome.db"),
        help="Output SQLite database path.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("data/unity_connectome.json"),
        help="Output Unity-readable JSON path.",
    )
    parser.add_argument(
        "--cell-metadata-dir",
        type=Path,
        default=Path("data/wormwiring/si4_sheets"),
        help="Optional directory containing WormWiring SI 4 sheets exported as CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_connections = read_csv(args.input)
    cell_metadata = load_cell_metadata(args.cell_metadata_dir)
    nodes = make_nodes(raw_connections, cell_metadata)
    edges, validation = make_edges(raw_connections)
    summary = make_summary(raw_connections, nodes, edges)

    write_sqlite(
        db_path=args.db,
        source_csv=args.input,
        raw_connections=raw_connections,
        nodes=nodes,
        edges=edges,
        summary=summary,
        validation=validation,
    )
    write_unity_json(
        json_path=args.json,
        source_csv=args.input,
        nodes=nodes,
        edges=edges,
        summary=summary,
        validation=validation,
    )

    print(json.dumps({"summary": summary, "validation": validation}, indent=2))
    print(f"Wrote {args.db}")
    print(f"Wrote {args.json}")


if __name__ == "__main__":
    main()
