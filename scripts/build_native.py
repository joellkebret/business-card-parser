"""Build the native parser with a C11 GCC-compatible compiler."""
import argparse
import os
from pathlib import Path
import platform
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = 'vcparser.dll' if os.name == 'nt' else ('libvcparser.dylib' if platform.system() == 'Darwin' else 'libvcparser.so')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'build' / LIBRARY
    if args.clean:
        output.unlink(missing_ok=True)
        return
    output.parent.mkdir(exist_ok=True)
    command = [os.environ.get('CC', 'gcc'), '-std=c11', '-D_POSIX_C_SOURCE=200809L',
               '-Wall', '-Wextra', '-Wno-unused-parameter', '-O2', '-fPIC',
               *shlex.split(os.environ.get('CFLAGS', '')), '-shared', '-I', str(ROOT / 'include'),
               *map(str, sorted((ROOT / 'src').glob('*.c'))), '-o', str(output)]
    subprocess.run(command, check=True)
    print(output)

if __name__ == '__main__':
    main()
