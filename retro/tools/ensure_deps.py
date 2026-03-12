"""
ensure_deps.py — Centralized dependency installer for all Keystone tools.

Usage:
    from tools.ensure_deps import ensure, ensure_all

    ensure('pefile')                    # install single package
    ensure_all(['pefile', 'capstone'])  # install multiple packages
"""

import subprocess
import sys


def ensure(package, import_name=None):
    """Install a package if it is not already importable.

    Args:
        package: pip package name (e.g. 'pefile')
        import_name: import name if different from package name (e.g. 'cv2' for 'opencv-python')
    """
    name_to_check = import_name or package
    try:
        __import__(name_to_check)
    except ImportError:
        print(f"[ensure_deps] Installing missing dependency: {package}")
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', package, '--quiet'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )


def ensure_all(packages):
    """Install multiple packages if missing.

    Args:
        packages: list of package names, or list of (package, import_name) tuples
    """
    for item in packages:
        if isinstance(item, tuple):
            ensure(item[0], item[1])
        else:
            ensure(item)


# Standard set used across Keystone tools
KEYSTONE_DEPS = [
    'pefile',
    'capstone',
    'rich',
    'requests',
]

# r2pipe requires radare2 binary — install separately, skip gracefully
OPTIONAL_DEPS = [
    ('r2pipe', 'r2pipe'),
]


def ensure_keystone_core():
    """Install all core Keystone dependencies."""
    ensure_all(KEYSTONE_DEPS)


def ensure_keystone_optional():
    """Install optional dependencies, skipping gracefully on failure."""
    for package, import_name in OPTIONAL_DEPS:
        try:
            ensure(package, import_name)
        except subprocess.CalledProcessError:
            print(f"[ensure_deps] WARNING: optional package '{package}' could not be installed — skipping")


if __name__ == '__main__':
    print("[ensure_deps] Installing Keystone core dependencies...")
    ensure_keystone_core()
    print("[ensure_deps] Installing optional dependencies...")
    ensure_keystone_optional()
    print("[ensure_deps] Done.")
