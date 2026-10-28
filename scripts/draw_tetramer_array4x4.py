"""Draw a 4x4 periodic extension of the supplied candidate, without a solver."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Polygon, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/2026-10-28_tetramer_array_4x4'
COLORS = ['#cc8650', '#3989a3', '#3989a3', '#cc8650']


def prism(vertices, bottom, top):
    low = np.column_stack((vertices, np.full(4, bottom)))
    high = np.column_stack((vertices, np.full(4, top)))
    return [low, high] + [np.array([low[i], low[(i+1) % 4],
                                    high[(i+1) % 4], high[i]]) for i in range(4)]


def main():
    prediction = json.loads((OUT / 'source_prediction.json').read_text(encoding='utf-8'))
    g = prediction['parameters']
    period, side, height, dx, dy = (g[k] for k in ('p', 'l', 'h', 'alpha_x', 'alpha_y'))
    odd, even = g['theta_odd_deg'], g['theta_even_deg']
    angles = [odd, even, even, odd]
    centers = np.array([[-1, -1], [-1, 1], [1, -1], [1, 1]])
    centers = centers * np.array([side+dx, side+dy]) / 2
    corners = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]]) * side / 2
    unit = []
    for center, angle in zip(centers, angles):
        theta = np.deg2rad(angle)
        rotation = np.array([[np.cos(theta), -np.sin(theta)],
                             [np.sin(theta), np.cos(theta)]])
        unit.append(corners @ rotation.T + center)
    assert all(np.abs(polygon).max() < period / 2 for polygon in unit)
    instances = []
    for iy in range(4):
        for ix in range(4):
            translation = np.array([ix-1.5, iy-1.5]) * period
            for quadrant, vertices in enumerate(unit):
                instances.append({'cell': [ix, iy], 'quadrant': ['III', 'II', 'IV', 'I'][quadrant],
                                  'angle_deg': angles[quadrant], 'color': COLORS[quadrant],
                                  'vertices_nm': (vertices+translation).tolist()})
    assert len(instances) == 64
    width = 4 * period / 1000
    edge = width / 2
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False,
                         'font.size': 11, 'svg.fonttype': 'none'})
    fig = plt.figure(figsize=(16, 8.8), facecolor='#fbfcfe')
    gs = fig.add_gridspec(1, 2, left=.06, right=.97, top=.85, bottom=.23,
                          width_ratios=(1, 1.16), wspace=.15)
    fig.suptitle(r'As$_2$Se$_3$ 四聚体 · 4 × 4 周期单元延拓', fontsize=23,
                 weight='bold', color='#203b51', y=.965)
    fig.text(.5, .91, '16 个周期单元 × 每单元 4 根柱 = 64 根柱',
             ha='center', fontsize=14, color='#556d80')

    top = fig.add_subplot(gs[0])
    top.set_facecolor('#f8f3df')
    for instance in instances:
        top.add_patch(Polygon(np.asarray(instance['vertices_nm'])/1000,
                              facecolor=instance['color'], edgecolor='#284958', linewidth=.7))
    for position in np.linspace(-edge, edge, 5):
        top.axvline(position, color='#9baab5', linestyle=(0, (4, 4)), lw=.75, alpha=.85)
        top.axhline(position, color='#9baab5', linestyle=(0, (4, 4)), lw=.75, alpha=.85)
    top.add_patch(Rectangle((-edge, -edge), width, width, fill=False,
                            edgecolor='#526e7f', linewidth=1.25))
    top.set(xlim=(-edge, edge), ylim=(-edge, edge), aspect='equal',
            xlabel='x / μm', ylabel='y / μm', title='俯视图 · 虚线为周期单元边界')
    top.set_xticks(np.linspace(-edge, edge, 5),
                   [f'{x:.3f}' for x in np.linspace(-edge, edge, 5)])
    top.set_yticks(np.linspace(-edge, edge, 5),
                   [f'{x:.3f}' for x in np.linspace(-edge, edge, 5)])
    top.tick_params(labelsize=9)

    view = fig.add_subplot(gs[1], projection='3d', computed_zorder=False)
    view.set_facecolor('#fbfcfe')
    footprint = np.array([[-edge, -edge], [edge, -edge], [edge, edge], [-edge, edge]])
    faces, colors = [], []
    # Thick glass is shown as a cropped slab, not a finite physical thickness.
    for bottom, upper, color in ((-.45, -.1, '#b8cddd'), (-.1, 0, '#d9b64f')):
        layer_faces = prism(footprint, bottom, upper)
        faces.extend(layer_faces)
        colors.extend([color]*len(layer_faces))
    view.add_collection3d(Poly3DCollection(faces, facecolors=colors, edgecolors='#3d5766',
                                         linewidths=.35, zsort='average', zorder=1))
    # Every pillar is above z=0. Draw them after the slab to prevent the large
    # gold face's mean-depth sorting from covering pillars in the back rows.
    faces, colors = [], []
    for instance in instances:
        current = prism(np.asarray(instance['vertices_nm'])/1000, 0, height/1000)
        faces.extend(current)
        colors.extend([instance['color']]*len(current))
    view.add_collection3d(Poly3DCollection(faces, facecolors=colors, edgecolors='#3d5766',
                                         linewidths=.35, zsort='average', zorder=2))
    view.set(xlim=(-edge, edge), ylim=(-edge, edge), zlim=(-.45, height/1000),
             xlabel='x / μm', ylabel='y / μm', zlabel='z / μm', title=r'三维图 · SiO$_2$ → Au → 四聚体')
    view.set_box_aspect((width, width, .45+height/1000))
    view.view_init(elev=29, azim=-56)
    view.tick_params(labelsize=8, pad=1)
    view.set_xticks([-1, 0, 1])
    view.set_yticks([-1, 0, 1])
    view.set_zticks([-.4, 0, .36])
    view.grid(False)

    handles = [Patch(facecolor=COLORS[0], label=f'I / III：{odd:.2f}°'),
               Patch(facecolor=COLORS[1], label=f'II / IV：{even:.2f}°'),
               Patch(facecolor='#d9b64f', label='Au 100 nm'),
               Patch(facecolor='#b8cddd', label=r'厚 SiO$_2$（截示）')]
    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(.5, .15),
               ncol=4, frameon=False, fontsize=12)
    fig.text(.5, .111, f'周期 P = {period:.2f} nm    |    阵列覆盖范围 {width:.3f} × {width:.3f} μm',
             ha='center', fontsize=12, color='#254659')
    fig.text(.5, .074, f'L = {side:.2f} nm    H = {height:.2f} nm    '
             f'dX = {dx:.2f} nm    dY = {dy:.2f} nm', ha='center', fontsize=11, color='#4b6375')
    fig.text(.5, .036, r'按所给图中候选参数重复平移；奇偶象限在每个单元内定义。两种柱色均为 As$_2$Se$_3$。',
             ha='center', fontsize=10, color='#657b8b')
    for suffix in ('png', 'svg'):
        fig.savefig(OUT / f'array_4x4.{suffix}', dpi=180, facecolor=fig.get_facecolor())
    svg = OUT / 'array_4x4.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',
                   encoding='utf-8', newline='\n')
    plt.close(fig)
    description = {'source': 'source_prediction.json', 'source_model_version': prediction['version'],
                   'source_seed': prediction['seed'], 'array_cells': [4, 4], 'pillar_count': 64,
                   'unit_period_nm': period, 'array_width_nm': 4*period,
                   'parameters': g, 'instances': instances,
                   'meaning': 'geometric periodic extension only; no finite-array electromagnetic simulation'}
    (OUT / 'array_geometry.json').write_text(json.dumps(description, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'image': str(OUT/'array_4x4.png'), 'pillars':64, 'width_um':width}, ensure_ascii=False))


if __name__ == '__main__':
    main()
