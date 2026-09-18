from datetime import datetime, timedelta, timezone

from src.autonomous_interpreter import ConservativeAutonomousInterpreter
from src.evidence_gate import EvidenceItem

RUN_AT=datetime(2026,9,18,4,0,tzinfo=timezone.utc)


def candles(start=100.0, step=0.8, n=60, volume=1000.0):
    rows=[]
    base=RUN_AT-timedelta(days=n)
    for i in range(n):
        o=start+i*step
        c=o+step*0.6
        rows.append([
            (base+timedelta(days=i)).isoformat(),
            o,
            c+0.5,
            o-0.5,
            c,
            volume*(1.0 + (0.05 if i==n-1 else 0.0)),
            0,
        ])
    return rows


def payloads():
    stock=candles()
    nifty=candles(start=20000,step=20)
    return {
        "upstox:/v3/historical-candle/NSE_EQ%7CINE498L01015/days/1/2026-09-18/2026-03-22#sha256=a":
            {"status":"success","data":{"candles":stock}},
        "upstox:/v3/historical-candle/NSE_INDEX%7CNifty%2050/days/1/2026-09-18/2026-03-22#sha256=b":
            {"status":"success","data":{"candles":nifty}},
        "upstox:/v2/fundamentals/INE498L01015/income-statement?time_period=quarterly&type=consolidated#sha256=c":
            {"status":"success","data":{"income_statement":[
                {"category":"revenue","history":[{"change":"+12%"}]},
                {"category":"net_profit","history":[{"change":"+18%"}]},
            ]}},
        "upstox:/v2/fundamentals/INE498L01015/key-ratios#sha256=d":
            {"status":"success","data":[
                {"name":"P/E","company_value":"15","sector_value":"20"},
                {"name":"P/B","company_value":"2","sector_value":"3"},
                {"name":"EV/EBITDA","company_value":"8","sector_value":"10"},
            ]},
        "upstox:/v2/fundamentals/INE498L01015/share-holdings#sha256=e":
            {"status":"success","data":[
                {"category":"fii","history":[{"value":12.0},{"value":11.0}]},
                {"category":"mutual_funds","history":[{"value":5.0},{"value":4.5}]},
            ]},
        "upstox:/v2/news?category=instrument_keys#sha256=f":
            {"status":"success","data":{"NSE_EQ|INE498L01015":[
                {"heading":"Company wins order","summary":"new order win announced"},
                {"heading":"Partnership approval","summary":"approval and partnership"},
            ]}},
    }


def evidence():
    cats=(
        "PRICE_STRUCTURE","PV_PVPO","SPECIFIC_CHART_PATTERN","NEWS_EVENTS_CATALYSTS",
        "BUSINESS_FUNDAMENTALS","INSTITUTIONAL_BEHAVIOUR","RELATIVE_STRENGTH",
        "VALUATION","EVENT_SHOCK",
    )
    return tuple(EvidenceItem(c,"LTF",RUN_AT,f"ref:{c}",True) for c in cats)


def test_interpreter_produces_all_nine_components_when_structured_data_is_available():
    out=ConservativeAutonomousInterpreter()("LTF",evidence(),payloads(),RUN_AT)
    rows={r.component:r.raw_score for r in out.component_scores}
    assert set(rows)=={
        "PRICE_STRUCTURE","PV_PVPO","SPECIFIC_CHART_PATTERN","NEWS_EVENTS_CATALYSTS",
        "BUSINESS_FUNDAMENTALS","INSTITUTIONAL_BEHAVIOUR","RELATIVE_STRENGTH",
        "VALUATION","EVENT_SHOCK",
    }
    assert rows["BUSINESS_FUNDAMENTALS"] == 2
    assert rows["INSTITUTIONAL_BEHAVIOUR"] == 2
    assert rows["VALUATION"] >= 1
    assert rows["NEWS_EVENTS_CATALYSTS"] >= 1
    assert out.completeness_score == 100.0
    assert out.expected_price_zone_low is None
    assert out.expected_price_zone_high is None
    assert out.zone_context is not None
    assert out.zone_context.close > 0
    assert out.definitive_recommendation.startswith("SHADOW ONLY")


def test_keyword_event_classifier_never_escalates_to_o2_or_o3():
    p=payloads()
    p["upstox:/v2/news?category=instrument_keys#sha256=f"]={
        "status":"success","data":{"NSE_EQ|INE498L01015":[
            {"heading":"Fraud investigation default","summary":"auditor resignation investigation"}
        ]}
    }
    out=ConservativeAutonomousInterpreter()("LTF",evidence(),p,RUN_AT)
    assert out.event_override == "O1"


def test_malformed_fundamentals_are_not_fabricated():
    p=payloads()
    p["upstox:/v2/fundamentals/INE498L01015/income-statement?time_period=quarterly&type=consolidated#sha256=c"]={
        "status":"success","data":{}
    }
    out=ConservativeAutonomousInterpreter()("LTF",evidence(),p,RUN_AT)
    row=[r for r in out.component_scores if r.component=="BUSINESS_FUNDAMENTALS"][0]
    assert row.verified is False
    assert row.raw_score is None
    assert out.completeness_score < 100
