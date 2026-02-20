"""Notebook syntax and structure validation tests."""
import ast
import json
import os
import pytest


def load_notebook(path):
    """Load a notebook and return its cells."""
    with open(path) as f:
        nb = json.load(f)
    return nb.get("cells", [])


def get_notebook_paths(project_root):
    """Return paths to all notebooks in the project."""
    paths = []
    for candidate in [
        os.path.join(project_root, "apex_nextload_demo.ipynb"),
        os.path.join(project_root, "notebooks", "freight_360_demo.ipynb"),
    ]:
        if os.path.isfile(candidate):
            paths.append(candidate)
    return paths


@pytest.mark.notebook
class TestNotebookStructure:
    """Validate notebook cell structure."""

    def test_notebooks_exist(self, project_root):
        paths = get_notebook_paths(project_root)
        assert len(paths) > 0, "No notebooks found in project"

    def test_no_empty_cells(self, project_root):
        issues = []
        for path in get_notebook_paths(project_root):
            cells = load_notebook(path)
            for i, cell in enumerate(cells):
                source = "".join(cell.get("source", []))
                if source.strip() == "":
                    issues.append(f"{os.path.basename(path)}:cell_{i}")
        assert len(issues) == 0, f"Empty cells found: {issues}"

    def test_has_markdown_cells(self, project_root):
        for path in get_notebook_paths(project_root):
            cells = load_notebook(path)
            md_cells = [c for c in cells if c.get("cell_type") == "markdown"]
            assert len(md_cells) > 0, f"{os.path.basename(path)} has no markdown cells"


@pytest.mark.notebook
class TestNotebookPythonSyntax:
    """Validate Python cells parse correctly."""

    def test_python_cells_parse(self, project_root):
        issues = []
        sql_prefixes = ("--", "SELECT", "INSERT", "CREATE", "DROP", "ALTER",
                        "USE ", "SHOW ", "DESCRIBE ", "GRANT ", "CALL ",
                        "TRUNCATE", "DELETE", "UPDATE", "MERGE", "WITH ")
        for path in get_notebook_paths(project_root):
            cells = load_notebook(path)
            for i, cell in enumerate(cells):
                if cell.get("cell_type") != "code":
                    continue
                source = "".join(cell.get("source", []))
                stripped = source.strip()
                # Skip cells that are SQL magic or shell commands
                if stripped.startswith(("%%sql", "%%sh", "!", "%")):
                    continue
                # Skip empty cells
                if stripped == "":
                    continue
                # Skip SQL cells (Snowflake notebooks store SQL as code cells)
                if stripped.upper().startswith(sql_prefixes):
                    continue
                # Skip cells with SQL language metadata
                lang = cell.get("metadata", {}).get("language", "")
                if lang.lower() == "sql":
                    continue
                try:
                    ast.parse(source)
                except SyntaxError as e:
                    issues.append(
                        f"{os.path.basename(path)}:cell_{i}: {e.msg} (line {e.lineno})"
                    )
        assert len(issues) == 0, f"Python syntax errors:\n" + "\n".join(issues)


@pytest.mark.notebook
class TestNotebookContent:
    """Validate notebook content quality."""

    def test_no_hardcoded_credentials(self, project_root):
        issues = []
        # Known safe patterns that contain keyword substrings but are not credentials
        safe_patterns = [
            "/snowflake/session/token",  # SPCS token file read
            "token = open(",             # SPCS token file read
            ".connection.token",         # Snowpark session token attribute
            "conn.token",                # Snowpark session token via alias
            'Token=\\"',                 # Snowflake auth header pattern
            "Token=\"",                  # Snowflake auth header pattern
        ]
        for path in get_notebook_paths(project_root):
            cells = load_notebook(path)
            for i, cell in enumerate(cells):
                source = "".join(cell.get("source", []))
                for keyword in ["password=", "token=", "secret=", "api_key="]:
                    if keyword in source.lower():
                        # Check if line matches a known safe pattern
                        is_safe = any(sp in source for sp in safe_patterns)
                        if not is_safe:
                            issues.append(f"{os.path.basename(path)}:cell_{i}: found '{keyword}'")
        assert len(issues) == 0, f"Possible credentials:\n" + "\n".join(issues)
