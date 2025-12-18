import os
import ast
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

IGNORE_DIRS = {'.git', '.cursor', '__pycache__', 'node_modules', '.pytest_cache', 'venv', 'env', '.idea', '.vscode'}

def analyze_directory(root_path):
    stats = {}
    
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        rel_root = os.path.relpath(root, root_path)
        if rel_root == ".":
            rel_root = ""
            
        current_stats = {
            "file_count": 0,
            "last_mod": 0,
            "files": []
        }
        
        for f in files:
            full_path = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(full_path)
                current_stats["file_count"] += 1
                current_stats["last_mod"] = max(current_stats["last_mod"], mtime)
                current_stats["files"].append(f)
            except OSError:
                pass
                
        stats[rel_root] = current_stats

    return stats

def get_imports(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
            else:
                # Relative import
                imports.append("." * node.level)
    return imports

def analyze_code_usage(src_path):
    dependency_graph = defaultdict(set)
    all_modules = set()
    
    for root, dirs, files in os.walk(src_path):
        for f in files:
            if f.endswith(".py"):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, src_path)
                module_name = "src." + rel_path.replace(os.sep, ".").replace(".py", "")
                if module_name.endswith(".__init__"):
                    module_name = module_name[:-9]
                
                all_modules.add(module_name)
                
                imports = get_imports(full_path)
                for imp in imports:
                    if imp.startswith("src."):
                        dependency_graph[imp].add(module_name)
                    elif imp.startswith("."):
                        # Resolve relative imports (simplified)
                        # This is tricky without full context, but we can approximate
                        pass

    return all_modules, dependency_graph

def format_date(timestamp):
    if timestamp == 0:
        return "N/A"
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')

print("--- DIRECTORY ANALYSIS ---")
root_dir = os.getcwd()
stats = analyze_directory(root_path=root_dir)

# Group by top-level
top_level_stats = defaultdict(lambda: {"count": 0, "max_mtime": 0, "subdirs": 0})
for path, data in stats.items():
    if not path: continue
    top_level = path.split(os.sep)[0]
    top_level_stats[top_level]["count"] += data["file_count"]
    top_level_stats[top_level]["max_mtime"] = max(top_level_stats[top_level]["max_mtime"], data["last_mod"])
    top_level_stats[top_level]["subdirs"] += 1

print(f"{'Directory':<25} | {'Files':<5} | {'Last Mod':<10}")
print("-" * 45)
for dir_name, data in sorted(top_level_stats.items()):
    print(f"{dir_name:<25} | {data['count']:<5} | {format_date(data['max_mtime']):<10}")

print("\n--- DOCS ANALYSIS ---")
docs_path = os.path.join(root_dir, "docs")
if os.path.exists(docs_path):
    doc_stats = analyze_directory(docs_path)
    print(f"{'Subdirectory':<30} | {'Files':<5} | {'Last Mod':<10}")
    print("-" * 50)
    for path, data in sorted(doc_stats.items()):
        if path:
            print(f"{path:<30} | {data['file_count']:<5} | {format_date(data['last_mod']):<10}")

print("\n--- CODE USAGE (src/) ---")
src_path = os.path.join(root_dir, "src")
if os.path.exists(src_path):
    all_modules, deps = analyze_code_usage(src_path)
    
    # Identify modules used by routes.py
    routes_deps = set()
    # We manually added src.api.routes to the graph in our mental model, but let's check what imports WHAT
    # Actually, we want to know what is imported BY the app.
    # The dependency graph keys are the IMPORTED modules, values are IMPORTERS.
    
    # Let's find orphans: modules that are never imported by another src module
    # (Note: entry points won't be imported, so they will look like orphans)
    
    imported_modules = set(deps.keys())
    orphans = []
    for mod in all_modules:
        if mod not in imported_modules:
            orphans.append(mod)
            
    print(f"Total Modules: {len(all_modules)}")
    print(f"Modules imported by others: {len(imported_modules)}")
    print(f"Potential Entry Points / Orphans ({len(orphans)}):")
    for o in sorted(orphans):
        print(f"  - {o}")

