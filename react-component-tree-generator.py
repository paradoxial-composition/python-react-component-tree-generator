import os
import re
import sys
import argparse
from collections import defaultdict

def get_component_files(directory, include_dirs=None):
    """
    Recursively find all .jsx and .tsx files in the directory.
    If include_dirs is provided, only return files whose path is within one of those directories.
    """
    component_files = []
    base_abs = os.path.abspath(directory)
    if include_dirs:
        # Convert include_dirs to absolute paths relative to base_abs if needed.
        include_dirs_abs = []
        for d in include_dirs:
            if os.path.isabs(d):
                include_dirs_abs.append(os.path.abspath(d))
            else:
                include_dirs_abs.append(os.path.join(base_abs, d))
    else:
        include_dirs_abs = None

    for root, _, files in os.walk(directory):
        if include_dirs_abs:
            # Check if the current root is within any of the include directories.
            in_include = any(os.path.abspath(root).startswith(os.path.abspath(inc)) for inc in include_dirs_abs)
            if not in_include:
                continue
        for file in files:
            if file.endswith(('.jsx', '.tsx')):
                component_files.append(os.path.join(root, file))
    return component_files

def extract_component_name(file_path):
    """Assume the component name is the file name without extension."""
    return os.path.splitext(os.path.basename(file_path))[0]

def extract_imported_ignored_components(file_path, ignore_libs):
    """
    Extract component names imported from libraries that should be ignored.
    Handles both default and named imports.
    """
    ignored = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Default imports: e.g. import Component from 'lib'
        default_imports = re.findall(r"import\s+([A-Z][a-zA-Z0-9_]*)\s+from\s+['\"]([^'\"]+)['\"]", content)
        for comp, module in default_imports:
            if module in ignore_libs:
                ignored.add(comp)
        # Named imports: e.g. import { CompA, CompB as Alias } from 'lib'
        named_imports = re.findall(r"import\s*\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]", content)
        for comps, module in named_imports:
            if module in ignore_libs:
                for comp in comps.split(','):
                    comp_name = comp.strip().split(' as ')[0].strip()
                    if comp_name:
                        ignored.add(comp_name)
    except Exception as e:
        print(f"Error reading imports in {file_path}: {e}")
    return ignored

def extract_used_components(file_path, ignore_libs):
    """
    Extract used component names by looking for JSX tags starting with an uppercase letter,
    and then ignore those imported from libraries in ignore_libs.
    """
    used = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        matches = re.findall(r'<([A-Z][a-zA-Z0-9_]*)', content)
        used.update(matches)
        ignored = extract_imported_ignored_components(file_path, ignore_libs)
        used = used - ignored
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return used

def build_component_graph(directory, ignore_libs, project_only, include_dirs):
    """
    Build a graph where keys are component names and values are sets of component names used within them.
    If project_only is True, only add used components that are defined in the project.
    Only files in include_dirs (if provided) are considered.
    """
    files = get_component_files(directory, include_dirs)
    graph = defaultdict(set)
    # Map each file to its component name.
    file_to_component = {file: extract_component_name(file) for file in files}
    # Only consider components that exist in our project.
    component_set = set(file_to_component.values())
    
    for file, comp in file_to_component.items():
        used = extract_used_components(file, ignore_libs)
        for used_comp in used:
            if not project_only or used_comp in component_set:
                graph[comp].add(used_comp)
    return graph

def find_roots(graph):
    """
    Find root components (not used by any other component).
    """
    in_degree = defaultdict(int)
    for node in graph:
        in_degree[node]  # Ensure key exists
    for parent in graph:
        for child in graph[parent]:
            in_degree[child] += 1
    roots = [node for node, deg in in_degree.items() if deg == 0]
    return roots

def generate_markdown_tree(graph, node, indent=0, visited=None):
    """
    Recursively generate a markdown nested list for the tree.
    'visited' helps avoid infinite loops if there are cycles.
    """
    if visited is None:
        visited = set()
    md = "  " * indent + f"- {node}\n"
    if node in visited:
        return md
    visited.add(node)
    for child in sorted(graph.get(node, [])):
        md += generate_markdown_tree(graph, child, indent + 1, visited.copy())
    return md

def main(directory, ignore_libs, project_only, include_dirs):
    graph = build_component_graph(directory, ignore_libs, project_only, include_dirs)
    roots = find_roots(graph)
    md_lines = [
        "---",
        "title: Component Tree",
        "markmap:",
        "  colorFreezeLevel: 4",
        "---",
        ""
    ]
    
    for root in sorted(roots):
        md_lines.append(f"## {root}")
        md_lines.append("")
        md_lines.append(generate_markdown_tree(graph, root))
    
    md_content = "\n".join(md_lines)
    
    with open("componentsTree.mm.md", "w", encoding="utf-8") as f:
        f.write(md_content)
    print("Markdown file 'componentsTree.mm.md' generated successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a component tree for a React project.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory of the React project")
    parser.add_argument("--ignore-libs", nargs="*", default=[], help="List of library names to ignore components from")
    parser.add_argument("--project-only", action="store_true", help="Only include components defined in the project")
    # Use '--in' flag to only include files from specified directories.
    parser.add_argument("--in", dest="include_dirs", nargs="*", default=None,
                        help="List of directories (relative to project directory) to include, e.g., --in ./src/components ./src/pages")
    args = parser.parse_args()
    
    main(args.directory, args.ignore_libs, args.project_only, args.include_dirs)
