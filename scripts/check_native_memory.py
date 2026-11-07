"""Compile/run the real parser with tracked allocations and injected failures."""
import os
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sanitize', action='store_true', help='Enable AddressSanitizer and UndefinedBehaviorSanitizer (Linux GCC)')
    args = parser.parse_args()
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    executable = build / ('native_memory.exe' if os.name == 'nt' else 'native_memory')
    command = [os.environ.get('CC', 'gcc'), '-std=c11', '-D_POSIX_C_SOURCE=200809L',
               '-g', '-Wall', '-Wextra', '-Wno-unused-parameter',
               '-I', str(ROOT / 'include'), '-I', str(ROOT / 'tests'),
               '-include', str(ROOT / 'tests/native_alloc.h'),
               *map(str, sorted((ROOT / 'src').glob('*.c'))), str(ROOT / 'tests/native_memory.c'),
               '-o', str(executable)]
    if args.sanitize:
        command[1:1] = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    subprocess.run(command, check=True)
    invalid = build / 'invalid.vcf'
    invalid.write_bytes(b'BEGIN:VCARD\r\nVERSION:4.0\r\nFN:Invalid\r\nBDAY:T\r\nEND:VCARD\r\n')
    malformed = build / 'malformed.vcf'
    malformed.write_bytes(b'BEGIN:VCARD\r\nVERSION:4.0\r\nFN:Invalid\r\nX-TEST;BROKEN:value\r\nEND:VCARD\r\n')
    subprocess.run([str(executable), *map(str, sorted((ROOT / 'tests/fixtures/cards').glob('*.vcf'))),
                    str(invalid), str(malformed)], check=True)


if __name__ == '__main__':
    main()
