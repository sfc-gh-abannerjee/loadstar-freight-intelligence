"""Static analysis tests for the Streamlit app (no Snowflake needed)."""
import os
import subprocess
import pytest


@pytest.mark.streamlit
class TestStreamlitStatic:
    """Static analysis of streamlit/streamlit_app.py."""

    def _get_app_path(self, project_root):
        return os.path.join(project_root, "streamlit", "streamlit_app.py")

    def test_app_file_exists(self, project_root):
        app_path = self._get_app_path(project_root)
        assert os.path.isfile(app_path), f"Streamlit app not found at {app_path}"

    def test_ruff_no_errors(self, project_root):
        app_path = self._get_app_path(project_root)
        if not os.path.isfile(app_path):
            pytest.skip("App file not found")
        import sys
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", app_path, "--select", "E,F"],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"Ruff found errors:\n{result.stdout}"

    def test_ruff_no_security_issues(self, project_root):
        app_path = self._get_app_path(project_root)
        if not os.path.isfile(app_path):
            pytest.skip("App file not found")
        import sys
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", app_path, "--select", "S"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            pytest.fail(f"Ruff found security issues:\n{result.stdout}")

    def test_uses_st_connection(self, project_root):
        """Container runtime should use st.connection, not get_active_session."""
        app_path = self._get_app_path(project_root)
        if not os.path.isfile(app_path):
            pytest.skip("App file not found")
        with open(app_path) as f:
            content = f.read()
        assert "get_active_session" not in content, (
            "Found get_active_session() -- container runtime should use st.connection('snowflake')"
        )

    def test_no_fstring_sql_injection(self, project_root):
        """Check for obvious SQL injection patterns."""
        app_path = self._get_app_path(project_root)
        if not os.path.isfile(app_path):
            pytest.skip("App file not found")
        with open(app_path) as f:
            lines = f.readlines()
        issues = []
        for i, line in enumerate(lines, 1):
            if 'f"SELECT' in line or "f'SELECT" in line:
                if "st.text_input" in line or "user_input" in line.lower():
                    issues.append(f"  Line {i}: {line.strip()}")
        assert len(issues) == 0, (
            f"Potential SQL injection via f-string:\n" + "\n".join(issues)
        )

    def test_snowflake_yml_exists(self, project_root):
        yml_path = os.path.join(project_root, "streamlit", "snowflake.yml")
        assert os.path.isfile(yml_path), "streamlit/snowflake.yml not found"
