"""Rebuild figures and report from two real local FDTD exports (no solver run)."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import least_squares
from scipy.signal import find_peaks, peak_widths


def read_npz(path):
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key].copy() for key in data.files}


def copy_provenance(source, target):
    if source.suffix != '.log':
        shutil.copyfile(source, target)
        return
    # Native engine launch lines embed shared license context. Publish only
    # numerical progress and diagnostics; retain original logs locally.
    text = source.read_text(errors='replace')
    blocked = ('license', 'licensing', 'expires (', 'running fsp file:', 'running on host:')
    lines = ['[runtime identity / licensing line omitted]' if any(x in line.lower() for x in blocked)
             else line for line in text.splitlines()]
    target.write_text('\n'.join(lines)+'\n', encoding='utf-8', newline='\n')


def features(wavelength, signal, sign=-1, relative=False):
    prominence = max(float(np.ptp(signal))*.03, 1e-10) if relative else .03
    peaks, props = find_peaks(sign*signal, prominence=prominence)
    widths = peak_widths(sign*signal, peaks, rel_height=.5)
    return [dict(index=int(i), wavelength_nm=float(wavelength[i]), value=float(signal[i]),
                 prominence=float(prom), half_prominence_width_nm=float(width*np.diff(wavelength).mean()))
            for i, prom, width in zip(peaks, props['prominences'], widths[0])]


def q_candidates(wavelength, transmission, status, time_ps):
    """Screen fits in frequency; never equate half prominence width with mode FWHM."""
    if status != 2:
        return [], ['未达到自动关断阈值，不从截断谱发布 Q 候选值。']
    accepted, rejected = [], []
    for sign, label in [(1, '透射峰'), (-1, '透射谷')]:
        for item in features(wavelength, transmission, sign=sign, relative=True):
            width, center = item['half_prominence_width_nm'], item['wavelength_nm']
            mask = abs(wavelength-center) <= max(3*width, 10)
            if mask.sum() < 15 or width < 8*np.diff(wavelength).mean():
                rejected.append(f'{label} {center:.2f} nm：线宽采样不足。')
                continue
            f = 299792.458/wavelength[mask]  # THz, lambda in nm.
            raw = transmission[mask]
            scale = float(np.ptp(raw))
            if scale <= 1e-10:
                continue
            y = raw/scale
            fc = 299792.458/center
            df = 299792.458*width/center**2
            span = float(np.ptp(f))
            def model(x):
                b, slope, a, f0, gamma = x
                return b+slope*(f-fc)/span+a/(1+4*((f-f0)/gamma)**2)
            x0 = [float(np.median(y)), 0., float(sign), fc, df]
            fit = least_squares(lambda x: model(x)-y, x0,
                                bounds=([-np.inf, -np.inf, -5 if sign < 0 else 0, min(f), df/5],
                                        [np.inf, np.inf, 0 if sign < 0 else 5, max(f), span]),
                                max_nfev=3000)
            b, slope, a, f0, gamma = fit.x
            r2 = 1-float(np.sum((model(fit.x)-y)**2)/np.sum((y-y.mean())**2))
            linewidth_nm = 299792.458*gamma/f0**2
            resolved = linewidth_nm/float(np.diff(wavelength).mean())
            edge_distance = min(abs(f0-min(f)), abs(max(f)-f0))
            valid = (fit.success and r2 >= .98 and resolved >= 8
                     and gamma >= 3/time_ps and edge_distance >= 1.5*gamma
                     and abs(299792.458/f0-center) <= width)
            if not valid:
                rejected.append(f'{label} {center:.2f} nm：孤立 Lorentz 线型/采样/时间分辨率筛选未通过（R²={r2:.4f}）。')
                continue
            accepted.append(dict(type=label, center_nm=float(299792.458/f0), f0_THz=float(f0),
                                 fitted_FWHM_THz=float(gamma), equivalent_FWHM_nm=float(linewidth_nm),
                                 Q_fit=float(f0/gamma), fit_r2=r2,
                                 linewidth_grid_intervals=resolved, precision_certified=False))
    return accepted, rejected


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--finite-dir', type=Path, required=True)
    parser.add_argument('--pml-dir', type=Path, required=True)
    parser.add_argument('--generator-dir', type=Path, required=True)
    parser.add_argument('--strict-dir', type=Path, help='Same glass/metal mesh with a stricter shutoff threshold')
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parents[1]/'reports/2026-10-18_topmetal_thick_substrate')
    args = parser.parse_args()
    out = args.output
    for name in ('figures', 'data', 'provenance'):
        (out/name).mkdir(parents=True, exist_ok=True)
    old = read_npz(args.finite_dir/'historical_server_sample0.npz')
    finite, thick = [read_npz(p/'result.npz') for p in (args.finite_dir, args.pml_dir)]
    wavelength = thick['wavelength_nm']
    for case in (old, finite):
        if not np.allclose(case['wavelength_nm'], wavelength, atol=1e-5, rtol=0):
            raise ValueError('Cannot compare different wavelength grids')
    if str(thick['substrate_termination']) != 'pml' or str(thick['transmission_medium']) != 'SiO2':
        raise ValueError('Target export must explicitly identify transmission inside a PML substrate')
    preflight = json.loads((args.pml_dir/'preflight.json').read_text(encoding='utf-8-sig'))
    settings = json.loads(str(thick['settings_json']))
    status, t_ps = int(thick['status']), float(thick['simulation_time_ps'])
    automatic = status == 2
    cases = [dict(name='旧版：Au / SiO2 / 四聚体', R=old['spectra'], T=old['transmittance'],
                  label='旧版：Au / 有限 SiO2 / 四聚体；T 在空气', status=2),
             dict(name='上金膜 / 有限基板诊断', R=finite['reflectance'], T=finite['transmittance'],
                  label='上金膜 / 有限 SiO2；1 ps 未自动关断', status=int(finite['status'])),
             dict(name='目标：厚 SiO2 / Au / 四聚体', R=thick['reflectance'], T=thick['transmittance'],
                  label='厚 SiO2 / Au / 四聚体；T 在玻璃', status=status)]
    summary = []
    for case in cases:
        case['R_features'] = features(wavelength, case['R'])
        case['T_peaks'] = features(wavelength, case['T'], sign=1, relative=True)
        case['T_dips'] = features(wavelength, case['T'], sign=-1, relative=True)
        summary.append({k: v for k, v in case.items() if k not in ('R', 'T')}
                       | dict(R_min=float(min(case['R'])), R_max=float(max(case['R'])),
                              T_min=float(min(case['T'])), T_max=float(max(case['T']))))
    solver_text = (args.pml_dir/'sample0_p0.log').read_text(errors='replace')
    completed = re.findall(r'Completed \d+ iterations, or ([0-9.eE+-]+)s', solver_text)
    observed = re.findall(r'Elapsed simulation time: ([0-9.eE+-]+) secs', solver_text)
    actual_time_ps = float((completed or observed)[-1])*1e12
    qs, rejected = q_candidates(wavelength, thick['transmittance'], status, actual_time_ps)
    result = dict(geometry_values=thick['geometry_values'].tolist(), cases=summary,
                  actual_settings=settings, native_preflight=preflight,
                  auto_shutoff_reached=automatic, solver_status=status,
                  numerical_precision_certified=False, dataset_quality_level='pipeline_validation',
                  actual_solver_wall_seconds=float(thick['elapsed_seconds']),
                  time_limit_ps=t_ps, actual_propagation_time_ps=actual_time_ps,
                  Q_fit_candidates=qs, Q_rejected=rejected,
                  max_absolute_delta_R_thick_vs_finite=float(abs(thick['reflectance']-finite['reflectance']).max()),
                  mean_absolute_delta_R_thick_vs_finite=float(abs(thick['reflectance']-finite['reflectance']).mean()),
                  max_absolute_delta_R_thick_vs_old=float(abs(thick['reflectance']-old['spectra']).max()),
                  note='Finite local spectrum is not auto-shutoff converged; old server version differs. Differences are previews.')
    plt.rcParams.update({'font.sans-serif': ['Microsoft YaHei', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    colors = ['#76899A', '#D59639', '#1768AC']
    for case, color in zip(cases, colors):
        axes[0].plot(wavelength, case['R'], color=color, lw=1.5, label=case['label'])
        axes[1].plot(wavelength, case['T']*100, color=color, lw=1.5)
        axes[2].semilogy(wavelength, case['T'], color=color, lw=1.3)
    axes[0].set(ylabel='反射率 R', ylim=(-.02, 1.04))
    axes[0].legend(loc='best', fontsize=9)
    axes[1].set(ylabel='透射率 T (%)')
    axes[2].set(ylabel='透射率 T（对数）', xlabel='波长 (nm)', xlim=(700, 1700))
    for ax in axes:
        ax.grid(alpha=.2)
    label = '已触发 1e-5 自动关断' if automatic else '未自动关断，仅作诊断'
    fig.suptitle(f'SiO2 / Au100 / As2Se3：真实 R / T 光谱\n目标模型：{label}', fontsize=15)
    fig.text(.08, .018, '所有层序按从下到上书写。旧谱来自 v251；两个本机测试用 v241。时间、材料和网格精度尚未全部认证。', fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, .94))
    fig.savefig(out/'figures/spectra.png', dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    axes[0].plot(wavelength, thick['reflectance'], color=colors[2])
    axes[1].plot(wavelength, thick['transmittance']*100, color=colors[2])
    for feat in summary[2]['R_features']:
        axes[0].annotate(f"{feat['wavelength_nm']:.1f} nm", (feat['wavelength_nm'], feat['value']),
                         xytext=(8, 20), textcoords='offset points', fontsize=9,
                         arrowprops=dict(arrowstyle='-', color='#555555'))
    axes[0].set(ylabel='反射率 R', ylim=(0, 1))
    axes[1].set(ylabel='透射率 T (%)', xlabel='波长 (nm)', xlim=(700, 1700))
    for ax in axes:
        ax.grid(alpha=.2)
    fig.suptitle(f'目标厚基板模型单独展示：{label}', fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(out/'figures/target_spectra.png', dpi=180)
    plt.close(fig)
    for path, name in [(args.finite_dir/'result.npz', 'finite_topmetal_diagnostic.npz'),
                       (args.pml_dir/'result.npz', 'pml_topmetal_sample0.npz'),
                       (args.finite_dir/'historical_server_sample0.npz', 'historical_sample0.npz')]:
        shutil.copyfile(path, out/'data'/name)
    with (out/'data/spectra.csv').open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow(['wavelength_nm', 'R_old', 'T_old_air', 'R_finite_diagnostic',
                         'T_finite_air_diagnostic', 'R_thick', 'T_thick_SiO2'])
        writer.writerows(zip(wavelength, old['spectra'], old['transmittance'], finite['reflectance'],
                              finite['transmittance'], thick['reflectance'], thick['transmittance']))
    for prefix, folder in [('finite', args.finite_dir), ('pml', args.pml_dir)]:
        for filename in ['settings.json', 'preflight.json', 'state.json', 'material_identity.json', 'sample0_p0.log']:
            p = folder/filename
            if p.exists():
                target_name = filename.replace('.log', '.txt')
                copy_provenance(p, out/'provenance'/f'{prefix}_{target_name}')
    if args.strict_dir:
        strict = read_npz(args.strict_dir/'result.npz')
        strict_settings = json.loads(str(strict['settings_json']))
        # Verify this comparison changes only the duration/threshold controls.
        changing = {'auto_shutoff_min', 'simulation_time_ps'}
        if any(settings[k] != strict_settings[k] for k in settings if k not in changing):
            raise ValueError('Strict time check changed another simulation setting')
        if not np.array_equal(thick['geometry_values'], strict['geometry_values']):
            raise ValueError('Time check changed geometry')
        if not np.array_equal(thick['wavelength_nm'], strict['wavelength_nm']):
            raise ValueError('Time check changed wavelength samples')
        for axis in ('x', 'y', 'z'):
            if not np.array_equal(thick[f'mesh_{axis}_nm'], strict[f'mesh_{axis}_nm']):
                raise ValueError('Time check changed actual mesh')
        matched = []
        strict_features = features(wavelength, strict['reflectance'])
        for previous in summary[2]['R_features']:
            after = min(strict_features, key=lambda x: abs(x['wavelength_nm']-previous['wavelength_nm']))
            matched.append(dict(base=previous, strict=after,
                                shift_nm=after['wavelength_nm']-previous['wavelength_nm'],
                                depth_delta=after['value']-previous['value'],
                                width_relative_delta=after['half_prominence_width_nm']/previous['half_prominence_width_nm']-1))
        result['time_check'] = dict(strict_status=int(strict['status']),
                                  strict_threshold=float(strict_settings['auto_shutoff_min']),
                                  base_threshold=float(settings['auto_shutoff_min']),
                                  strict_time_limit_ps=float(strict['simulation_time_ps']),
                                  wall_seconds=float(strict['elapsed_seconds']),
                                  maximum_R_delta=float(max(abs(strict['reflectance']-thick['reflectance']))),
                                  maximum_T_delta=float(max(abs(strict['transmittance']-thick['transmittance']))),
                                  features=matched)
        result['same_1ps_substrate_comparison'] = dict(
            maximum_R_delta=float(max(abs(strict['reflectance']-finite['reflectance']))),
            mean_R_delta=float(np.mean(abs(strict['reflectance']-finite['reflectance']))),
            maximum_T_delta=float(max(abs(strict['transmittance']-finite['transmittance']))),
            note='Equal 1 ps duration, both time limited. T is inside SiO2 for thick case and in air for finite case.')
        text = (args.strict_dir/'sample0_p0.log').read_text(errors='replace')
        times = re.findall(r'Completed \d+ iterations, or ([0-9.eE+-]+)s', text)
        if times:
            strict_t_ps = float(times[-1])*1e12
            result['time_check']['propagation_time_ps'] = strict_t_ps
            strict_qs, strict_rejected = q_candidates(wavelength, strict['transmittance'], int(strict['status']), strict_t_ps)
            result['time_check'].update(Q_fit_candidates=strict_qs, Q_rejected=strict_rejected)
        fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
        strict_label = '阈值 1e-7（1 ps 到限，未达到）' if int(strict['status']) == 1 else '已达到阈值 1e-7'
        for case, name, color in [(thick, '已达到阈值 1e-5', '#D59639'), (strict, strict_label, '#1768AC')]:
            axes[0].plot(wavelength, case['reflectance'], color=color, label=name, lw=1.5)
            axes[1].plot(wavelength, case['transmittance']*100, color=color, lw=1.5)
        axes[2].plot(wavelength, (strict['reflectance']-thick['reflectance'])*100, color='#1768AC')
        axes[0].set(ylabel='反射率 R')
        axes[0].legend()
        axes[1].set(ylabel='透射率 T (%)')
        axes[2].set(ylabel='反射率差（百分点）', xlabel='波长 (nm)', xlim=(700, 1700))
        for ax in axes:
            ax.grid(alpha=.2)
        fig.suptitle('相同结构、材料、原生网格：收紧时间衰减阈值的影响', fontsize=14)
        fig.tight_layout(rect=(0, 0, 1, .95))
        fig.savefig(out/'figures/time_check.png', dpi=180)
        plt.close(fig)
        shutil.copyfile(args.strict_dir/'result.npz', out/'data/pml_topmetal_strict.npz')
        for filename in ('settings.json', 'state.json', 'sample0_p0.log'):
            copy_provenance(args.strict_dir/filename, out/'provenance'/('strict_'+filename.replace('.log', '.txt')))
        with (out/'data/time_check.csv').open('w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow(['wavelength_nm', 'R_1e5', 'T_1e5', 'R_strict_1ps', 'T_strict_1ps'])
            writer.writerows(zip(wavelength, thick['reflectance'], thick['transmittance'],
                                  strict['reflectance'], strict['transmittance']))
    shutil.copyfile(args.generator_dir/'artifacts/checksums.json', out/'provenance/generator_wheel.json')
    result['file_sha256'] = {str(p.relative_to(out)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted((out/'data').iterdir()) if p.is_file()}
    (out/'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('native_preflight', 'actual_settings', 'cases')},
                     ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
