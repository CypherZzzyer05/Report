"""Read-only native FDTD material audit; never run, save or modify a model."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--lumapi', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, api = args.project.resolve(), args.lumapi.resolve()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(str(api.parent))
    spec = importlib.util.spec_from_file_location('lumapi', api)
    lumapi = importlib.util.module_from_spec(spec); spec.loader.exec_module(lumapi)
    report = dict(source_sha256_before=before, read_only=True,
                  solver_run_performed=False, material_modified=False, save_performed=False)
    with lumapi.FDTD(filename=str(source), hide=True) as session:
        report['version'] = str(session.version())
        lo = float(session.getnamed('source', 'wavelength start'))*1e9
        hi = float(session.getnamed('source', 'wavelength stop'))*1e9
        wavelength = np.linspace(lo, hi, 1000)
        frequency = 299792458/(wavelength*1e-9)
        name = 'Au (Gold) - Palik'
        raw = np.asarray(session.getindex(name, frequency)).reshape(-1)
        fitted = np.asarray(session.getfdtdindex(name, frequency, frequency.min(), frequency.max())).reshape(-1)
        eps, epsfit = raw**2, fitted**2
        report.update(source_wavelength_start_nm=lo, source_wavelength_stop_nm=hi,
                      raw_imag_epsilon_range=[float(eps.imag.min()), float(eps.imag.max())],
                      fitted_imag_epsilon_range=[float(epsfit.imag.min()), float(epsfit.imag.max())],
                      max_imaginary_permittivity_error=float(max(abs(eps.imag-epsfit.imag))))
        for prop in ('tolerance', 'max coefficients', 'imaginary weight', 'make fit passive', 'specify fit range'):
            report[prop] = float(np.asarray(session.getmaterial(name, prop)).item())
        points = []
        for target in (700, 805.105, 1129.429, 1550, 1700):
            i = int(np.argmin(abs(wavelength-target)))
            points.append(dict(wavelength_nm=float(wavelength[i]), raw_n=float(raw[i].real),
                               raw_k=float(raw[i].imag), fitted_n=float(fitted[i].real),
                               fitted_k=float(fitted[i].imag), raw_imag_epsilon=float(eps[i].imag),
                               fitted_imag_epsilon=float(epsfit[i].imag)))
        report['selected_points'] = points
    report['source_sha256_after'] = hashlib.sha256(source.read_bytes()).hexdigest()
    report['source_hash_unchanged'] = report['source_sha256_after'] == before
    if not report['source_hash_unchanged']:
        raise RuntimeError('Original project checksum changed')
    (args.output/'native_material_audit.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    with (args.output/'au_checkpoints.csv').open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=list(points[0])); writer.writeheader(); writer.writerows(points)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
