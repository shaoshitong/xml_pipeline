import unittest
import xml.etree.ElementTree as ET

from svg_source_group_nesting_v1 import nest_source_groups, _world_rectangles


def document(rows):
    tree = ET.Element("mxfile")
    root = ET.SubElement(ET.SubElement(ET.SubElement(tree, "diagram"), "mxGraphModel"), "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    for identifier, parent, box, group in rows:
        cell = ET.SubElement(root, "mxCell", id=identifier, parent=parent, vertex="1", style="group=1;" if group else "shape=text;")
        ET.SubElement(cell, "mxGeometry", dict(zip(("x", "y", "width", "height"), map(str, box))), **{"as": "geometry"})
    return ET.tostring(tree, encoding="unicode")


def parsed(xml):
    return {c.get("id"): c for c in ET.fromstring(xml).iter("mxCell")}


def paint_order(xml):
    cells = parsed(xml)
    def visit(parent):
        result = []
        for identifier, cell in cells.items():
            if cell.get("parent") == parent:
                if not identifier.startswith("node_source_"):
                    result.append(identifier)
                result.extend(visit(identifier))
        return result
    return visit("1")


class NestingTests(unittest.TestCase):
    def test_intervening_inner_node_then_outer_annotation_preserves_source_order(self):
        xml = document([
            ("node_source_outer", "1", ("10.25", "20.5", 200, 150), True),
            ("outline", "node_source_outer", (0, 0, 200, 150), False),
            ("node_source_inner", "1", ("30.75", "40.5", 80, 30), True),
            ("inner_label", "node_source_inner", (1, 2, 10, 10), False),
            ("late_outer_annotation", "node_source_outer", (30, 30, 5, 5), False),
        ])
        self.assertEqual(paint_order(xml), ["outline", "late_outer_annotation", "inner_label"])
        result, proof = nest_source_groups(xml)
        self.assertEqual(paint_order(result), ["outline", "inner_label", "late_outer_annotation"])
        self.assertEqual(_world_rectangles(parsed(result)), _world_rectangles(parsed(xml)))
        self.assertEqual(parsed(result)["node_source_inner"].get("parent"), "node_source_outer")
        self.assertEqual(parsed(result)["inner_label"].get("parent"), "node_source_inner")
        self.assertEqual(proof["nested_groups"], 1)
        again, second = nest_source_groups(result)
        self.assertEqual(again, result)
        self.assertEqual(second["changes"], [])

    def test_three_levels_preserve_world_geometry_and_endpoint_bindings(self):
        xml = document([
            ("node_source_a", "1", (10, 10, 200, 200), True),
            ("node_source_b", "1", (30, 40, 100, 100), True),
            ("node_source_c", "1", (45, 55, 20, 20), True),
        ])
        tree = ET.fromstring(xml)
        root = tree.find(".//root")
        edge = ET.SubElement(root, "mxCell", id="edge", parent="1", edge="1", source="node_source_c", target="node_source_a", style="exitX=0.5;entryY=0.1;")
        geometry = ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
        ET.SubElement(geometry, "mxPoint", x="100.5", y="90.25", **{"as": "sourcePoint"})
        xml = ET.tostring(tree, encoding="unicode")
        result, proof = nest_source_groups(xml)
        cells = parsed(result)
        self.assertEqual(cells["node_source_c"].get("parent"), "node_source_b")
        self.assertEqual(cells["node_source_b"].get("parent"), "node_source_a")
        self.assertEqual(ET.tostring(cells["edge"]), ET.tostring(parsed(xml)["edge"]))
        self.assertEqual(proof["nested_groups"], 2)
        self.assertEqual(_world_rectangles(cells), _world_rectangles(parsed(xml)))

    def test_intersection_and_ambiguous_equal_area_do_not_create_arbitrary_parent(self):
        xml = document([
            ("node_source_a", "1", (0, 0, 100, 100), True),
            ("node_source_b", "1", (5, 0, 100, 100), True),
            ("node_source_c", "1", (20, 20, 10, 10), True),
        ])
        result, proof = nest_source_groups(xml)
        self.assertEqual(proof["nested_groups"], 0)
        self.assertEqual(proof["ambiguous_containment_left_on_layer"], ["node_source_c"])
        self.assertEqual(_world_rectangles(parsed(result)), _world_rectangles(parsed(xml)))

    def test_relative_or_transformed_groups_are_rejected(self):
        xml = document([("node_source_a", "1", (0, 0, 100, 100), True)])
        for attribute, value in [("relative", "1"), ("rotation", "15")]:
            tree = ET.fromstring(xml)
            cell = next(c for c in tree.iter("mxCell") if c.get("id") == "node_source_a")
            if attribute == "relative":
                cell.find("mxGeometry").set(attribute, value)
            else:
                cell.set("style", cell.get("style") + attribute + "=" + value + ";")
            with self.assertRaises(ValueError):
                nest_source_groups(ET.tostring(tree, encoding="unicode"))


if __name__ == "__main__":
    unittest.main()
