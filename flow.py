"""Text view of declared dependencies, independent of task list order."""

from workflow import Call, validate


def flow_levels(pipeline):
    validate(pipeline)
    remaining = {task.name: task for task in pipeline.tasks}
    done = set()
    levels = []
    while remaining:
        ready = [task for task in remaining.values() if set(task.needs) <= done]
        levels.append(ready)
        for task in ready:
            del remaining[task.name]
        done.update(task.name for task in ready)
    return levels


def flow_layout(pipeline, width=20):
    levels = flow_levels(pipeline)
    positions = {}
    edges = [(parent, task.name) for level in levels for task in level
             for parent in dict.fromkeys(task.needs)]
    ranks = {task.name: rank for rank, level in enumerate(levels) for task in level}
    y = 0
    for rank, level in enumerate(levels):
        desired = {}
        for index, task in enumerate(level):
            parents = {positions[name][0] for name in task.needs}
            desired[task.name] = (2 * round(sum(parents) / len(parents) / 2) if parents
                                  else 2 * (width // 4) + index * (width + 6))
        occupied = []
        for task in sorted(level, key=lambda task: desired[task.name]):
            center = desired[task.name]
            while any(abs(center - other) < width + 6 for other in occupied):
                center += width + 6
            positions[task.name] = (center, y)
            occupied.append(center)
        touching = [edge for edge in edges
                    if ranks[edge[0]] == rank or ranks[edge[1]] == rank + 1]
        y += 4 + max(3, len(touching) + 1)
    return positions, edges


def live_flow(pipeline, states, commit=None):
    from rich.cells import cell_len
    from rich.text import Text

    levels = flow_levels(pipeline)
    labels = {}
    statuses = {}
    styles = {}
    for level in levels:
        for task in level:
            status = states.get(task.name, "pending")
            if task.name not in states and task.__class__.__name__ == "Deploy":
                status = states.get("release", "pending")
            status = status.replace("finished (cache hit)", "cached").replace("finished", "done")
            statuses[task.name] = status
            styles[task.name] = ("red" if status in ("failed", "blocked") else
                                 "cyan" if "cache" in status else
                                 "green" if status == "done" else
                                 "bold yellow" if status in ("building", "deploying") else "dim")
            labels[task.name] = task.name + (" ↗" if isinstance(task, Call) else "")
    width = max([20] + [cell_len(value) + 4 for value in labels.values()] +
                [cell_len(value) + 4 for value in statuses.values()] +
                [2 * len(task.needs) + 4 for level in levels for task in level])
    positions, edges = flow_layout(pipeline, width)
    outgoing = {name: [] for name in positions}
    incoming = {name: [] for name in positions}
    for edge in edges:
        outgoing[edge[0]].append(edge)
        incoming[edge[1]].append(edge)
    width = max(width, max((2 * len(value) + 4 for value in outgoing.values()), default=0))
    width += width % 2
    positions, edges = flow_layout(pipeline, width)
    # Even source columns and odd target columns keep routes from sharing vertical runs.
    source_ports = {}
    target_ports = {}
    for name, children in outgoing.items():
        children.sort(key=lambda edge: positions[edge[1]])
        for index, edge in enumerate(children):
            source_ports[edge] = positions[name][0] + 2 * (index - len(children) // 2)
    for name, parents in incoming.items():
        parents.sort(key=lambda edge: positions[edge[0]])
        for index, edge in enumerate(parents):
            target_ports[edge] = positions[name][0] + 2 * (index - len(parents) // 2) + 1

    gap_rows = {}
    for rank, level in enumerate(levels[:-1]):
        top = positions[level[0].name][1] + 4
        next_top = positions[levels[rank + 1][0].name][1]
        touching = [edge for edge in edges
                    if positions[edge[0]][1] == top - 4 or positions[edge[1]][1] == next_top]
        for index, edge in enumerate(touching):
            gap_rows[edge, rank] = top + index
    ranks = {task.name: rank for rank, level in enumerate(levels) for task in level}
    lines = {}
    arrows = set()
    trunks = []

    def segment(edge, start, end):
        x, y = start
        dx = (end[0] > x) - (end[0] < x)
        dy = (end[1] > y) - (end[1] < y)
        while (x, y) != end:
            nx, ny = x + dx, y + dy
            forward, backward = (2, 8) if dx > 0 else (8, 2) if dx < 0 else (4, 1)
            for point, direction in (((x, y), forward), ((nx, ny), backward)):
                cell = lines.setdefault(point, {})
                cell[edge] = cell.get(edge, 0) | direction
            x, y = nx, ny

    for edge in edges:
        parent, child = edge
        sx, tx = source_ports[edge], target_ports[edge]
        sy, ty = positions[parent][1] + 4, positions[child][1] - 1
        first, last = ranks[parent], ranks[child] - 1
        start_row, end_row = gap_rows[edge, first], gap_rows[edge, last]
        if first == last:
            points = [(sx, sy), (sx, end_row), (tx, end_row), (tx, ty)]
        else:
            obstacles = [(x - width // 2, x - width // 2 + width - 1)
                         for x, y in positions.values() if sy <= y < ty]
            candidates = [sx] + [x for left, right in obstacles for x in (left - 2, right + 2)]
            candidates += [max(x for x, y in positions.values()) + width + 2 * index
                           for index in range(len(edges) + 1)]
            candidates.sort(key=lambda x: abs(x - sx) + abs(x - tx))
            trunk = next(x for x in candidates
                         if not any(left <= x <= right for left, right in obstacles)
                         and x not in target_ports.values()
                         and not any(x == port and other != edge
                                     for other, port in source_ports.items())
                         and not any(x == used and sy <= bottom and ty >= top
                                     for used, top, bottom in trunks))
            trunks.append((trunk, sy, ty))
            points = [(sx, sy), (sx, start_row), (trunk, start_row),
                      (trunk, end_row), (tx, end_row), (tx, ty)]
        for start, end in zip(points, points[1:]):
            segment(edge, start, end)
        cell = lines.setdefault((sx, sy), {})
        cell[edge] = cell.get(edge, 0) | 1
        arrows.add((tx, ty))

    glyphs = {1: "│", 2: "─", 4: "│", 8: "─", 5: "│", 10: "─",
              3: "└", 6: "┌", 9: "┘", 12: "┐"}
    grid = {point: ("▼" if point in arrows else
                    "╳" if len(owners) > 1 else glyphs[next(iter(owners.values()))], "dim")
            for point, owners in lines.items()}
    box_rows = {}
    for name, (center, y) in positions.items():
        left = center - width // 2
        top = list("┌" + "─" * (width - 2) + "┐")
        bottom = list("└" + "─" * (width - 2) + "┘")
        for edge in incoming[name]:
            top[target_ports[edge] - left] = "┴"
        for edge in outgoing[name]:
            bottom[source_ports[edge] - left] = "┬"

        def centered(value):
            padding = width - 2 - cell_len(value)
            return "│" + " " * (padding // 2) + value + " " * (padding - padding // 2) + "│"

        for offset, row in enumerate(("".join(top), centered(labels[name]),
                                      centered(statuses[name]), "".join(bottom))):
            box_rows[left, y + offset] = (row, styles[name])
    output = Text()
    output.append(f"Commit: {commit[:12] if commit else 'select a commit'}\n", style="bold")
    output.append(f"Pool: {pipeline.pool or 'none'}\n\n", style="dim")
    if positions:
        left = min([x - width // 2 for x, y in positions.values()] + [x for x, y in grid])
        right = max([x - width // 2 + width for x, y in positions.values()] + [x + 1 for x, y in grid])
        for y in range(max(y for x, y in positions.values()) + 4):
            row = Text()
            x = left
            while x < right:
                if (x, y) in box_rows:
                    value, style = box_rows[x, y]
                    row.append(value, style=style)
                    x += width
                else:
                    value, style = grid.get((x, y), (" ", ""))
                    row.append(value, style=style)
                    x += 1
            row.rstrip()
            output.append_text(row)
            output.append("\n")
    else:
        output.append("(no tasks)\n", style="dim")
    output.append("\nEdges are declared dependencies; ▼ points to the dependent task.", style="dim")
    return output


def render_flow(pipeline, label="pipeline", depth=0):
    validate(pipeline)
    indent = "  " * depth
    lines = [f"{indent}{label} | pool: {pipeline.pool or 'none'}"]
    remaining = {task.name: task for task in pipeline.tasks}
    done = set()
    stage = 0
    while remaining:
        ready = [task for task in remaining.values() if set(task.needs) <= done]
        lines.append(f"{indent}  stage {stage}: " + "   |   ".join(
            f"[{task.name}]" for task in ready))
        for task in ready:
            if task.needs:
                lines.append(f"{indent}    {', '.join(task.needs)} -> {task.name}")
            if isinstance(task, Call):
                lines.extend(render_flow(task.pipeline, f"call {task.name}", depth + 2).splitlines())
            del remaining[task.name]
        done.update(task.name for task in ready)
        stage += 1
    if not pipeline.tasks:
        lines.append(f"{indent}  (no tasks)")
    return "\n".join(lines)
