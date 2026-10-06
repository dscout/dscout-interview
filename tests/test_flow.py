import unittest

from flow import flow_layout, live_flow, render_flow
from workflow import Build, Call, Deploy, Pipeline


class FlowTests(unittest.TestCase):
    def test_dependencies_not_list_order_define_levels(self):
        declaration = Pipeline(pool="example", tasks=[
            Deploy("release", needs=["zorch", "blerg"]),
            Build("blerg", needs=["greeb"]), Build("greeb"), Build("zorch"),
        ])
        output = render_flow(declaration)
        self.assertIn("stage 0: [greeb]   |   [zorch]", output)
        self.assertIn("stage 1: [blerg]", output)
        self.assertIn("stage 2: [release]", output)
        self.assertIn("greeb -> blerg", output)
        self.assertIn("pool: example", output)

    def test_nested_pipeline_is_visible(self):
        output = render_flow(Pipeline(tasks=[Call("component", Pipeline(tasks=[Build("zorch")]))]))
        self.assertIn("call component | pool: none", output)
        self.assertIn("[zorch]", output)

    def test_live_boxes_show_names_states_and_parallel_columns(self):
        declaration = Pipeline(tasks=[Build("zorch"), Build("greeb"),
                                      Build("blerg", needs=["greeb"])])
        output = live_flow(declaration, {"zorch": "building", "greeb": "finished (cache hit)"},
                           "abcdef123456789").plain
        self.assertIn("PR (tip SHA): abcdef123456", output)
        self.assertNotIn("Commit:", output)
        self.assertIn("building", output)
        self.assertIn("cached", output)
        self.assertTrue(any("zorch" in line and "greeb" in line for line in output.splitlines()))
        lines = output.splitlines()
        parent = next(line for line in lines if "greeb" in line)
        child = next(line for line in lines if "blerg" in line)
        self.assertEqual(parent.index("greeb"), child.index("blerg"))
        self.assertEqual(sum(line.count("▼") for line in lines if not line.startswith("Edges")), 1)

    def assert_rendered_edges(self, declaration):
        lines = live_flow(declaration, {}).plain.splitlines()[3:]
        positions, edges = flow_layout(declaration)
        directions = {"│": ((0, -1), (0, 1)), "─": ((-1, 0), (1, 0)),
                      "┌": ((1, 0), (0, 1)), "┐": ((-1, 0), (0, 1)),
                      "└": ((1, 0), (0, -1)), "┘": ((-1, 0), (0, -1))}
        rendered = []
        routes = {}
        for parent, (center, top) in positions.items():
            bottom = lines[top + 3]
            for x in range(center - 10, center + 10):
                if bottom[x] != "┬":
                    continue
                y = top + 4
                dx, dy = 0, 1
                visited = set()
                path = [(x, y)]
                while lines[y][x] != "▼":
                    self.assertNotIn((x, y, dx, dy), visited)
                    visited.add((x, y, dx, dy))
                    glyph = lines[y][x]
                    if glyph != "╳":
                        choices = directions[glyph]
                        dx, dy = next(direction for direction in choices
                                      if direction != (-dx, -dy))
                    x, y = x + dx, y + dy
                    path.append((x, y))
                child = next(name for name, (cx, cy) in positions.items()
                             if cy == y + 1 and cx - 10 <= x < cx + 10)
                rendered.append((parent, child))
                routes[parent, child] = path
        self.assertCountEqual(rendered, edges)
        self.assertEqual(sum(line.count("▼") for line in lines
                             if not line.startswith("Edges")), len(edges))
        return routes

    def assert_left_bypass(self, declaration, source, intermediate, sink):
        routes = self.assert_rendered_edges(declaration)
        positions, _ = flow_layout(declaration)
        direct = routes[source, sink]
        center, top = positions[intermediate]
        self.assertTrue(all(x < center - 10 for x, y in direct if top <= y < top + 4))
        self.assertLess(direct[0][0], routes[source, intermediate][0][0])
        self.assertLess(direct[-1][0], routes[intermediate, sink][-1][0])
        graph = live_flow(declaration, {}).plain.split("\nEdges")[0]
        self.assertNotIn("╳", graph)

    def test_starter_alignment_and_all_three_release_edges(self):
        declaration = Pipeline(tasks=[Build("zorch"), Build("greeb"),
                                      Build("blerg", needs=["greeb"]),
                                      Deploy("release", needs=["zorch", "greeb", "blerg"])])
        positions, edges = flow_layout(declaration)
        self.assertLess(positions["zorch"][0], positions["greeb"][0])
        self.assertEqual(positions["blerg"][0], positions["greeb"][0])
        self.assertLess(positions["zorch"][0], positions["release"][0])
        self.assertLess(positions["release"][0], positions["greeb"][0])
        self.assertIn(("greeb", "release"), edges)
        self.assert_left_bypass(declaration, "greeb", "blerg", "release")

    def test_left_bypass_uses_geometry_not_names_or_dependency_order(self):
        for needs in (["peer", "origin", "middle"], ["middle", "origin", "peer"]):
            with self.subTest(needs=needs):
                declaration = Pipeline(tasks=[
                    Deploy("peer"), Deploy("origin"),
                    Deploy("middle", needs=["origin"]), Deploy("sink", needs=needs),
                ])
                self.assert_left_bypass(declaration, "origin", "middle", "sink")

    def test_arbitrary_branching_and_skip_level_edges(self):
        declaration = Pipeline(tasks=[
            Deploy("sink", needs=["root", "left", "deep", "right"]),
            Deploy("deep", needs=["left"]),
            Deploy("left", needs=["root"]),
            Deploy("right", needs=["root"]),
            Call("root", Pipeline()),
        ])
        self.assert_rendered_edges(declaration)
        output = live_flow(declaration, {}).plain
        self.assertIn("root ↗", output)
        self.assertIn("╳", output)

    def test_routes_preserve_edges_across_varied_dags(self):
        import random

        randomizer = random.Random(1)
        for sample in range(40):
            declaration = Pipeline(tasks=[
                Deploy(f"t{index}", needs=[f"t{parent}" for parent in range(index)
                                          if randomizer.random() < 0.3])
                for index in range(6)
            ])
            with self.subTest(sample=sample):
                self.assert_rendered_edges(declaration)

    def test_independent_tasks_have_no_connectors(self):
        output = live_flow(Pipeline(tasks=[Deploy("one"), Deploy("two")]), {}).plain
        graph = output.split("\nEdges")[0]
        self.assertNotIn("▼", graph)
        self.assertNotIn("┬", graph)
        self.assertNotIn("↓", graph)

    def test_live_status_styles_and_headers(self):
        declaration = Pipeline(pool="example", tasks=[
            Deploy("one"), Deploy("two"), Deploy("three"), Deploy("four"),
        ])
        output = live_flow(declaration, {"one": "failed", "two": "finished (cache hit)",
                                         "three": "finished", "four": "deploying"})
        self.assertIn("PR (tip SHA): select a PR", output.plain)
        self.assertNotIn("select a commit", output.plain)
        self.assertIn("Pool: example", output.plain)
        for name, style in (("one", "red"), ("two", "cyan"), ("three", "green"),
                            ("four", "bold yellow")):
            start = output.plain.index(name)
            self.assertTrue(any(span.start <= start < span.end and span.style == style
                                for span in output.spans))

    def test_wide_labels_use_display_cell_width(self):
        from rich.cells import cell_len

        output = live_flow(Pipeline(tasks=[Deploy("任务"), Deploy("longer task name")]), {}).plain
        lines = output.splitlines()
        label_row = next(line for line in lines if "任务" in line)
        border_row = next(line for line in lines if "┌" in line)
        self.assertEqual(cell_len(label_row), cell_len(border_row))

    def test_empty_pipeline(self):
        self.assertIn("(no tasks)", render_flow(Pipeline()))
        self.assertIn("(no tasks)", live_flow(Pipeline(), {}).plain)
