import json
import sys
import re
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree

class UltraCleanValidationExplorer(App):
    TITLE = "Validation Report"
    BINDINGS = [("q", "quit", "Quit"), ("r", "reload", "Reload")]

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = Path(file_path)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Tree(f"📁 {self.file_path.name}", id="json-tree")
        yield Footer()

    def on_mount(self) -> None:
        self.load_report()

    def natural_sort_key(self, s):
        """Sorts 'camera_ir (occ 2)' before 'camera_ir (occ 10)'."""
        match = re.search(r'^(.*?) \(occ (\d+)\)$', s)
        if match:
            return (match.group(1).lower(), int(match.group(2)))
        return (s.lower(), 0)

    def load_report(self) -> None:
        tree = self.query_one("#json-tree", Tree)
        tree.root.remove_children()
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.build_tree(data, tree.root)
        except Exception as e:
            tree.root.add(f"[bold red]Read Error:[/] {e}")

    def build_tree(self, data, parent_node, is_inside_shot=False):
        if isinstance(data, dict):
            # Natural sort for keys (e.g., camera_ir occ 1, occ 2...)
            sorted_items = sorted(data.items(), key=lambda x: self.natural_sort_key(x[0]))
            
            for key, value in sorted_items:
                # 1. REDUNDANCY REMOVAL
                if is_inside_shot and key == "shot":
                    continue
                if key == "nodes_count": # Removed as it is redundant with the 'nodes' label
                    continue

                # 2. LAZY HANDLING OF 'NODES'
                if key == "nodes" and isinstance(value, list):
                    count = len(value)
                    label = f"[bold yellow]▶ nodes[/] [dim]({count} items)[/]"
                    node = parent_node.add(label, expand=False)
                    node.data = {"lazy_content": value, "is_loaded": False}
                    continue

                if isinstance(value, (dict, list)):
                    # 3. FORMATTING IMPACTED_SHOTS
                    if key == "impacted_shots" and isinstance(value, list):
                        ids = []
                        for v in value:
                            if isinstance(v, dict): ids.append(str(v.get("shot", "?")))
                            else: ids.append(str(v))
                        
                        count = len(ids)
                        suffix = "..." if count > 8 else ""
                        preview = ", ".join(ids[:8])
                        label = f"[bold cyan]impacted_shots[/]([bold white]{count}[/]) [yellow][{preview}{suffix}][/]"
                    else:
                        label = f"[bold cyan]{key}[/]"
                    
                    new_node = parent_node.add(label, expand=False)
                    self.build_tree(value, new_node)
                else:
                    # Simple value
                    parent_node.add_leaf(f"[bold cyan]{key}[/]: [green]{value}[/]")

        elif isinstance(data, list):
            for i, item in enumerate(data):
                label = f"[magenta]index [{i}][/]"
                is_shot = False
                if isinstance(item, dict):
                    if "shot" in item:
                        label = f"Shot [bold yellow]{item['shot']}[/]"
                        is_shot = True
                    elif "rule" in item:
                        rule = str(item.get("rule", "")).split(":")[-1]
                        label = f"Rule [bold white]{rule}[/]"

                new_node = parent_node.add(label, expand=False)
                self.build_tree(item, new_node, is_inside_shot=is_shot)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        node = event.node
        custom_data = getattr(node, "data", None)
        
        if isinstance(custom_data, dict) and not custom_data.get("is_loaded", True):
            items = custom_data.get("lazy_content", [])
            node.set_label(f"[bold green]▼ nodes[/] [dim]({len(items)} items)[/]")
            
            if not items:
                node.add_leaf("[italic red](Empty list in JSON)[/]")
            else:
                for val in items:
                    node.add_leaf(f"[white]{val}[/]")
            
            custom_data["is_loaded"] = True

    def action_reload(self) -> None:
        self.load_report()

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "myreport.json"
    FinalApp = UltraCleanValidationExplorer(path)
    FinalApp.run()