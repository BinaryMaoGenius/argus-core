from app.router import route_decide, MODE_TRiAGE, MODE_CODER


def test_route_short_prompt():
    m = route_decide("Quelle est la syntaxe pour lister les fichiers ?", threshold=200)
    assert m == MODE_TRiAGE


def test_route_long_prompt():
    long = "a" * 500
    m = route_decide(long, threshold=100)
    assert m == MODE_CODER
