# Authors:
# - Zakar Handricken
import shutil
import traceback
from pathlib import Path
import sqlite3
import json

extract = lambda x: int(str(x).split("-")[-1].split(".")[0])


class SQL:
    # TABLES
    @staticmethod
    def create_table_nodes_sql() -> str:
        return 'CREATE TABLE IF NOT EXISTS "nodes" ("key" TEXT NOT NULL, "properties" TEXT, PRIMARY KEY("key"));'

    @staticmethod
    def create_table_edges_sql() -> str:
        return 'CREATE TABLE IF NOT EXISTS "edges" ("source" TEXT, "target" TEXT, "properties" TEXT, UNIQUE("source", "target"));'

    @staticmethod
    def delete_table_nodes_sql() -> str:
        return "DROP TABLE nodes;"

    @staticmethod
    def delete_table_edges_sql() -> str:
        return "DROP TABLE edges;"

    # NODES
    @staticmethod
    def create_node_sql() -> str:
        return 'INSERT INTO nodes ("key", "properties") VALUES (?, ?);'

    @staticmethod
    def create_node_without_properties_sql() -> str:
        return 'INSERT INTO nodes ("key") VALUES (?);'

    @staticmethod
    def get_node_sql() -> str:
        return 'SELECT * FROM "main"."nodes" WHERE "key"=(?);'

    @staticmethod
    def update_node_sql() -> str:
        return 'UPDATE "main"."nodes" SET "properties"=(?) WHERE "key"=(?);'

    @staticmethod
    def delete_node_sql() -> str:
        return 'DELETE FROM "main"."nodes" WHERE "key"=(?);'

    @staticmethod
    def contains_node_sql() -> str:
        return 'SELECT * FROM "main"."nodes" WHERE "key"=(?) LIMIT 1;'

    @staticmethod
    def get_all_nodes_sql() -> str:
        return 'SELECT * FROM "main"."nodes";'

    @staticmethod
    def get_all_node_keys_sql() -> str:
        return 'SELECT "key" FROM "main"."nodes";'

    # EDGES
    @staticmethod
    def create_edge_sql() -> str:
        return 'INSERT INTO "main"."edges" ("source", "target", "properties") VALUES (?, ?, ?);'

    @staticmethod
    def create_edge_without_properties_sql() -> str:
        return 'INSERT INTO "main"."edges" ("source", "target") VALUES (?, ?);'

    @staticmethod
    def get_edge_sql() -> str:
        return 'SELECT * FROM "main"."edges" WHERE "source"=(?) AND "target"=(?);'

    @staticmethod
    def get_edge_incoming_sql() -> str:
        return 'SELECT * FROM "main"."edges" WHERE "target"=(?);'

    @staticmethod
    def get_edge_outgoing_sql() -> str:
        return 'SELECT * FROM "main"."edges" WHERE "source"=(?);'

    @staticmethod
    def update_edge_sql() -> str:
        return 'UPDATE "main"."edges" SET "properties"=(?) WHERE "source"=(?) AND "target"=(?);'

    @staticmethod
    def delete_edge_sql() -> str:
        return 'DELETE FROM "main"."edges" WHERE "source"=(?) AND "target"=(?);'

    @staticmethod
    def delete_edge_incoming_sql() -> str:
        return 'DELETE FROM "main"."edges" WHERE "target"=(?);'

    @staticmethod
    def delete_edge_outgoing_sql() -> str:
        return 'DELETE FROM "main"."edges" WHERE "source"=(?);'

    @staticmethod
    def contains_edge_sql() -> str:
        return (
            'SELECT * FROM "main"."edges" WHERE "source"=(?) AND "target"=(?) LIMIT 1;'
        )

    @staticmethod
    def get_all_edges_sql() -> str:
        return 'SELECT * FROM "main"."edges";'

    @staticmethod
    def get_all_edge_keys_sql() -> str:
        return 'SELECT "source", "target" FROM "main"."edges";'


