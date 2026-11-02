"""Shared static map and table rendering; no fitting or trajectory access."""
from html import escape
import numpy as np

def markdown_table(frame, columns):
    def value(x):
        if isinstance(x, (float, np.floating)):
            return 'NA' if np.isnan(x) else 'inf' if np.isinf(x) else f'{x:.6g}'
        return str(x)
    lines = ['| '+' | '.join(columns)+' |', '| '+' | '.join(['---']*len(columns))+' |']
    lines += ['| '+' | '.join(value(x) for x in row)+' |' for row in frame[columns].itertuples(index=False, name=None)]
    return '\n'.join(lines)


def map_svg(panels, land_rings, release_rings, origin, days, fold):
    width, height = 1200, 800
    x0, x1, y0, y1 = -83., -6., 19., 56.
    maximum = max([p for _, dist, _ in panels for c, p in dist.items() if c >= 0] or [1.])
    maximum = maximum or 1.
    result = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
              '<rect width="100%" height="100%" fill="white"/>',
              '<g font-family="Arial, sans-serif" fill="#182a3a">',
              f'<text x="25" y="28" font-size="20">{days} days | pooled stopped target | outer held-out fold {fold}</text>',
              f'<text x="25" y="51" font-size="13">Release cell {origin}; Shared scale: 0 to {maximum*100:.1f}% probability per cell. No renormalisation.</text>']
    for panel, (title, distribution, u) in enumerate(panels):
        left, top = 45+(panel % 2)*590, 100+(panel//2)*340
        w, h = 540, 260
        def xy(lon, lat):
            return left+(lon-x0)/(x1-x0)*w, top+(y1-lat)/(y1-y0)*h
        result.append(f'<text x="{left}" y="{top-14}" font-size="17">{escape(title)}</text>')
        result.append(f'<rect x="{left}" y="{top}" width="{w}" height="{h}" fill="#f4f8fa" stroke="#b0bdc5"/>')
        for cell, p in distribution.items():
            if cell < 0 or p <= 0:
                continue
            lon, lat = -180+cell % 360, -90+cell//360
            x, y = xy(lon, lat+1)
            t = min(1., p/maximum)
            red, green, blue = int(255-100*t), int(250-230*t), int(252-130*t)
            result.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{w/(x1-x0):.3f}" height="{h/(y1-y0):.3f}" fill="rgb({red},{green},{blue})"/>')
        def rings_path(rings):
            chunks = []
            for ring in rings:
                points = [xy(lon, lat) for lon, lat in ring]
                chunks.append('M'+' L'.join(f'{x:.2f},{y:.2f}' for x, y in points)+' Z')
            return ' '.join(chunks)
        if land_rings:
            result.append(f'<path d="{rings_path(land_rings)}" fill="#d9dedf" fill-rule="evenodd" stroke="#7c898f" stroke-width="0.5"/>')
        if release_rings:
            result.append(f'<path d="{rings_path(release_rings)}" fill="none" stroke="#1d6a48" stroke-width="1.2"/>')
        ox, oy = xy(-180+origin % 360, -90+origin//360+1)
        result.append(f'<rect x="{ox:.3f}" y="{oy:.3f}" width="{w/(x1-x0):.3f}" height="{h/(y1-y0):.3f}" fill="none" stroke="#00a55b" stroke-width="2"/>')
        for lon in [-80, -60, -40, -20]:
            x, y = xy(lon, y0)
            result.append(f'<text x="{x-13:.1f}" y="{y+16:.1f}" font-size="11">{abs(lon)} W</text>')
        for lat in [20, 30, 40, 50]:
            x, y = xy(x0, lat)
            result.append(f'<text x="{x-33:.1f}" y="{y+4:.1f}" font-size="11">{lat} N</text>')
        result.append(f'<text x="{left}" y="{top+h+37}" font-size="12">OUTSIDE {distribution.get(-2, 0.)*100:.3f}% | unresolved {u*100:.3f}% | geographic mass {sum(p for c,p in distribution.items() if c>=0)*100:.3f}%</text>')
    result += ['<text x="25" y="791" font-size="11">Equirectangular display; cell probability, not density or confirmed grounding. Grey land can obscure coastal cell fills.</text>', '</g></svg>']
    return ''.join(result)


def _rings(geometry):
    parts = list(geometry.geoms) if geometry.geom_type == 'MultiPolygon' else [geometry]
    return [list(r.coords) for p in parts if p.geom_type == 'Polygon' for r in [p.exterior, *p.interiors]]
