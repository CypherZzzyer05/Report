"""Local numerical audit and figures. No FDTD engine run or material changes."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--generator-dir', type=Path, required=True)
    parser.add_argument('--native-audit-dir', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root/'reports/2026-10-18_device_feasibility'
    output.mkdir(exist_ok=True, parents=True)
    for name in ('data', 'figures'):
        (output/name).mkdir(exist_ok=True)
    source = args.generator_dir/'src/deta_generator2/assets/materials/as2se3_joseph_700nm.csv'
    raw = np.loadtxt(source, delimiter=',', skiprows=1)
    old = np.load(root/'reports/2026-10-18_topmetal_thick_substrate/data/pml_topmetal_sample0.npz')
    geometry = old['geometry_values']
    wavelengths = np.array([700., 805.1051051051052, 1129.4294294294295, 1550., 1688.])
    n = np.interp(wavelengths, raw[:, 0], raw[:, 1])
    k = np.interp(wavelengths, raw[:, 0], raw[:, 2])
    transmission = np.exp(-4*np.pi*k*geometry[2]/wavelengths)
    rows = [dict(wavelength_nm=float(w), n=float(a), k=float(b),
                 uniform_medium_single_pass_intensity_fraction=float(c))
            for w, a, b, c in zip(wavelengths, n, k, transmission)]
    data = dict(calculation_type='material scale illustration, not device absorptance or modal Q',
                source_csv_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                resonator_height_nm=float(geometry[2]), source_film_thickness_nm=700,
                measured_stop_nm=1688, extrapolated_1688_to_1700=True,
                checkpoints=rows, no_new_fdtd_simulation=True,
                substrate_index_from_archived_fit=1.45051927,
                glass_first_diffraction_cutoff_nm=float(1.45051927*geometry[0]))
    (output/'data/material_scale.json').write_text(json.dumps(data, indent=2)+'\n', encoding='utf-8')
    with (output/'data/as2se3_checkpoints.csv').open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    native = json.loads((args.native_audit_dir/'native_material_audit.json').read_text())
    (output/'data/native_material_audit.json').write_text(json.dumps(native, indent=2)+'\n', encoding='utf-8')
    with (output/'data/au_checkpoints.csv').open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=list(native['selected_points'][0])); writer.writeheader(); writer.writerows(native['selected_points'])
    gold = np.genfromtxt(args.native_audit_dir/'au_raw_vs_native_fit.csv', delimiter=',', names=True)
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'DejaVu Sans'], 'axes.unicode_minus': False,
                         'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.1))
    axes[0].plot(gold['wavelength_nm'], gold['raw_n'], color='#194e77', label='原生 Palik 数据 n')
    axes[0].plot(gold['wavelength_nm'], gold['fitted_n'], color='#b35430', label='存档 FDTD 拟合 n')
    axes[0].set(xlabel='波长 (nm)', ylabel='折射率实部 n', title='金膜拟合的 n 几乎为零')
    axes[1].semilogy(gold['wavelength_nm'], gold['raw_imag_epsilon'], color='#194e77', label='原生 Palik Im(ε)')
    axes[1].semilogy(gold['wavelength_nm'], gold['fitted_imag_epsilon'], color='#b35430', label='存档 FDTD 拟合 Im(ε)')
    axes[1].set(xlabel='波长 (nm)', ylabel='Im(ε) = 2nk', title='欧姆吸收损耗与原数据严重不符')
    for ax in axes:
        ax.grid(alpha=.2); ax.legend(fontsize=9); ax.set_xlim(700, 1700)
    fig.tight_layout()
    fig.savefig(output/'figures/gold_fit_audit.png', dpi=190)
    plt.close(fig)
    use = (raw[:, 0] >= 700) & (raw[:, 0] <= 1688)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.1))
    axes[0].plot(raw[use, 0], raw[use, 2], color='#194e77')
    axes[0].set(xlabel='波长 (nm)', ylabel='As2Se3 原始 k', title='Joseph 700 nm 薄膜：不能设 k = 0')
    axes[1].plot(raw[use, 0], np.exp(-4*np.pi*raw[use, 2]*geometry[2]/raw[use, 0]), color='#194e77')
    axes[1].set(xlabel='波长 (nm)', ylabel='I(H) / I(0)', ylim=(.5, 1), title='仅均匀材料单程衰减，非器件透射率')
    for ax in axes:
        ax.grid(alpha=.2); ax.set_xlim(700, 1700)
    fig.tight_layout(); fig.savefig(output/'figures/as2se3_material_scale.png', dpi=190); plt.close(fig)
    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    main()