class Database(SQL):
    def __init__(self, directory: str) -> None:
        self.directory = directory
        self.connection = sqlite3.connect(directory)
        self.connection.autocommit = True
        self.cursor = self.connection.cursor()

    def clear_data(self):
        self.cursor.execute(self.clear_data_sql())

    # TABLES
    def create_table_nodes(self):
        self.cursor.execute(self.create_table_nodes_sql())

    def create_table_edges(self):
        self.cursor.execute(self.create_table_edges_sql())

    def delete_table_nodes(self):
        self.cursor.execute(self.delete_table_nodes_sql())

    def delete_table_edges(self):
        self.cursor.execute(self.delete_table_edges_sql())

    # NODES
    def create_node(self, key: str, properties=None):
        with self.connection:
            self.cursor.execute(self.create_node_sql(), (key, properties))

    def get_node(self, key: str):
        return self.cursor.execute(self.get_node_sql(), (key,)).fetchone()

    def update_node(self, key: str, properties: None):
        with self.connection:
            self.cursor.execute(self.update_node_sql(), (properties, key))

    def delete_node(self, key: str):
        with self.connection:
            self.cursor.execute(self.delete_node_sql(), (key,))

    def get_all_nodes(self):
        return self.cursor.execute(self.get_all_nodes_sql(), ()).fetchall()

    def get_all_node_keys(self):
        return self.cursor.execute(self.get_all_node_keys_sql()).fetchall()

    # EDGES
    def create_edge(self, source: str, target: str, properties=None):
        with self.connection:
            self.cursor.execute(self.create_edge_sql(), (source, target, properties))

    def get_edge(self, source: str, target: str):
        return self.cursor.execute(self.get_edge_sql(), (source, target)).fetchone()

    def get_edge_incoming(self, target: str):
        return self.cursor.execute(self.get_edge_incoming_sql(), (target,)).fetchall()

    def get_edge_outgoing(self, source: str):
        return self.cursor.execute(self.get_edge_outgoing_sql(), (source,)).fetchall()

    def update_edge(self, source: str, target: str, properties=None):
        with self.connection:
            self.cursor.execute(self.update_edge_sql(), (properties, source, target))

    def delete_edge(self, source: str, target: str):
        with self.connection:
            self.cursor.execute(self.delete_edge_sql(), (source, target))

    def delete_edge_incoming(self, target: str):
        with self.connection:
            self.cursor.execute(self.delete_edge_incoming_sql(), (target,))

    def delete_edge_outgoing(self, source: str):
        with self.connection:
            self.cursor.execute(self.delete_edge_outgoing_sql(), (source,))

    def get_all_edges(self):
        return self.cursor.execute(self.get_all_edges_sql()).fetchall()


class Node(object):
    __slots__ = ["key", "properties"]

    def __init__(
        self,
        key=None,
        properties=None,
    ) -> None:
        self.key = key
        self.properties = properties

    def update(self, state: dict) -> None:
        self.key = state["key"]
        self.properties = state["properties"]

    def data(self) -> dict:
        return {"key": self.key, "properties": self.properties}


class Edge(object):
    __slots__ = ["source", "target", "properties"]

    def __init__(
        self,
        source=None,
        target=None,
        properties=None,
    ) -> None:
        self.source = source
        self.target = target
        self.properties = properties

    def update(self, state: dict) -> None:
        self.source = state["source"]
        self.target = state["target"]
        self.properties = state["properties"]

    def data(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "properties": self.properties,
        }


class NodeManager:
    def __init__(self, database: Database) -> None:
        self.database = database

    def _encode_properties(self, properties):
        return json.dumps(properties)

    def _decode_properties(self, properties):
        if properties is None:
            return None
        try:
            return json.loads(properties)
        except json.JSONDecodeError:
            return properties

    def create(self, key, properties={}) -> None:
        try:
            if not self.contains(key):
                self.database.create_node(
                    key=key, properties=self._encode_properties(properties)
                )
        except Exception:
            traceback.print_exc()

    def get(self, key):
        try:
            data = self.database.get_node(key=key)
            if data is None:
                return None
            key, properties = data
            return self._decode_properties(properties)
        except Exception:
            traceback.print_exc()
        return None

    def update(self, key, properties) -> None:
        try:
            if self.contains(key):
                self.database.update_node(
                    key=key, properties=self._encode_properties(properties)
                )
        except Exception:
            traceback.print_exc()

    def delete(self, key) -> None:
        try:
            self.database.delete_node(key=key)
            self.database.delete_edge_outgoing(source=key)
            self.database.delete_edge_incoming(target=key)
        except Exception:
            traceback.print_exc()

    def contains(self, key) -> bool:
        return self.database.get_node(key=key) is not None

    def all(self) -> iter:
        try:
            for key, properties in self.database.get_all_nodes():
                yield key
        except Exception:
            traceback.print_exc()
        return []

    def keys(self) -> iter:
        return self.all()

    def get_all(self) -> iter:
        return self.all()

    def validate(self, key):
        if not isinstance(key, str):
            raise TypeError("key is not an instance of str. Must be str.")


