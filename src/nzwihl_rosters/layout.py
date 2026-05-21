"""Render the single-page roster PDF for any two NZWIHL teams.

Calling convention:

    build_roster_pdf(
        out_path="/.../Admirals_vs_Thunder.pdf",
        away_team=Team(...), away_skaters=[...], away_goalies=[...],
        home_team=Team(...), home_skaters=[...], home_goalies=[...],
        game_info=GameInfo(...),
    )

The two columns are: HOME left, AWAY right.
"""
from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.pagesizes import portrait, A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .scraper import SkaterRow, GoalieRow
from .teams import Team


# Neutral palette
INK       = HexColor("#0C0C0C")
SUBINK    = HexColor("#404040")
MUTED     = HexColor("#6A6A6A")
DIM       = HexColor("#9A9A9A")
RULE      = HexColor("#D8D8D8")
DIM_BG    = HexColor("#F2F2F2")
ZERO_BG   = HexColor("#F7F7F7")
HIGHLIGHT = HexColor("#FFF1B8")


@dataclass
class GameInfo:
    round_label: str       # e.g. "Rd 03"
    date_label: str        # e.g. "Fri 22 May 19:00 & Sat 23 May 18:30"
    venue: str             # e.g. "Dunedin Ice Stadium"

    @property
    def footer_line(self) -> str:
        return f"NZIHL · {self.round_label} · {self.date_label} · {self.venue}"


def _jersey_sort_key(num: str):
    try:
        return (0, int(num))
    except ValueError:
        return (1, 9999)


def _sort_skaters(rows: list[SkaterRow]):
    played = sorted([r for r in rows if r.gp > 0], key=lambda r: _jersey_sort_key(r.jersey))
    bench  = sorted([r for r in rows if r.gp == 0], key=lambda r: _jersey_sort_key(r.jersey))
    return played, bench


def _top3_keys(rows: list[SkaterRow]) -> set[tuple[str, str]]:
    scored = [r for r in rows if r.gp > 0 and (r.g + r.a) > 0]
    scored.sort(key=lambda r: (-(r.g + r.a), -r.g, _jersey_sort_key(r.jersey)))
    return {(r.jersey, r.last) for r in scored[:3]}


def _merge_bench_goalies_into_skaters(skaters: list[SkaterRow], goalies: list[GoalieRow]) -> tuple[list[SkaterRow], list[GoalieRow]]:
    """GP=0 goalies appear in the 'NOT YET PLAYED' skater list; GP>0 goalies get cards."""
    played_g = [g for g in goalies if g.gp > 0]
    bench_g = [g for g in goalies if g.gp == 0]
    bench_as_skaters = [
        SkaterRow(jersey=g.jersey, last=g.last, first=g.first,
                  position="G", gp=0, g=0, a=0, flag=g.flag)
        for g in bench_g
    ]
    return skaters + bench_as_skaters, played_g


