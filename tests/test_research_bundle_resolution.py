from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src import research_bundle as module

NOW=datetime(2026,10,2,13,45,tzinfo=timezone.utc)

class Connection:
    def __init__(self, ids):
        self.ids=ids
        self.calls=[]
    def cursor(self):
        return self
    def __enter__(self):
        return self
    def __exit__(self,*args):
        pass
    def execute(self,query,params):
        self.calls.append((query,params))
    def fetchall(self):
        return [(i,) for i in self.ids]


def bundle(identity,ticker='LTF',age=10):
    return SimpleNamespace(bundle_id=identity,ticker=ticker,research_fresh_at=NOW-timedelta(minutes=age))


def test_selects_eligible_older_bundle_after_newest_fails_gate(monkeypatch):
    conn=Connection(['invalid-new','eligible-older'])
    def load(connection,identity,**kwargs):
        assert kwargs=={'ticker':'LTF','run_at':NOW}
        if identity=='invalid-new':
            raise ValueError('unverified material evidence')
        return bundle(identity)
    monkeypatch.setattr(module,'load_governed_research_bundle',load)
    selected=module.latest_fresh_governed_research_bundle(conn,ticker='ltf',run_at=NOW)
    assert selected.bundle_id=='eligible-older'
    assert conn.calls[0][1]==('LTF',NOW-timedelta(hours=24))
    assert all(sql.strip().lower().startswith('select ') for sql,_ in conn.calls)


def test_no_eligible_bundle_returns_none_without_fabrication():
    assert module.latest_fresh_governed_research_bundle(Connection([]),ticker='CUPID',run_at=NOW) is None


def test_mismatched_and_stale_stored_lineage_is_not_selected(monkeypatch):
    candidates={
        'wrong-stock':bundle('wrong-stock','CUPID'),
        'wrong-id':bundle('different-id'),
        'stale':bundle('stale',age=1441),
        'future':bundle('future',age=-3),
    }
    monkeypatch.setattr(module,'load_governed_research_bundle',lambda conn,identity,**kwargs:candidates[identity])
    assert module.latest_fresh_governed_research_bundle(Connection(candidates),ticker='LTF',run_at=NOW) is None


def test_database_error_is_not_treated_as_missing_research(monkeypatch):
    import pytest
    def load(*args,**kwargs):
        raise RuntimeError('database unavailable')
    monkeypatch.setattr(module,'load_governed_research_bundle',load)
    with pytest.raises(RuntimeError):
        module.latest_fresh_governed_research_bundle(Connection(['some-id']),ticker='LTF',run_at=NOW)