class EdgeManager(object):
    def __init__(self, database: Database) -> None:
        self.database = database

    def _encode_properties(self, properties):
        return json.dumps(properties)

    def _decode_properties(self, properties):
        if properties is None:
            return None
        try:
            return json.loads(properties)
        except json.JSONDecodeError:
            return properties

    def create(self, source, target, properties={}) -> None:
        try:
            if not self.contains(source, target):
                self.database.create_edge(
                    source=source,
                    target=target,
                    properties=self._encode_properties(properties),
                )
        except Exception:
            traceback.print_exc()

    def get(self, source, target):
        try:
            data = self.database.get_edge(source=source, target=target)
            if data is None:
                return None
            source, target, properties = data
            return self._decode_properties(properties)
        except Exception:
            traceback.print_exc()
        return None

    def incoming(self, key) -> iter:
        try:
            for data in self.database.get_edge_incoming(target=key):
                source, target, properties = data
                yield source
        except Exception:
            traceback.print_exc()
        return []

    def outgoing(self, key) -> iter:
        try:
            for data in self.database.get_edge_outgoing(source=key):
                source, target, properties = data
                yield target
        except Exception:
            traceback.print_exc()
        return []

    def update(self, source, target, properties={}) -> None:
        try:
            self.validate(source)
            self.validate(target)
            if self.contains(source, target):
                self.database.update_edge(
                    source=source,
                    target=target,
                    properties=self._encode_properties(properties),
                )
        except Exception:
            traceback.print_exc()

    def delete(self, source, target) -> None:
        try:
            self.validate(source)
            self.validate(target)
            self.database.delete_edge(source=source, target=target)
        except Exception:
            traceback.print_exc()

    def delete_related(self, key) -> None:
        try:
            self.validate(key)
            self.database.delete_edge_incoming(target=key)
            self.database.delete_edge_outgoing(source=key)
        except Exception:
            traceback.print_exc()

    def contains(self, source, target) -> bool:
        return self.database.get_edge(source=source, target=target) is not None

    def all(self) -> iter:
        try:
            for data in self.database.get_all_edges():
                source, target, properties = data
                yield (source, target)
        except Exception:
            traceback.print_exc()
        return []

    def get_all(self) -> iter:
        return self.all()

    def get_incoming(self, key) -> iter:
        return self.incoming(key)

    def get_outgoing(self, key) -> iter:
        return self.outgoing(key)

    def delete_all(self, key) -> None:
        self.delete_related(key)

    def validate(self, key):
        if not isinstance(key, str):
            raise TypeError("key is not an instance of str")


class GRT(object):
    def __init__(
        self,
        directory="./database",
    ) -> None:

        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.directory_database = self.directory.joinpath("graph.db")

        self.database = Database(self.directory_database)
        self.database.create_table_nodes()
        self.database.create_table_edges()

        self.nodes = NodeManager(self.database)
        self.edges = EdgeManager(self.database)

    def close(self):
        self.database.connection.close()

    def clear(self):
        try:
            self.database = Database(self.directory_database)
            self.database.delete_table_edges()
            self.database.delete_table_nodes()
            self.database.create_table_nodes()
            self.database.create_table_edges()
        except Exception:
            traceback.print_exc()

    def copy(self, directory):
        try:
            shutil.copytree(self.directory, directory, dirs_exist_ok=True)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as directory:
        grt = GRT(directory=directory)

        # Create nodes
        grt.nodes.create("1", {"name": "Node 1"})
        grt.nodes.create("2", {"name": "Node 2"})

        # Create an edge
        grt.edges.create("1", "2", {"relationship": "connected"})

        # Get node
        print("Node 1:", grt.nodes.get("1"))
        print("Node All:", next(grt.nodes.all()))

        # Get edge
        print("Edge 1->2:", grt.edges.get("1", "2"))

        # Check if node exists
        print("Node 1 exists:", grt.nodes.contains("1"))

        # Check if edge exists
        print("Edge 1->2 exists:", grt.edges.contains("1", "2"))

        # Update node
        grt.nodes.update("1", {"name": "Updated Node 1"})
        print("Updated Node 1:", grt.nodes.get("1"))

        # Update edge
        grt.edges.update("1", "2", {"relationship": "updated connection"})
        print("Updated Edge 1->2:", grt.edges.get("1", "2"))

        # Delete nodes and edges
        grt.edges.delete("1", "2")
        grt.nodes.delete("1")
        grt.nodes.delete("2")
        grt.close()
