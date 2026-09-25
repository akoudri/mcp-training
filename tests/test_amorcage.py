import importlib


def test_fastmcp_epingle():
    fastmcp = importlib.import_module("fastmcp")
    assert fastmcp.__version__ == "4.0.10"


def test_src_sur_le_chemin():
    import sys
    assert any(p.endswith("src") for p in sys.path)
