"""Shared fixtures for LoadStar quality tests."""
import os
import pytest


def get_snowflake_session():
    """Create a Snowflake session using the snow CLI connection config."""
    try:
        from snowflake.snowpark import Session

        session = Session.builder.config("connection_name", "se_demo").create()
        session.sql("USE DATABASE APEX_CAPITAL_DEMO").collect()
        return session
    except Exception as e:
        pytest.skip(f"Snowflake connection unavailable: {e}")


@pytest.fixture(scope="session")
def sf_session():
    """Snowflake session fixture, shared across the test session."""
    session = get_snowflake_session()
    yield session
    session.close()


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
