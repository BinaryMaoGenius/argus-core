from app.security import SecurityEngine


def test_security_allows_safe_action():
    s = SecurityEngine()
    res = s.allow_action("List files in the current directory")
    assert res["allowed"] is True


def test_security_blocks_destructive():
    s = SecurityEngine()
    res = s.allow_action("rm -rf / important")
    assert res["allowed"] is False
