from __future__ import annotations

from nzwihl_rosters import overrides
from nzwihl_rosters.scraper import _split_first_last


def test_shattock_override_and_generic_regression():
    assert overrides.normalize_name("Reagyn", "Shattock (Niskakoski)", 675637, "3") == ("Reagyn", "Shattock")
    assert _split_first_last("Some Kercso-Magos") == ("Some", "Kercso-Magos")
    assert _split_first_last("Eli Seo Jun Paek") == ("Eli Seo Jun", "Paek")


def test_load_remote_overrides_success_updates_module_state(monkeypatch):
    fallback_multi = set(overrides.MULTI_WORD_SURNAMES)
    fallback_so = dict(overrides.SURNAME_OVERRIDES)

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "multi_word_surnames": ["van berg"],
                "team_jersey_overrides": [
                    {"league": "nzwihl", "team_id": 675637, "jersey": "3",
                     "first": "Reagyn", "last": "Shattock"},
                    # nzihl entry -- must be filtered out, this repo is nzwihl-only
                    {"league": "nzihl", "team_id": 674110, "jersey": "26",
                     "first": "Benjamin", "last": "De Jonge"},
                ],
            }

    def fake_get(url, timeout=None):
        assert "name-overrides.json" in url
        return FakeResp()

    monkeypatch.setattr("requests.get", fake_get)
    try:
        assert overrides.load_remote_overrides() is True
        assert overrides.MULTI_WORD_SURNAMES == {"van berg"}
        assert overrides.SURNAME_OVERRIDES == {(675637, "3"): ("Shattock", "Reagyn")}
        assert _split_first_last("A Van Berg") == ("A", "Van Berg")
        assert overrides.normalize_name("Reagyn", "Shattock (Niskakoski)", 675637, "3") == ("Reagyn", "Shattock")
    finally:
        overrides.MULTI_WORD_SURNAMES = fallback_multi
        overrides.SURNAME_OVERRIDES = fallback_so


def test_load_remote_overrides_failure_keeps_fallback(monkeypatch):
    fallback_multi = set(overrides.MULTI_WORD_SURNAMES)
    fallback_so = dict(overrides.SURNAME_OVERRIDES)

    def fake_get(url, timeout=None):
        raise ConnectionError("simulated network failure")

    monkeypatch.setattr("requests.get", fake_get)
    assert overrides.load_remote_overrides() is False
    assert overrides.MULTI_WORD_SURNAMES == fallback_multi
    assert overrides.SURNAME_OVERRIDES == fallback_so
