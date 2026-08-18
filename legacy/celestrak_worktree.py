import requests
from dataclasses import dataclass
from typing import Optional

GP_URL = "https://celestrak.org/NORAD/elements/gp.php"

@dataclass
class SatelliteTLE:
    norad_id: str
    name: str
    tle_line1: str
    tle_line2: str

def fetch_tle_for_object(norad_id: str) -> Optional[SatelliteTLE]:
    r = requests.get(GP_URL, params={
        "CATNR": norad_id,
        "FORMAT": "TLE"
    }, timeout=10)
    r.raise_for_status()
    text = r.text.strip()
    lines = text.splitlines()
    if len(lines) < 3:
        return None
    return SatelliteTLE(
        norad_id=norad_id,
        name=lines[0].strip(),
        tle_line1=lines[1].strip(),
        tle_line2=lines[2].strip()
    )

if __name__ == "__main__":
    from rich import print as rprint
    print("Fetching TLE for ISS (NORAD 25544)...")
    iss = fetch_tle_for_object("25544")
    if iss:
        rprint(f"[bold green]Got TLE for: {iss.name}[/bold green]")
        rprint(f"  NORAD ID: {iss.norad_id}")
        rprint(f"  Line 1: {iss.tle_line1}")
        rprint(f"  Line 2: {iss.tle_line2}")
    else:
        print("No data returned")