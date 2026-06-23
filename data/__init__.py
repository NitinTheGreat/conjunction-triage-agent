import requests
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

@dataclass
class ConjunctionEvent:
    event_id: str
    tca: str
    hours_to_tca: float
    miss_distance_km: float
    pc: Optional[float]
    sat1_norad: str
    sat1_name: str
    sat2_norad: str
    sat2_name: str
    relative_speed_kms: Optional[float]
    source: str
    raw: dict

def fetch_conjunctions(limit: int = 50) -> list[ConjunctionEvent]:
    r = requests.get("https://celestrak.org/SOCRATES/query.php", params={
        "FORMAT": "json",
        "LIMIT": limit,
        "MIN_DAYS": 0,
        "MAX_DAYS": 7,
        "MAX_RANGE": 5,
    })
    r.raise_for_status()
    raw_events = r.json()
    events = []
    now = datetime.utcnow()
    for e in raw_events:
        tca_str = e.get("TCA", "")
        try:
            tca_dt = datetime.strptime(tca_str, "%Y-%m-%d %H:%M:%S")
            hours = (tca_dt - now).total_seconds() / 3600
        except:
            hours = 0.0
        pc_raw = e.get("MAX_PROB")
        pc = float(pc_raw) if pc_raw not in (None, "", "N/A") else None
        speed_raw = e.get("REL_SPEED")
        speed = float(speed_raw) if speed_raw not in (None, "", "N/A") else None
        events.append(ConjunctionEvent(
            event_id=f"{e.get('SAT1_ID','?')}_{e.get('SAT2_ID','?')}_{tca_str[:10]}",
            tca=tca_str,
            hours_to_tca=round(hours, 2),
            miss_distance_km=float(e.get("MIN_RANGE", 0)),
            pc=pc,
            sat1_norad=str(e.get("SAT1_ID", "")),
            sat1_name=e.get("SAT1_NAME", ""),
            sat2_norad=str(e.get("SAT2_ID", "")),
            sat2_name=e.get("SAT2_NAME", ""),
            relative_speed_kms=speed,
            source="celestrak",
            raw=e
        ))
    return events

if __name__ == "__main__":
    from rich import print as rprint
    events = fetch_conjunctions(limit=10)
    print(f"\nGot {len(events)} conjunction events from CelesTrak\n")
    for ev in events[:5]:
        rprint(f"[bold]{ev.sat1_name}[/bold] vs [bold]{ev.sat2_name}[/bold]")
        rprint(f"  TCA: {ev.tca}  ({ev.hours_to_tca:.1f} hours)")
        rprint(f"  Miss distance: {ev.miss_distance_km:.3f} km")
        rprint(f"  Pc: {ev.pc}")
        print()