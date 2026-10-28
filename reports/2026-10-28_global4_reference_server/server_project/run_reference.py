"""Run one fixed global-4-nm / metal-2-nm reference with the bundled generator."""
import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXPECTED = [649.7604076511419, 161.1566330153756, 284.88377288849,
            133.54673339593725, 116.4992120505661, -33.64481402341028,
            39.36335222367701]
SERVER_API = r'E:\Lumerical\ANSYS Inc\v251\Lumerical\api\python\lumapi.py'


def check_reference():
    import deta_generator2
    import numpy as np
    from deta_generator2.config import load_config

    if deta_generator2.__version__ != '2.2.0':
        raise ValueError('Install artifacts/deta_generator2-2.2.0-py3-none-any.whl in this interpreter first.')
    config = load_config(ROOT / 'job.json')
    if config.sample_count != 1:
        raise ValueError('This reference must contain exactly one sample.')
    settings = config.simulation
    actual = (settings.mesh_policy, settings.maximum_mesh_nm, settings.mesh_nm,
              settings.metal_mesh_nm, settings.metal_thickness_nm,
              settings.metal_position, settings.substrate_termination)
    if actual != ('legacy', 4., 4., 2., 100., 'above_substrate', 'pml'):
        raise ValueError(f'Reference mesh or layer settings changed: {actual}')
    geometry = config.geometry_values(config.sample_geometries()[0])
    np.testing.assert_allclose(geometry, EXPECTED, rtol=0, atol=1e-8)
    return {'generator': deta_generator2.__version__, 'samples': 1,
            'geometry_values': geometry.tolist(), 'global_mesh_nm': 4,
            'metal_mesh_nm': 2, 'output_dir': str(config.output_dir)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'run'), nargs='?', default='run')
    parser.add_argument('--lumapi', default=os.environ.get('LUMERICAL_LUMAPI_PATH', SERVER_API))
    parser.add_argument('--threads', type=int, default=32)
    args = parser.parse_args()
    (ROOT / 'tmp').mkdir(exist_ok=True)
    os.environ['TEMP'] = str(ROOT / 'tmp')
    os.environ['TMP'] = str(ROOT / 'tmp')
    print(json.dumps(check_reference(), ensure_ascii=False, indent=2), flush=True)
    if args.command == 'check':
        print('Offline identity check passed. No solver was opened.', flush=True)
        return 0
    from deta_generator2.cli import main as generator_main
    common = ['--config', str(ROOT / 'job.json'), '--lumapi', args.lumapi,
              '--threads', str(args.threads)]
    print('Native preflight: checking materials, layout, actual mesh and resources.', flush=True)
    code = generator_main(['preflight', *common])
    if code:
        return code
    print('Preflight passed. Starting the single fixed reference; successful data are reused on restart.', flush=True)
    return generator_main(['generate', *common, '--limit', '1', '--fail-fast'])


if __name__ == '__main__':
    raise SystemExit(main())