def build_roster_pdf(
    *,
    out_path: str,
    away_team: Team, away_skaters: list[SkaterRow], away_goalies: list[GoalieRow],
    home_team: Team, home_skaters: list[SkaterRow], home_goalies: list[GoalieRow],
    game_info: GameInfo,
) -> str:
    """Build the PDF; return the output path."""
    PAGE = portrait(A4)
    PW, PH = PAGE
    MARGIN = 12*mm
    COL_GUTTER = 5*mm
    FOOTER_H = 7*mm

    c = canvas.Canvas(out_path, pagesize=PAGE)
    c.setTitle(f"{away_team.display_name} vs {home_team.display_name}")

    content_top    = PH - MARGIN
    content_bottom = MARGIN + FOOTER_H
    col_w  = (PW - 2*MARGIN - COL_GUTTER) / 2
    left_x  = MARGIN
    right_x = MARGIN + col_w + COL_GUTTER

    # Compute one header font size that fits both team names
    def _fit_header_fs() -> float:
        fs = 19.0
        max_w = col_w - 8*mm
        for t in (away_team.display_name, home_team.display_name):
            up = t.upper()
            while c.stringWidth(up, "Helvetica-Bold", fs) > max_w and fs > 11:
                fs -= 0.5
        return fs
    HEADER_FS = _fit_header_fs()

    def draw_team(x: float, team: Team, skaters: list[SkaterRow], played_goalies: list[GoalieRow]):
        y_top = content_top
        primary = HexColor(team.primary_hex)
        accent  = HexColor(team.accent_hex)
        title_color = HexColor(team.title_hex)

        # team header band
        band_h = 14*mm
        c.setFillColor(primary); c.rect(x, y_top - band_h, col_w, band_h, fill=1, stroke=0)
        c.setFillColor(title_color); c.setFont("Helvetica-Bold", HEADER_FS)
        c.drawCentredString(x + col_w/2, y_top - band_h + 4.7*mm, team.display_name.upper())
        cur_y = y_top - band_h - 5*mm

        highlight = _top3_keys(skaters)

        # goalies
        c.setFillColor(MUTED); c.setFont("Helvetica-Bold", 8)
        c.drawString(x, cur_y, "GOALIES")
        c.setStrokeColor(RULE); c.setLineWidth(0.4)
        c.line(x + 18*mm, cur_y + 2.5, x + col_w, cur_y + 2.5)
        cur_y -= 3*mm

        n = len(played_goalies)
        goalie_card_h = 19*mm
        gw = (col_w - max(n-1, 0)*3*mm) / max(n, 1)
        for i, g in enumerate(played_goalies):
            gx = x + i*(gw + 3*mm)
            c.setFillColor(DIM_BG); c.setStrokeColor(RULE); c.setLineWidth(0.4)
            c.rect(gx, cur_y - goalie_card_h, gw, goalie_card_h, fill=1, stroke=1)
            # jersey
            num_fs = 17
            c.setFillColor(primary); c.setFont("Helvetica-Bold", num_fs)
            c.drawString(gx + 3*mm, cur_y - goalie_card_h + 11*mm, g.jersey)
            num_w = c.stringWidth(g.jersey, "Helvetica-Bold", num_fs)
            name_x = gx + 3*mm + num_w + 2*mm
            name_max_w = (gx + gw) - name_x - 1.5*mm
            # surname auto-shrink
            last_fs = 11.5
            while c.stringWidth(g.last, "Helvetica-Bold", last_fs) > name_max_w and last_fs > 8:
                last_fs -= 0.5
            c.setFillColor(INK); c.setFont("Helvetica-Bold", last_fs)
            c.drawString(name_x, cur_y - goalie_card_h + 12.5*mm, g.last)
            first_fs = 9
            while c.stringWidth(g.first, "Helvetica", first_fs) > name_max_w and first_fs > 7:
                first_fs -= 0.5
            c.setFont("Helvetica", first_fs); c.setFillColor(SUBINK)
            c.drawString(name_x, cur_y - goalie_card_h + 8.5*mm, g.first)
            # stats
            c.setFont("Helvetica", 7.5); c.setFillColor(MUTED)
            c.drawString(gx + 3*mm, cur_y - goalie_card_h + 4.5*mm,
                         f"GP {g.gp}  ·  GAA {g.gaa}")
            c.drawString(gx + 3*mm, cur_y - goalie_card_h + 1.5*mm,
                         f"SV {g.sv_pct}")
        cur_y -= goalie_card_h + 5*mm

        # skaters header
        c.setFillColor(MUTED); c.setFont("Helvetica-Bold", 8)
        c.drawString(x, cur_y, "SKATERS")
        c.setStrokeColor(RULE); c.setLineWidth(0.4)
        c.line(x + 18*mm, cur_y + 2.5, x + col_w, cur_y + 2.5)
        cur_y -= 4*mm

        a_x   = x + col_w - 4*mm
        g_x   = a_x  - 7*mm
        pos_x = g_x  - 7*mm
        name_right = pos_x - 5*mm

        c.setFillColor(MUTED); c.setFont("Helvetica-Bold", 7)
        c.drawRightString(x + 10*mm, cur_y, "#")
        c.drawString(x + 12*mm, cur_y, "NAME")
        c.drawRightString(pos_x, cur_y, "POS")
        c.drawRightString(g_x, cur_y, "G")
        c.drawRightString(a_x, cur_y, "A")
        c.setStrokeColor(RULE); c.setLineWidth(0.5)
        c.line(x, cur_y - 1.8*mm, x + col_w, cur_y - 1.8*mm)
        cur_y -= 3.5*mm

        played, benched = _sort_skaters(skaters)
        avail_h = cur_y - content_bottom
        divider_h = 4.5*mm if benched else 0
        denom = max(len(played) + 0.78 * len(benched), 1)
        unit = (avail_h - divider_h) / denom
        unit = min(unit, 8.4*mm); unit = max(unit, 5.0*mm)
        played_row_h  = unit
        benched_row_h = unit * 0.78

        def draw_row(r: SkaterRow, ry: float, row_h: float, dim: bool):
            is_no_num = (r.jersey == "-")
            is_top3 = (r.jersey, r.last) in highlight
            num_fs   = 13.5 if not dim else 10
            last_fs0 = 12   if not dim else 9
            first_fs = 10   if not dim else 7.5
            body_fs  = 10   if not dim else 8
            flag_fs  = 7    if not dim else 6

            num_color  = primary if not (dim or is_no_num) else (DIM if dim else MUTED)
            body_color = INK if not dim else DIM
            first_color = SUBINK if not dim else DIM

            if is_top3:
                c.setFillColor(HIGHLIGHT)
                c.rect(x, ry, col_w, row_h, fill=1, stroke=0)

            baseline = ry + row_h*0.32

            c.setFillColor(num_color); c.setFont("Helvetica-Bold", num_fs)
            c.drawRightString(x + 10*mm, baseline, r.jersey)

            # surname (auto-shrink for very long names)
            last_fs = last_fs0
            last_text = r.last
            while c.stringWidth(last_text, "Helvetica-Bold", last_fs) > (name_right - (x + 12*mm)) * 0.7 and last_fs > 8.5:
                last_fs -= 0.5
            c.setFillColor(body_color); c.setFont("Helvetica-Bold", last_fs)
            c.drawString(x + 12*mm, baseline, last_text)
            last_w = c.stringWidth(last_text, "Helvetica-Bold", last_fs)

            first_x = x + 12*mm + last_w + 2.2*mm
            c.setFillColor(first_color); c.setFont("Helvetica", first_fs)
            flag_w = c.stringWidth(r.flag, "Helvetica-Bold", flag_fs) + 1.6*mm if r.flag else 0
            max_first_w = name_right - first_x - flag_w
            first_text = r.first
            while c.stringWidth(first_text, "Helvetica", first_fs) > max_first_w and len(first_text) > 1:
                first_text = first_text[:-1]
            if first_text != r.first:
                first_text = first_text.rstrip() + "."
            c.drawString(first_x, baseline, first_text)
            first_text_w = c.stringWidth(first_text, "Helvetica", first_fs)

            if r.flag:
                flag_color = MUTED if dim else (
                    MUTED if r.flag in ("AF", "RO") else accent if r.flag == "IM" else primary
                )
                c.setFillColor(flag_color); c.setFont("Helvetica-Bold", flag_fs)
                c.drawString(first_x + first_text_w + 1.4*mm, baseline, r.flag)

            c.setFillColor(body_color); c.setFont("Helvetica-Bold", body_fs)
            c.drawRightString(pos_x, baseline, r.position)
            if r.gp == 0:
                c.setFillColor(DIM)
                c.drawRightString(g_x, baseline, "–")
                c.drawRightString(a_x, baseline, "–")
            else:
                c.setFillColor(body_color)
                c.drawRightString(g_x, baseline, str(r.g))
                c.drawRightString(a_x, baseline, str(r.a))

            c.setStrokeColor(RULE); c.setLineWidth(0.25)
            c.line(x, ry, x + col_w, ry)

        ry = cur_y
        for r in played:
            ry -= played_row_h
            draw_row(r, ry, played_row_h, dim=False)
        if benched:
            ry -= divider_h
            c.setFillColor(ZERO_BG)
            c.rect(x, ry, col_w, divider_h, fill=1, stroke=0)
            c.setFillColor(MUTED); c.setFont("Helvetica-Bold", 6.8)
            c.drawString(x + 2*mm, ry + divider_h/2 - 2, "NOT YET PLAYED THIS SEASON")
            for r in benched:
                ry -= benched_row_h
                draw_row(r, ry, benched_row_h, dim=True)

    # Move bench goalies into the skater "not yet played" group
    away_skaters_full, away_played_g = _merge_bench_goalies_into_skaters(away_skaters, away_goalies)
    home_skaters_full, home_played_g = _merge_bench_goalies_into_skaters(home_skaters, home_goalies)

    draw_team(left_x,  home_team, home_skaters_full, home_played_g)
    draw_team(right_x, away_team, away_skaters_full, away_played_g)

    # Footer
    c.setFillColor(MUTED); c.setFont("Helvetica", 8.5)
    c.drawCentredString(PW/2, MARGIN + 1.5*mm, game_info.footer_line)

    c.showPage()
    c.save()
    return out_path
