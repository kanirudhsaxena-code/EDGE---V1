import os
import sys
from types import SimpleNamespace

from src.production_orchestrator import HoldingState


def test_live_candidate_workflow_defaults_to_unknown_holding_semantics():
    assert HoldingState("UNKNOWN") is HoldingState.UNKNOWN


def test_cli_source_does_not_enable_publish():
    from pathlib import Path
    text=Path("src/production_candidate_cli.py").read_text(encoding="utf-8")
    assert "publish=False" in text
    assert "publish=True" not in text


def test_candidate_forwards_governed_research_bundle_without_enabling_publish(monkeypatch):
    from src import production_candidate_cli as cli
    calls = []
    connection = SimpleNamespace(close=lambda: None)
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda _: connection))
    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", "test-db")
    monkeypatch.setenv("EDGE_RESEARCH_BUNDLE_ID", "research-test-id")
    monkeypatch.setenv("EDGE_HOLDING_STATE", "UNKNOWN")
    def build(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status="PRODUCTION_CANDIDATE_READY", blockers=(), canonical_bundle=None, report_markdown=None)
    monkeypatch.setattr(cli, "build_production_candidate", build)
    assert cli.main() == 0
    assert calls[0]["research_bundle_id"] == "research-test-id"
    assert calls[0]["publish"] is False


def test_candidate_resolves_real_stored_id_when_omitted(monkeypatch,capsys):
    from src import production_candidate_cli as cli
    connection=SimpleNamespace(close=lambda:None)
    monkeypatch.setitem(sys.modules,'psycopg',SimpleNamespace(connect=lambda _:connection))
    monkeypatch.setenv('UPSTOX_ANALYTICS_TOKEN','test-token')
    monkeypatch.setenv('DATABASE_URL','test-db')
    monkeypatch.setenv('EDGE_TICKER','CUPID')
    monkeypatch.setenv('EDGE_HOLDING_STATE','UNKNOWN')
    monkeypatch.delenv('EDGE_RESEARCH_BUNDLE_ID',raising=False)
    calls=[]
    def resolve(conn,**kwargs):
        assert conn is connection and kwargs['ticker']=='CUPID'
        calls.append(kwargs)
        return SimpleNamespace(bundle_id='stored-cupid-id')
    monkeypatch.setattr(cli,'latest_fresh_governed_research_bundle',resolve)
    def build(**kwargs):
        assert kwargs['research_bundle_id']=='stored-cupid-id'
        assert kwargs['run_at']==calls[0]['run_at']
        assert kwargs['publish'] is False
        return SimpleNamespace(status='PRODUCTION_CANDIDATE_READY',blockers=(),canonical_bundle=None,report_markdown=None)
    monkeypatch.setattr(cli,'build_production_candidate',build)
    assert cli.main()==0
    assert 'stored-cupid-id' in capsys.readouterr().out


def test_candidate_missing_bundle_blocks_before_upstox_and_closes_connection(monkeypatch,capsys):
    from src import production_candidate_cli as cli
    closed=[]
    monkeypatch.setitem(sys.modules,'psycopg',SimpleNamespace(connect=lambda _:SimpleNamespace(close=lambda:closed.append(True))))
    monkeypatch.setenv('UPSTOX_ANALYTICS_TOKEN','test-token')
    monkeypatch.setenv('DATABASE_URL','test-db')
    monkeypatch.setenv('EDGE_HOLDING_STATE','UNKNOWN')
    monkeypatch.delenv('EDGE_RESEARCH_BUNDLE_ID',raising=False)
    monkeypatch.setattr(cli,'latest_fresh_governed_research_bundle',lambda *args,**kwargs:None)
    monkeypatch.setattr(cli,'build_production_candidate',lambda **kwargs: (_ for _ in ()).throw(AssertionError('must not run')))
    assert cli.main()==3
    assert closed==[True]
    out=capsys.readouterr().out
    assert 'FRESH_GOVERNED_RESEARCH_REQUIRED' in out
    assert 'test-token' not in out and 'test-db' not in out
