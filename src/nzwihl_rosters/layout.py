"""Render the single-page roster PDF for any two NZWIHL teams.

Calling convention:

    build_roster_pdf(
        out_path="/.../Steel_vs_Wild.pdf",
        away_team=Team(...), away_skaters=[...], away_goalies=[...],
        home_team=Team(...), home_skaters=[...], home_goalies=[...],
        game_info=GameInfo(...),
    )

The two columns are: AWAY left, HOME right (matches the schedule order).

Font, column layout, and goalie-card logic are ported from the NZIHL roster
renderer so both leagues get identical treatment wherever the underlying
data supports it (Mat, 2026-07-05). The one deliberate difference kept from
before: NZWIHL logos already carry a white circular backdrop, so no chip is
drawn behind them (NZIHL logos are drawn on a white rounded chip because
theirs don't).
"""
from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path

from reportlab.lib.pagesizes import portrait, A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as PDFTrueTypeFont

from .scraper import SkaterRow, GoalieRow
from .teams import Team

# House font: Inter, with tabular figures ('tnum') baked into the cmap as the
# default glyphs (same rationale/font files as the NZIHL renderer — see that
# module's comment for why features are baked in rather than applied via
# OpenType shaping, which reportlab's TTFont embedding doesn't support).
_FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
FONT_REGULAR = "Inter"
FONT_BOLD = "Inter-Bold"
pdfmetrics.registerFont(PDFTrueTypeFont(FONT_REGULAR, str(_FONT_DIR / "Inter-Regular-tnum.ttf")))
pdfmetrics.registerFont(PDFTrueTypeFont(FONT_BOLD, str(_FONT_DIR / "Inter-Bold-tnum.ttf")))
FONT_SEMIBOLD = "Inter-SemiBold"
pdfmetrics.registerFont(PDFTrueTypeFont(FONT_SEMIBOLD, str(_FONT_DIR / "Inter-SemiBold-tnum.ttf")))
FONT_THIN = "Inter-Thin"
pdfmetrics.registerFont(PDFTrueTypeFont(FONT_THIN, str(_FONT_DIR / "Inter-Thin-tnum.ttf")))
pdfmetrics.registerFontFamily(FONT_REGULAR, normal=FONT_REGULAR, bold=FONT_BOLD)


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
    venue: str              # e.g. "Dunedin Ice Stadium"

    @property
    def footer_line(self) -> str:
        return f"NZWIHL · {self.round_label} · {self.date_label} · {self.venue}"


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

    # Compute one header font size that fits both team names. The logo + name are
    # drawn as a single centred group, so reserve horizontal room for the badge.
    LOGO_ALLOW = 9*mm   # badge width + gap budget when sizing the name
    def _fit_header_fs() -> float:
        fs = 19.0
        max_w = col_w - 8*mm - LOGO_ALLOW
        for t in (away_team.display_name, home_team.display_name):
            up = t.upper()
            while c.stringWidth(up, FONT_BOLD, fs) > max_w and fs > 11:
                fs -= 0.5
        return fs
    HEADER_FS = _fit_header_fs()

    def _draw_header_badge_and_name(x: float, team: Team, title_color, band_top: float, band_h: float):
        """Draw the team name centred, with its logo immediately to the left, the
        pair centred together in the band. NZWIHL logos already carry a white
        circular backdrop, so no chip is drawn behind them (unlike NZIHL)."""
        text = team.display_name.upper()
        text_w = c.stringWidth(text, FONT_BOLD, HEADER_FS)
        band_mid = band_top - band_h/2
        baseline = band_top - band_h + 4.7*mm

        logo_path = team.logo_path
        if logo_path is None:
            # graceful fallback: name only, centred
            c.setFillColor(title_color); c.setFont(FONT_BOLD, HEADER_FS)
            c.drawCentredString(x + col_w/2, baseline, text)
            return

        logo_box = HEADER_FS * 1.55     # drawn logo size (pt) ~ a touch over cap height
        gap      = 2.2*mm
        group_w  = logo_box + gap + text_w
        start_x  = x + col_w/2 - group_w/2

        # logo drawn directly on the band (its own white circle gives contrast),
        # centred vertically, aspect preserved, alpha respected
        c.drawImage(str(logo_path), start_x, band_mid - logo_box/2,
                    logo_box, logo_box, mask='auto', preserveAspectRatio=True)

        # team name
        c.setFillColor(title_color); c.setFont(FONT_BOLD, HEADER_FS)
        c.drawString(start_x + logo_box + gap, baseline, text)

    def draw_team(x: float, team: Team, skaters: list[SkaterRow], played_goalies: list[GoalieRow]):
        y_top = content_top
        primary = HexColor(team.primary_hex)
        # Text drawn directly on the white page (jersey #, captain letter) uses
        # `text_primary` rather than `primary`: most teams' primary colour reads
        # fine as text, but Wild's yellow is illegible on white, so their Team
        # entry overrides text_hex to their navy (ported from NZIHL's identical
        # Stampede fix, Mat, 2026-07-05). The header band itself still fills
        # with the true primary colour.
        text_primary = HexColor(team.text_hex or team.primary_hex)
        accent  = HexColor(team.accent_hex)
        title_color = HexColor(team.title_hex)

        # team header band
        band_h = 14*mm
        c.setFillColor(primary); c.rect(x, y_top - band_h, col_w, band_h, fill=1, stroke=0)
        _draw_header_badge_and_name(x, team, title_color, y_top, band_h)
        cur_y = y_top - band_h - 5*mm

        highlight = _top3_keys(skaters)

        # goalies
        c.setFillColor(MUTED); c.setFont(FONT_BOLD, 8)
        c.drawString(x, cur_y, "GOALIES")
        c.setStrokeColor(RULE); c.setLineWidth(0.4)
        c.line(x + 18*mm, cur_y + 2.5, x + col_w, cur_y + 2.5)
        cur_y -= 3*mm

        # Feature the top 3 goalies (by minutes played) as cards; any beyond 3 become a
        # compact "Also dressed" depth line. Teams with <=3 goalies render unchanged.
        carded = sorted(played_goalies, key=lambda g: (-g.mp, _jersey_sort_key(g.jersey)))
        extras = carded[3:]
        carded = carded[:3]
        n = len(carded)
        goalie_card_h = 19*mm
        gw = (col_w - max(n-1, 0)*3*mm) / max(n, 1)
        for i, g in enumerate(carded):
            gx = x + i*(gw + 3*mm)
            c.setFillColor(DIM_BG); c.setStrokeColor(RULE); c.setLineWidth(0.4)
            c.rect(gx, cur_y - goalie_card_h, gw, goalie_card_h, fill=1, stroke=1)
            # jersey
            num_fs = 17
            c.setFillColor(text_primary); c.setFont(FONT_BOLD, num_fs)
            c.drawString(gx + 3*mm, cur_y - goalie_card_h + 11*mm, g.jersey)
            num_w = c.stringWidth(g.jersey, FONT_BOLD, num_fs)
            name_x = gx + 3*mm + num_w + 2*mm
            name_max_w = (gx + gw) - name_x - 1.5*mm
            # surname auto-shrink
            last_fs = 11.5
            while c.stringWidth(g.last, FONT_SEMIBOLD, last_fs) > name_max_w and last_fs > 8:
                last_fs -= 0.5
            c.setFillColor(INK); c.setFont(FONT_SEMIBOLD, last_fs)
            c.drawString(name_x, cur_y - goalie_card_h + 12.5*mm, g.last)
            first_fs = 9
            while c.stringWidth(g.first, FONT_REGULAR, first_fs) > name_max_w and first_fs > 7:
                first_fs -= 0.5
            c.setFont(FONT_REGULAR, first_fs); c.setFillColor(SUBINK)
            c.drawString(name_x, cur_y - goalie_card_h + 8.5*mm, g.first)
            # stats
            c.setFont(FONT_REGULAR, 7.5); c.setFillColor(MUTED)
            c.drawString(gx + 3*mm, cur_y - goalie_card_h + 4.5*mm,
                         f"GP {g.gp}  ·  GAA {g.gaa}")
            c.drawString(gx + 3*mm, cur_y - goalie_card_h + 1.5*mm,
                         f"SV {g.sv_pct}")
        cur_y -= goalie_card_h
        if extras:
            cur_y -= 4*mm
            label = "Also dressed:   " + "    ·    ".join(
                f"#{g.jersey} {g.last} ({g.gp} GP, {g.sv_pct})" for g in extras)
            fs = 7.5
            while c.stringWidth(label, FONT_REGULAR, fs) > col_w and fs > 6:
                fs -= 0.5
            c.setFont(FONT_REGULAR, fs); c.setFillColor(MUTED)
            c.drawString(x, cur_y, label)
        cur_y -= 5*mm

        # skaters header
        c.setFillColor(MUTED); c.setFont(FONT_BOLD, 8)
        c.drawString(x, cur_y, "SKATERS")
        c.setStrokeColor(RULE); c.setLineWidth(0.4)
        c.line(x + 18*mm, cur_y + 2.5, x + col_w, cur_y + 2.5)
        cur_y -= 4*mm

        cap_x = x + 1.0*mm            # indicator column: C/A letter or IM/AF pill
        num_right = x + 14.0*mm       # jersey # right edge — kept wide enough that
                                       # a 2-digit jersey can't collide with an IM/AF
                                       # pill sharing this gutter.
        pos_left  = num_right + 1.0*mm
        pos_col_w = 5.6*mm            # just enough for the "POS" header label itself
        name_left = pos_left + pos_col_w + 0.8*mm
        pm_x  = x + col_w - 4*mm      # +/-, right-aligned (right edge of the column)
        pm_col_w = 7.5*mm
        a_x   = pm_x - pm_col_w
        g_x   = a_x  - 7*mm
        name_right = g_x - 5*mm

        c.setFillColor(MUTED); c.setFont(FONT_BOLD, 7)
        c.drawRightString(num_right, cur_y, "#")
        c.drawCentredString(pos_left + pos_col_w/2, cur_y, "POS")
        c.drawString(name_left, cur_y, "NAME")
        c.drawRightString(g_x, cur_y, "G")
        c.drawRightString(a_x, cur_y, "A")
        c.drawRightString(pm_x, cur_y, "+/-")
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

            num_color  = text_primary if not (dim or is_no_num) else (DIM if dim else MUTED)
            body_color = INK if not dim else DIM
            first_color = SUBINK if not dim else DIM

            if is_top3:
                c.setFillColor(HIGHLIGHT)
                c.rect(x, ry, col_w, row_h, fill=1, stroke=0)

            baseline = ry + row_h*0.32

            c.setFillColor(num_color); c.setFont(FONT_BOLD, num_fs)
            c.drawRightString(num_right, baseline, r.jersey)

            # Indicator column, left of the jersey #: captain/alternate captain
            # letters (team colour) and IM/AF pills (neutral, same colour
            # treatment as the name) both live here.
            if r.flag in ("C", "A"):
                cap_fs = 7.5 if not dim else 6
                cap_color = MUTED if dim else text_primary
                c.setFillColor(cap_color); c.setFont(FONT_BOLD, cap_fs)
                c.drawString(cap_x, baseline, r.flag)
            elif r.flag in ("IM", "AF"):
                pill_fs = flag_fs
                pill_text_w = c.stringWidth(r.flag, FONT_BOLD, pill_fs)
                pill_h = pill_fs + 1.6
                pill_y = baseline - pill_h*0.28
                c.setFillColor(DIM_BG); c.setStrokeColor(RULE); c.setLineWidth(0.4)
                c.roundRect(cap_x, pill_y, pill_text_w + 1.8*mm, pill_h, pill_h/2, fill=1, stroke=1)
                c.setFillColor(body_color); c.setFont(FONT_BOLD, pill_fs)
                c.drawString(cap_x + 0.9*mm, baseline, r.flag)

            # position, small-caps style: first letter full size, rest reduced
            pos_color = body_color
            pos_text = (r.position or "").upper()
            if pos_text:
                pos_big_fs, pos_small_fs = body_fs, body_fs * 0.72
                first_w = c.stringWidth(pos_text[0], FONT_BOLD, pos_big_fs)
                rest_w = c.stringWidth(pos_text[1:], FONT_BOLD, pos_small_fs) if len(pos_text) > 1 else 0
                total_w = first_w + (rest_w + 0.3 if rest_w else 0)
                start_x = pos_left + (pos_col_w - total_w) / 2
                c.setFillColor(pos_color); c.setFont(FONT_BOLD, pos_big_fs)
                c.drawString(start_x, baseline, pos_text[0])
                if len(pos_text) > 1:
                    c.setFont(FONT_BOLD, pos_small_fs)
                    c.drawString(start_x + first_w + 0.3, baseline, pos_text[1:])

            # surname (auto-shrink for very long names)
            last_fs = last_fs0
            last_text = r.last
            while c.stringWidth(last_text, FONT_SEMIBOLD, last_fs) > (name_right - name_left) * 0.7 and last_fs > 8.5:
                last_fs -= 0.5
            c.setFillColor(body_color); c.setFont(FONT_SEMIBOLD, last_fs)
            c.drawString(name_left, baseline, last_text)
            last_w = c.stringWidth(last_text, FONT_SEMIBOLD, last_fs)

            is_ro_flag = r.flag == "RO"
            ro_w = (c.stringWidth(r.flag, FONT_BOLD, flag_fs) + 1.6*mm) if is_ro_flag else 0

            # One space's worth of air between surname and first name, not two.
            first_x = name_left + last_w + 1.1*mm
            max_first_w = name_right - first_x - ro_w
            first_text = r.first
            # If the full first name doesn't fit, shrink it a touch before
            # resorting to truncation-with-a-period.
            first_fs_eff = first_fs
            min_first_fs = first_fs - (1.5 if not dim else 1.0)
            while (c.stringWidth(first_text, FONT_REGULAR, first_fs_eff) > max_first_w
                   and first_fs_eff > min_first_fs):
                first_fs_eff -= 0.5
            while c.stringWidth(first_text, FONT_REGULAR, first_fs_eff) > max_first_w and len(first_text) > 1:
                first_text = first_text[:-1]
            if first_text != r.first:
                first_text = first_text.rstrip() + "."
            c.setFillColor(first_color); c.setFont(FONT_REGULAR, first_fs_eff)
            c.drawString(first_x, baseline, first_text)
            first_text_w = c.stringWidth(first_text, FONT_REGULAR, first_fs_eff)
            tail_x = first_x + first_text_w + 1.4*mm

            if is_ro_flag:
                c.setFillColor(MUTED); c.setFont(FONT_BOLD, flag_fs)
                c.drawString(tail_x, baseline, r.flag)

            # G / A / +/- / Last all share one explicit style so none of them
            # silently inherit bold (or any other weight) from whatever was
            # drawn just before them.
            c.setFont(FONT_REGULAR, body_fs)
            if r.gp == 0:
                c.setFillColor(DIM)
                c.drawRightString(g_x, baseline, "–")
                c.drawRightString(a_x, baseline, "–")
            else:
                c.setFillColor(body_color)
                c.drawRightString(g_x, baseline, str(r.g))
                c.drawRightString(a_x, baseline, str(r.a))

            # +/- : "E" (even) as-is; otherwise ensure a sign so +7 isn't just "7".
            if r.plus_minus:
                pm = r.plus_minus
                if pm not in ("E", "e") and not pm.startswith(("+", "-")):
                    pm = f"+{pm}"
                c.setFillColor(body_color); c.setFont(FONT_REGULAR, body_fs - 1)
                c.drawRightString(pm_x, baseline, pm)

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
            c.setFillColor(MUTED); c.setFont(FONT_BOLD, 6.8)
            c.drawString(x + 2*mm, ry + divider_h/2 - 2, "NOT YET PLAYED THIS SEASON")
            for r in benched:
                ry -= benched_row_h
                draw_row(r, ry, benched_row_h, dim=True)

    # Move bench goalies into the skater "not yet played" group
    away_skaters_full, away_played_g = _merge_bench_goalies_into_skaters(away_skaters, away_goalies)
    home_skaters_full, home_played_g = _merge_bench_goalies_into_skaters(home_skaters, home_goalies)

    draw_team(left_x,  away_team, away_skaters_full, away_played_g)
    draw_team(right_x, home_team, home_skaters_full, home_played_g)

    # Footer
    footer_baseline = MARGIN + 1.5*mm

    # Legend: honey swatch = "top 3 in points" highlight used in the SKATERS tables
    legend_label = "Top 3 in points"
    swatch_w, swatch_h = 3.6*mm, 3.2*mm
    swatch_y = footer_baseline - 0.9*mm
    c.setFillColor(HIGHLIGHT); c.setStrokeColor(RULE); c.setLineWidth(0.4)
    c.rect(MARGIN, swatch_y, swatch_w, swatch_h, fill=1, stroke=1)
    c.setFillColor(MUTED); c.setFont(FONT_BOLD, 7.5)
    c.drawString(MARGIN + swatch_w + 1.6*mm, footer_baseline, legend_label)

    c.setFillColor(MUTED); c.setFont(FONT_REGULAR, 8.5)
    c.drawCentredString(PW/2, footer_baseline, game_info.footer_line)

    c.showPage()
    c.save()
    return out_path
