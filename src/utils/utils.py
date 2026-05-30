"""
utils.py - Ratgeber utility functions

Low level string and other utility functions

copyright (c) 2026 Always Up Networks. MIT License.
"""

import re

def strip_markdown(text: str) -> str:
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s', '', text)
    return text.strip()

def draw_node(node, width=22):
        """
        Render a single deployment node as an ASCII box.

        Example input:
        {
            "name": "Node A",
            "role": "Primary",
            "state": "Active"
        }
        """

        lines = [
            node["name"],
            f"Role: {node['role']}",
            f"State: {node['state']}"
        ]

        border = "+" + "-" * width + "+"

        output = [border]

        for line in lines:
            truncated = line[:width - 1]
            output.append("| " + truncated.ljust(width - 1) + "|")

        output.append(border)
        return "\n".join(output)

def draw_node_lines(node, width=22):
    """
    Return a node as a list of ASCII lines.
    """

    lines = [
        node["name"],
        f"Role: {node['role']}",
        f"State: {node['state']}"
    ]

    border = "+" + "-" * width + "+"

    output = [border]

    for line in lines:
        output.append("| " + line.ljust(width - 1) + "|")

    output.append(border)
    return output

def draw_topology(topology_json: dict, spacing=5):
    """
       Render multiple topology nodes horizontally.
    """
    nodes = topology_json["nodes"]
    links = topology_json.get("links", [])

    rendered_nodes = [draw_node_lines(node) for node in nodes]

    for row_parts in zip(*rendered_nodes):
        print((" " * spacing).join(row_parts))

    if links:
        print(draw_links(links, nodes))

def draw_links(links, nodes, width=22, spacing=5):
    """
    Draw horizontal link arrows between nodes.

    Example output:

               <============ DRBD sync (Protocol C) ============>

    Assumptions:
    - Nodes are rendered horizontally in array order
    - Each node box width is width + 2 border chars
    - spacing chars exist between boxes
    """

    box_width = width + 2

    # Map node name -> index
    node_positions = {
        node["name"]: index
        for index, node in enumerate(nodes)
    }

    # Total rendered width occupied by one node slot
    slot_width = box_width + spacing
    rendered_lines = []
    for link in links:
        source = link["from"]
        target = link["to"]

        source_index = node_positions[source]
        target_index = node_positions[target]

        # Center X coordinate of each node
        source_center = (source_index * slot_width) + (box_width // 2)
        target_center = (target_index * slot_width) + (box_width // 2)

        left = min(source_center, target_center)
        right = max(source_center, target_center)
        label = f"{link['type']} (Protocol {link['protocol']})"
        arrow_body_width = right - left - 2

        if arrow_body_width < len(label) + 2:
            arrow_body_width = len(label) + 2

        remaining = arrow_body_width - len(label)
        left_fill = remaining // 2
        right_fill = remaining - left_fill

        arrow = (
                "<"
                + "=" * left_fill
                + " "
                + label
                + " "
                + "=" * right_fill
                + ">"
        )

        arrow_start = left - (len(arrow) // 2) + (arrow_body_width // 2)
        line = (" " * max(0, arrow_start)) + arrow
        rendered_lines.append(line)

    return "\n".join(rendered_lines)


import json

def clean_llm_response(response:str) -> str:
    """
    Remove Mistral's topology intro line
    """
    lines = response.split('\n')
    lines = [l for l in lines if not any(phrase in l.lower() for phrase in [
        'json representation',
        'here is the topology',
        'here is a topology',
        'topology json',
        'following topology'
    ])]
    return '\n'.join(lines).strip()

def extract_topology(response: str):
    """
    Extract topology JSON block from Mistral response.
    Returns (clean_text, topology_dict) or (response, None) if no topology found.
    """
    pattern = r'```topology\s*(.*?)\s*```'
    match = re.search(pattern, response, re.DOTALL)

    if not match:
        return response, None

    json_str = match.group(1)
    clean_text = response[:match.start()].strip()
    clean_text = clean_llm_response(clean_text)

    try:
        topology = json.loads(json_str)
        return clean_text, topology
    except json.JSONDecodeError:
        return response, None


# Example usage
nodes_example = [
    {
        "name": "Node A",
        "role": "Primary",
        "state": "Active"
    },
    {
        "name": "Node B",
        "role": "Secondary",
        "state": "Standby"
    },
    {
        "name": "Node C",
        "role": "Replica",
        "state": "Active"
    }
]

if __name__ == "__main__":
    test_topology = {
        "nodes": nodes_example,
        "links": [
            {"from": "Node A", "to": "Node B", "type": "DRBD sync", "protocol": "C"},
            {"from": "Node B", "to": "Node C", "type": "DRBD sync", "protocol": "C"}
        ]
    }
    draw_topology(test_topology)