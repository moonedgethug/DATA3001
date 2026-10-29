"""One-time, source-only layout migration. Never reads trajectory data."""
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = ROOT / "src/data3001/modelling"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if not (BASE / "markov.py").is_file() or (BASE / "markov_models").exists():
        raise RuntimeError("Expected the original flat source layout; do not rerun this migration.")
    if (HERE / "before").exists():
        raise RuntimeError("Migration already started; inspect its receipt before recovery.")
    sources = {p.stem: p.read_text() for p in BASE.glob("*.py") if p.name != "__init__.py"}
    before = {}
    protected = list((ROOT / "src/data3001").rglob("*.py"))
    protected += list(BASE.glob("*.cpp"))
    protected += [ROOT / p for p in (
        "README.md", "docs/architecture.md", "docs/markov_results.md",
        "docs/modelling_round1_plan.md", "pyproject.toml", ".gitignore")]
    for p in protected:
        relative = p.relative_to(ROOT)
        data = p.read_bytes()
        snapshot = HERE / "before" / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(data)
        before[str(relative)] = digest(data)

    mapping = {}
    for name in sources:
        if name == "experiment":
            family = "common"
        elif name in ("markov_scoring", "markov_position_scores"):
            family = "common"
        elif name.startswith("continuous") or name == "run_continuous":
            family = "continuous_models"
        elif name.startswith("markov") or name.startswith("run_markov"):
            family = "markov_models"
        else:
            family = "baselines"
        mapping[name] = f"data3001.modelling.{family}.{name}"

    extractions = []
    redirects = {}

    def extract(owner, names, destination, header):
        text = sources[owner]
        lines = text.splitlines(keepends=True)
        nodes = {n.name: n for n in ast.parse(text).body
                 if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        pieces, spans = [], []
        for name in names:
            n = nodes[name]
            start = min([n.lineno] + [d.lineno for d in n.decorator_list]) - 1
            pieces.append("".join(lines[start:n.end_lineno]))
            spans.append((start, n.end_lineno))
            redirects[(owner, name)] = f"data3001.modelling.common.{destination}"
            extractions.append({"old_module": owner, "symbol": name,
                                "new_module": redirects[(owner, name)],
                                "original_ast_sha256": digest(ast.dump(n).encode())})
        for start, end in sorted(spans, reverse=True):
            del lines[start:end]
        sources[owner] = "".join(lines)
        # Keep re-exports for historical callers. All active imports are routed below.
        sources[owner] += f"\nfrom data3001.modelling.common.{destination} import {', '.join(names)}\n"
        return header + "\n\n" + "\n\n".join(pieces) + "\n"

    common = {}
    common["runtime"] = extract("run_blend_cv", ["ReadOnlyInputs", "save_frame", "save_json"], "runtime",
        '"""Shared read guards and immutable run I/O; no model fitting."""\n'
        'import json\nimport os\nfrom pathlib import Path\nfrom data3001.paths import file_sha256')
    common["runtime"] += extract("run_neighbourhood",
        ["validate_parent_receipt", "verified_run", "_source_hashes", "_seal"], "runtime", "")
    common["probability"] = extract("evaluate", ["score_distribution", "check_scoring"], "probability",
        '"""Shared categorical probability scores, including unresolved mass."""\nimport numpy as np')
    common["geometry"] = extract("neighbourhood", ["EndpointMapper"], "geometry",
        '"""Shared endpoint geometry; mapper sentinels are distinct from model states."""\n'
        'from dataclasses import dataclass\nimport json\nimport numpy as np\n'
        'import shapely as sh\nfrom shapely.geometry import shape\n'
        'from data3001.preprocessing.prep_core import cells\nOUTSIDE = -2\nUNRESOLVED = -1')
    common["geometry"] += extract("run_markov_position", ["mapper_for"], "geometry", "")
    common["plotting"] = extract("markov_report", ["markdown_table", "map_svg", "_rings"], "plotting",
        '"""Shared static map and table rendering; no fitting or trajectory access."""\n'
        'from html import escape\nimport numpy as np')

    def rewrite(text):
        # Split imports when a shared symbol has moved out of a model runner.
        lines = text.splitlines(keepends=True)
        edits = []
        for n in ast.walk(ast.parse(text)):
            if not isinstance(n, ast.ImportFrom) or not n.module:
                continue
            prefix = "data3001.modelling."
            if not n.module.startswith(prefix):
                continue
            owner = n.module[len(prefix):]
            if owner not in mapping:
                continue
            groups = {}
            for alias in n.names:
                target = redirects.get((owner, alias.name), mapping[owner])
                groups.setdefault(target, []).append(alias.name + (f" as {alias.asname}" if alias.asname else ""))
            indent = " " * n.col_offset
            replacement = "\n".join(indent + f"from {target} import {', '.join(names)}"
                                    for target, names in groups.items()) + "\n"
            edits.append((n.lineno - 1, n.end_lineno, replacement))
        for start, end, replacement in sorted(edits, reverse=True):
            lines[start:end] = [replacement]
        text = "".join(lines)
        for old, new in sorted(mapping.items(), key=lambda pair: -len(pair[0])):
            text = re.sub(r"data3001\.modelling\." + re.escape(old) + r"\b", new, text)
            oldpath = f"src/data3001/modelling/{old}.py"
            newpath = "src/" + new.replace(".", "/") + ".py"
            text = text.replace(oldpath, newpath)
        return text

    for family in ("common", "baselines", "markov_models", "continuous_models", "_compat"):
        folder = BASE / family
        folder.mkdir()
        (folder / "__init__.py").write_text(f'"""{family.replace("_", " ").capitalize()} modules; import explicit submodules."""\n')
    for name, text in sources.items():
        target = ROOT / ("src/" + mapping[name].replace(".", "/") + ".py")
        text = rewrite(text)
        if name == "showcase":
            text = text.replace('Path(__file__).with_name("assets")', 'Path(__file__).resolve().parents[1] / "assets"')
        if name == "markov_neighbour_native":
            text = text.replace('from pathlib import Path', 'from pathlib import Path\nfrom data3001.paths import project_paths')
            text = text.replace("Path(__file__).resolve().parents[3]/'.superpowers/native/neighbour_scoring.dylib'",
                                "project_paths().root/'.superpowers/native/neighbour_scoring.dylib'")
        # Re-export bindings must exist before a script enters its main guard.
        tree = ast.parse(text)
        lines = text.splitlines(keepends=True)
        late = []
        for n in tree.body:
            if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("data3001.modelling.common."):
                if n.lineno > len(lines) - 8:
                    late.append((n.lineno - 1, n.end_lineno))
        imports = []
        for start, end in sorted(late, reverse=True):
            imports[0:0] = lines[start:end]
            del lines[start:end]
        text = "".join(lines)
        if imports:
            tree = ast.parse(text)
            insert = tree.body[0].end_lineno if isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) else 0
            lines = text.splitlines(keepends=True)
            lines[insert:insert] = imports
            text = "".join(lines)
        ast.parse(text)
        target.write_text(text)
        shim = ('"""Compatibility entry; implementation: ' + mapping[name] + '."""\n'
                'if __name__ == "__main__":\n'
                '    from runpy import run_module\n'
                f'    run_module("{mapping[name]}", run_name="__main__")\n'
                'else:\n'
                '    from importlib import import_module\n'
                '    import sys\n'
                f'    sys.modules[__name__] = import_module("{mapping[name]}")\n')
        (BASE / "_compat" / f"{name}.py").write_text(shim)
        (BASE / f"{name}.py").unlink()
    for name, text in common.items():
        text = rewrite(text)
        ast.parse(text)
        (BASE / "common" / f"{name}.py").write_text(text)
    (BASE / "_neighbour_scoring.cpp").rename(BASE / "markov_models" / "_neighbour_scoring.cpp")
    (BASE / "__init__.py").write_text(
        '"""Model families and shared services. Flat historical imports remain supported.\n\n'
        'New code imports common, baselines, markov_models or continuous_models.\n'
        'The package-local compatibility path contains forwarding modules only;\n'
        'it neither edits sys.path nor imports optional neural dependencies.\n'
        '"""\nfrom pathlib import Path\n\n'
        '__path__.append(str(Path(__file__).with_name("_compat")))\n')
    # Active package entry points outside modelling also use the canonical names.
    for p in (ROOT / "src/data3001").rglob("*.py"):
        if p.is_relative_to(BASE):
            continue
        old = p.read_text()
        new = rewrite(old)
        if new != old:
            p.write_text(new)
    receipt = {"scope": "source layout only; no dataset, model fit or historical run mutation",
               "before_sha256": before, "module_map": mapping, "extracted_symbols": extractions}
    (HERE / "migration.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"moved_modules": len(mapping), "shared_extractions": len(extractions),
                      "snapshot_files": len(before), "receipt": str(HERE / "migration.json")}))


if __name__ == "__main__":
    main()
