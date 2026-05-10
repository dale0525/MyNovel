import mynovel


def test_package_has_version() -> None:
    assert isinstance(mynovel.__version__, str)
    assert mynovel.__version__
