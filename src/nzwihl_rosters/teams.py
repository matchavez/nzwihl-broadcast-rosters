"""NZWIHL team registry."""
from dataclasses import dataclass
from pathlib import Path

# Logos bundled with the package (transparent PNGs with white circular
# backdrops, ~320px square).
_LOGO_DIR = Path(__file__).resolve().parent / "assets" / "logos"


@dataclass(frozen=True)
class Team:
    team_id: int
    display_name: str
    schedule_name: str
    primary_hex: str
    accent_hex: str
    title_hex: str
    home_venue: str
    short_code: str
    logo_file: str = ""          # filename in assets/logos/ (defaults to short_code.png)

    @property
    def logo_path(self) -> "Path | None":
        """Absolute path to this team's bundled logo, or None if missing."""
        name = self.logo_file or f"{self.short_code.lower()}.png"
        path = _LOGO_DIR / name
        return path if path.exists() else None


TEAMS: dict[str, Team] = {
    "AUCKLAND STEEL": Team(
        team_id=675636,
        display_name="Auckland Steel",
        schedule_name="AUCKLAND STEEL",
        primary_hex="#1A2A44",
        accent_hex="#8A9BB0",
        title_hex="#FFFFFF",
        home_venue="Auckland",
        short_code="AST",
    ),
    "CANTERBURY INFERNO": Team(
        team_id=675637,
        display_name="Canterbury Inferno",
        schedule_name="CANTERBURY INFERNO",
        primary_hex="#B00020",
        accent_hex="#FF6A13",
        title_hex="#FFFFFF",
        home_venue="Alpine Ice Sports Centre, Christchurch",
        short_code="CIN",
    ),
    "DUNEDIN THUNDER WOMEN": Team(
        team_id=675638,
        display_name="Dunedin Thunder Women",
        schedule_name="DUNEDIN THUNDER WOMEN",
        primary_hex="#025B3D",
        accent_hex="#FDAD19",
        title_hex="#FDAD19",
        home_venue="Dunedin Ice Stadium",
        short_code="DTW",
    ),
    "WAKATIPU WILD": Team(
        team_id=675639,
        display_name="Wakatipu Wild",
        schedule_name="WAKATIPU WILD",
        primary_hex="#FAC805",
        accent_hex="#1D3056",
        title_hex="#1D3056",
        home_venue="Queenstown Ice Arena",
        short_code="WLD",
    ),
}


def by_schedule_name(name: str) -> Team | None:
    return TEAMS.get(name.strip().upper())


def by_team_id(team_id: int) -> Team | None:
    for team in TEAMS.values():
        if team.team_id == team_id:
            return team
    return None
