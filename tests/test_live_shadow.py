from datetime import datetime, timezone

import src.live_shadow as live_shadow


class FakeBundle:
    pass


def test_live_shadow_module_has_no_publish_path():
    # Safety contract: the public function has no persistence or publish argument.
    names=live_shadow.run_live_shadow.__code__.co_varnames[:live_shadow.run_live_shadow.__code__.co_argcount]
    assert "publish" not in names
    assert "persistence" not in names


def test_missing_token_returns_safe_acquisition_diagnostic():
    try:
        live_shadow.run_live_shadow("LTF","",datetime(2026,9,18,4,0,tzinfo=timezone.utc))
    except Exception as exc:
        assert "UPSTOX_TOKEN_MISSING" in str(exc)
    else:
        raise AssertionError("missing token must fail")
