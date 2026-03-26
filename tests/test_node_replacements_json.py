"""Tests for NodeReplaceManager.load_from_json — auto-registration of
node_replacements.json from custom node directories."""
import json
import os
import tempfile
import unittest

from app.node_replace_manager import NodeReplaceManager


class SimpleNodeReplace:
    """Lightweight stand-in for comfy_api.latest._io.NodeReplace (avoids torch import)."""
    def __init__(self, new_node_id, old_node_id, old_widget_ids=None,
                 input_mapping=None, output_mapping=None):
        self.new_node_id = new_node_id
        self.old_node_id = old_node_id
        self.old_widget_ids = old_widget_ids
        self.input_mapping = input_mapping
        self.output_mapping = output_mapping

    def as_dict(self):
        return {
            "new_node_id": self.new_node_id,
            "old_node_id": self.old_node_id,
            "old_widget_ids": self.old_widget_ids,
            "input_mapping": list(self.input_mapping) if self.input_mapping else None,
            "output_mapping": list(self.output_mapping) if self.output_mapping else None,
        }


class TestLoadFromJson(unittest.TestCase):
    """Test auto-registration of node_replacements.json from custom node directories."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = NodeReplaceManager()

    def _write_json(self, data):
        path = os.path.join(self.tmpdir, "node_replacements.json")
        with open(path, "w") as f:
            json.dump(data, f)

    def _load(self):
        self.manager.load_from_json(self.tmpdir, "test-node-pack", _node_replace_class=SimpleNodeReplace)

    def test_no_file_does_nothing(self):
        """No node_replacements.json — should silently do nothing."""
        self._load()
        self.assertEqual(self.manager.as_dict(), {})

    def test_empty_object(self):
        """Empty {} — should do nothing."""
        self._write_json({})
        self._load()
        self.assertEqual(self.manager.as_dict(), {})

    def test_single_replacement(self):
        """Single replacement entry registers correctly."""
        self._write_json({
            "OldNode": [{
                "new_node_id": "NewNode",
                "old_node_id": "OldNode",
                "input_mapping": [{"new_id": "model", "old_id": "ckpt_name"}],
                "output_mapping": [{"new_idx": 0, "old_idx": 0}],
            }]
        })
        self._load()
        result = self.manager.as_dict()
        self.assertIn("OldNode", result)
        self.assertEqual(len(result["OldNode"]), 1)
        entry = result["OldNode"][0]
        self.assertEqual(entry["new_node_id"], "NewNode")
        self.assertEqual(entry["old_node_id"], "OldNode")
        self.assertEqual(entry["input_mapping"], [{"new_id": "model", "old_id": "ckpt_name"}])
        self.assertEqual(entry["output_mapping"], [{"new_idx": 0, "old_idx": 0}])

    def test_multiple_replacements(self):
        """Multiple old_node_ids each with entries."""
        self._write_json({
            "NodeA": [{"new_node_id": "NodeB", "old_node_id": "NodeA"}],
            "NodeC": [{"new_node_id": "NodeD", "old_node_id": "NodeC"}],
        })
        self._load()
        result = self.manager.as_dict()
        self.assertEqual(len(result), 2)
        self.assertIn("NodeA", result)
        self.assertIn("NodeC", result)

    def test_multiple_alternatives_for_same_node(self):
        """Multiple replacement options for the same old node."""
        self._write_json({
            "OldNode": [
                {"new_node_id": "AltA", "old_node_id": "OldNode"},
                {"new_node_id": "AltB", "old_node_id": "OldNode"},
            ]
        })
        self._load()
        result = self.manager.as_dict()
        self.assertEqual(len(result["OldNode"]), 2)

    def test_null_mappings(self):
        """Null input/output mappings (trivial replacement)."""
        self._write_json({
            "OldNode": [{
                "new_node_id": "NewNode",
                "old_node_id": "OldNode",
                "input_mapping": None,
                "output_mapping": None,
            }]
        })
        self._load()
        entry = self.manager.as_dict()["OldNode"][0]
        self.assertIsNone(entry["input_mapping"])
        self.assertIsNone(entry["output_mapping"])

    def test_old_node_id_defaults_to_key(self):
        """If old_node_id is missing from entry, uses the dict key."""
        self._write_json({
            "OldNode": [{"new_node_id": "NewNode"}]
        })
        self._load()
        entry = self.manager.as_dict()["OldNode"][0]
        self.assertEqual(entry["old_node_id"], "OldNode")

    def test_invalid_json_skips(self):
        """Invalid JSON file — should warn and skip, not crash."""
        path = os.path.join(self.tmpdir, "node_replacements.json")
        with open(path, "w") as f:
            f.write("{invalid json")
        self._load()
        self.assertEqual(self.manager.as_dict(), {})

    def test_non_object_json_skips(self):
        """JSON array instead of object — should warn and skip."""
        self._write_json([1, 2, 3])
        self._load()
        self.assertEqual(self.manager.as_dict(), {})

    def test_non_list_value_skips(self):
        """Value is not a list — should warn and skip that key."""
        self._write_json({
            "OldNode": "not a list",
            "GoodNode": [{"new_node_id": "NewNode", "old_node_id": "GoodNode"}],
        })
        self._load()
        result = self.manager.as_dict()
        self.assertNotIn("OldNode", result)
        self.assertIn("GoodNode", result)

    def test_with_old_widget_ids(self):
        """old_widget_ids are passed through."""
        self._write_json({
            "OldNode": [{
                "new_node_id": "NewNode",
                "old_node_id": "OldNode",
                "old_widget_ids": ["width", "height"],
            }]
        })
        self._load()
        entry = self.manager.as_dict()["OldNode"][0]
        self.assertEqual(entry["old_widget_ids"], ["width", "height"])

    def test_set_value_in_input_mapping(self):
        """input_mapping with set_value entries."""
        self._write_json({
            "OldNode": [{
                "new_node_id": "NewNode",
                "old_node_id": "OldNode",
                "input_mapping": [
                    {"new_id": "method", "set_value": "lanczos"},
                    {"new_id": "size", "old_id": "dimension"},
                ],
            }]
        })
        self._load()
        entry = self.manager.as_dict()["OldNode"][0]
        self.assertEqual(len(entry["input_mapping"]), 2)

    def test_missing_new_node_id_skipped(self):
        """Entry without new_node_id is skipped."""
        self._write_json({
            "OldNode": [
                {"old_node_id": "OldNode"},
                {"new_node_id": "", "old_node_id": "OldNode"},
                {"new_node_id": "ValidNew", "old_node_id": "OldNode"},
            ]
        })
        self._load()
        result = self.manager.as_dict()
        self.assertEqual(len(result["OldNode"]), 1)
        self.assertEqual(result["OldNode"][0]["new_node_id"], "ValidNew")

    def test_non_dict_entry_skipped(self):
        """Non-dict entries in the list are silently skipped."""
        self._write_json({
            "OldNode": [
                "not a dict",
                {"new_node_id": "NewNode", "old_node_id": "OldNode"},
            ]
        })
        self._load()
        result = self.manager.as_dict()
        self.assertEqual(len(result["OldNode"]), 1)

    def test_has_replacement_after_load(self):
        """Manager reports has_replacement correctly after JSON load."""
        self._write_json({
            "OldNode": [{"new_node_id": "NewNode", "old_node_id": "OldNode"}],
        })
        self.assertFalse(self.manager.has_replacement("OldNode"))
        self._load()
        self.assertTrue(self.manager.has_replacement("OldNode"))
        self.assertFalse(self.manager.has_replacement("UnknownNode"))


if __name__ == "__main__":
    unittest.main()
