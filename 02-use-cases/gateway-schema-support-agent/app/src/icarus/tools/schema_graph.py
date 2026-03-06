import hashlib
import json
from pathlib import Path

import networkx as nx
import yaml
from networkx.readwrite import json_graph
from strands import tool


def _extract_refs(obj: dict | list | str) -> list[str]:
    """Recursively extract all $ref values from an object."""
    refs = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "$ref" and isinstance(value, str):
                refs.append(value)
            else:
                refs.extend(_extract_refs(value))
    elif isinstance(obj, list):
        for item in obj:
            refs.extend(_extract_refs(item))
    return refs


class SchemaGraphActions:
    def __init__(self, context_dir: Path):
        context_dir = context_dir.resolve()

        self.context_dir = context_dir
        self.schema_path = context_dir / "schema.yaml"
        self.graph_cache_dir = context_dir / ".cache" / "schema_graphs"

        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

        # Ensure cache directory for schema graphs exists
        self.graph_cache_dir.mkdir(parents=True, exist_ok=True)

    def _build_schema_graph(
        self, include_methods: bool = True, exclude_nodes: list[str] | None = None
    ) -> nx.DiGraph:
        if exclude_nodes is None:
            exclude_nodes = []

        schema_data = self.schema_path.read_text()

        # Check if schema graph is cached
        schema_hash = hashlib.sha256(schema_data.encode("utf-8")).hexdigest()
        schema_cache_path = self.graph_cache_dir / f"{schema_hash}.json"
        if schema_cache_path.exists():
            schema_graph_data = json.loads(schema_cache_path.read_text())
            G = json_graph.node_link_graph(schema_graph_data, directed=True, edges="edges")
            assert isinstance(G, nx.DiGraph)
            return G

        # Else, build graph from scratch
        schema = yaml.safe_load(schema_data)
        G = nx.DiGraph()

        # Add component nodes
        if "components" in schema:
            for component_type, components in schema["components"].items():
                for name, definition in components.items():
                    node_id = f"#/components/{component_type}/{name}"
                    if node_id not in exclude_nodes:
                        G.add_node(node_id, node_type="component", component_type=component_type)
                        for ref in _extract_refs(definition):
                            if ref not in exclude_nodes:
                                G.add_edge(node_id, ref, edge_type="references")

        # Add path nodes
        if "paths" in schema:
            for path, path_item in schema["paths"].items():
                if path not in exclude_nodes:
                    methods = list(path_item.keys()) if include_methods else []
                    G.add_node(path, node_type="path", methods=methods)
                    for ref in _extract_refs(path_item):
                        if ref.startswith("#/components/") and ref not in exclude_nodes:
                            G.add_edge(ref, path, edge_type="used_in")

        # Add webhook nodes
        if "webhooks" in schema:
            for webhook, webhook_item in schema["webhooks"].items():
                node_id = f"webhook:{webhook}"
                if node_id not in exclude_nodes:
                    methods = list(webhook_item.keys()) if include_methods else []
                    G.add_node(node_id, node_type="webhook", methods=methods)
                    for ref in _extract_refs(webhook_item):
                        if ref.startswith("#/components/") and ref not in exclude_nodes:
                            G.add_edge(ref, node_id, edge_type="used_in")

        # Cache schema graph
        schema_graph_data = json_graph.node_link_data(G, edges="edges")
        schema_graph_json = json.dumps(schema_graph_data)
        schema_cache_path.write_text(schema_graph_json)

        return G

    @tool(
        description=(
            "Build a dependency graph from the OpenAPI schema and find all paths related to a component. "
            "The graph represents relationships between components, paths, and webhooks. "
            "Uses shortest path distance to determine relatedness, where max_distance_to_component "
            "controls how many hops away from the component to search for paths."
        ),
        inputSchema={
            "json": {
                "type": "object",
                "properties": {
                    "component_ref": {
                        "type": "string",
                        "description": "Component reference (e.g., #/components/schemas/MySchema).",
                    },
                    "max_distance_to_component": {
                        "type": "integer",
                        "description": (
                            "Maximum graph distance (number of hops) from the component to paths. "
                            "Distance 1 means directly related paths, distance 2 includes paths "
                            "related through one intermediate component, etc. [default: 1]"
                        ),
                        "default": 1,
                    },
                },
                "required": ["component_ref"],
            }
        },
    )
    def list_paths_related_to_component(
        self, component_ref: str, max_distance_to_component: int = 1
    ) -> dict:
        if not component_ref.startswith("#/components/"):
            raise ValueError(f"Invalid component reference: {component_ref}")

        G = self._build_schema_graph(include_methods=False)

        if component_ref not in G.nodes:
            raise ValueError(f"Component not found: {component_ref}")

        distances = nx.shortest_path_length(G, source=component_ref)

        related_paths = []
        for node, distance in distances.items():
            if node == component_ref:
                continue
            if G.nodes[node]["node_type"] == "path" and distance <= max_distance_to_component:
                related_paths.append(node)

        return {"status": "success", "content": [{"json": related_paths}]}

    @tool(
        description=(
            "Update the OpenAPI schema file to retain only the specified paths, removing all others. "
            "This modifies schema.yaml directly and permanently deletes unspecified paths. "
            "Always confirm with the user before using this tool as the operation is destructive."
        ),
        inputSchema={
            "json": {
                "type": "object",
                "properties": {
                    "keep_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of API endpoint paths to retain in the schema (e.g., ['/users', '/orders']). "
                            "All paths not in this list will be permanently removed from schema.yaml."
                        ),
                    },
                },
                "required": ["keep_paths"],
            }
        },
    )
    def update_schema_extract_paths(self, keep_paths: list[str]) -> dict:
        schema = yaml.safe_load(self.schema_path.read_text())
        schema["paths"] = schema.get("paths", {})

        num_paths_drop = 0
        keep_paths_set = set(keep_paths)
        for path in list(schema["paths"].keys()):
            if path not in keep_paths_set:
                del schema["paths"][path]
                num_paths_drop += 1

        self.schema_path.write_text(yaml.dump(schema, sort_keys=False))

        return {
            "status": "success",
            "content": [{"json": {"num_paths_dropped": num_paths_drop}}],
        }
