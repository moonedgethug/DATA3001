"""Read-only diagnostic plots of the nine preselected trajectory windows."""
import os
from pathlib import Path
OUT = Path(__file__).resolve().parents[1]
os.environ['MPLCONFIGDIR'] = str(OUT/'logs/mplconfig')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

rows = pd.read_csv(OUT/'results/case_review_rows.csv')
paths = pd.read_csv(OUT/'results/case_review_paths.csv')
fig, axes = plt.subplots(3, 3, figsize=(15, 13))
labels = {'looping_evidence':'Turning motion', 'consistent_drift_evidence':'Multi-day progress', 'suspected_local_stay':'Suspected residence'}
for ax, row in zip(axes.flat, rows.itertuples()):
    g = paths[(paths.id == row.id) & (paths.origin_source_obs == row.origin_source_obs)].sort_values('offset_hour')
    ax.plot(g.east_km, g.north_km, color='#bbbbbb', lw=1, zorder=1)
    p = ax.scatter(g.east_km, g.north_km, c=g.offset_hour, cmap='coolwarm', vmin=-72, vmax=72, s=9, zorder=2)
    ax.scatter([0], [0], marker='*', s=90, c='black', zorder=4)
    if row.path_evidence == 'suspected_local_stay':
        ax.add_patch(plt.Circle((0,0), 1, color='black', fill=False, ls='--'))
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_title(f'{labels[row.path_evidence]} | {row.id}\n' + pd.to_datetime(row.target_epoch, unit='s', utc=True).strftime('%Y-%m-%d %H:%M UTC'), fontsize=10)
    ax.set_xlabel('East of seven-day endpoint (km)')
    ax.set_ylabel('North (km)')
    ax.grid(alpha=.2)
fig.subplots_adjust(hspace=.45, wspace=.33, right=.91, top=.90)
cax = fig.add_axes([.93, .2, .015, .6])
fig.colorbar(p, cax=cax, label='Hours relative to seven-day endpoint')
fig.suptitle('Available hourly paths, -72 to +72 hours; star = target time\nEach panel uses its own distance scale; this is a diagnostic, not a model comparison', fontsize=13)
fig.savefig(OUT/'results/representative_trajectories.png', dpi=130)
plt.close(fig)
print('Saved nine trajectory examples')
