"""
Language & Technology Stack Detector
Scans a codebase and identifies: primary language, all languages present,
build systems, hardware APIs, platform targets, and frameworks.
"""

from pathlib import Path
from collections import Counter
import re

EXTENSION_MAP = {
    '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
    '.tsx': 'TypeScript/React', '.jsx': 'JavaScript/React',
    '.c': 'C', '.h': 'C/C++ Header', '.cpp': 'C++', '.cc': 'C++',
    '.cxx': 'C++', '.hpp': 'C++ Header', '.cs': 'C#', '.java': 'Java',
    '.go': 'Go', '.rs': 'Rust', '.rb': 'Ruby', '.php': 'PHP',
    '.swift': 'Swift', '.kt': 'Kotlin', '.scala': 'Scala',
    '.lua': 'Lua', '.sh': 'Shell', '.ps1': 'PowerShell',
    '.bat': 'Batch', '.vbs': 'VBScript',
    '.asm': 'Assembly', '.s': 'Assembly',
}

BUILD_SYSTEM_FILES = {
    'package.json': 'npm/Node.js', 'pom.xml': 'Maven/Java',
    'build.gradle': 'Gradle/Java', 'Cargo.toml': 'Cargo/Rust',
    'CMakeLists.txt': 'CMake/C++', 'Makefile': 'Make',
    'setup.py': 'setuptools/Python', 'pyproject.toml': 'Python/pyproject',
    'requirements.txt': 'pip/Python', 'go.mod': 'Go modules',
    'Gemfile': 'Bundler/Ruby', 'composer.json': 'Composer/PHP',
}

BUILD_SYSTEM_EXTS = {
    '.csproj': 'MSBuild/C#', '.sln': 'Visual Studio',
    '.vcxproj': 'Visual Studio/C++',
}

# Pattern -> (description, category)
HARDWARE_API_PATTERNS = {
    # Add domain-specific or hardware APIs here
    # Example:
    # 'DeviceIoControl':       ('Windows: DeviceIoControl', 'winapi'),
}

IGNORE_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv',
    'dist', 'build', 'target', '.idea', '.vs', '.vscode',
    'bin', 'obj', '.cache',
}


def detect_language(path: Path) -> dict:
    """
    Analyze a codebase and return a technology stack descriptor.

    Returns:
        {
          primary_language: str,
          languages: {lang: file_count},
          build_systems: [str],
          hardware_apis: [{pattern, description, category, files: [str]}],
          platform: str,
          file_count: int,
          total_lines: int,
          source_files: [str],   # relative paths of code files
        }
    """
    ext_counter = Counter()
    source_files = []
    build_systems = []
    hardware_hits: dict[str, dict] = {}
    total_lines = 0

    for f in _walk(path):
        rel = str(f.relative_to(path))

        # Build system detection
        if f.name in BUILD_SYSTEM_FILES:
            bs = BUILD_SYSTEM_FILES[f.name]
            if bs not in build_systems:
                build_systems.append(bs)
        if f.suffix in BUILD_SYSTEM_EXTS:
            bs = BUILD_SYSTEM_EXTS[f.suffix]
            if bs not in build_systems:
                build_systems.append(bs)

        # Language counting
        if f.suffix.lower() in EXTENSION_MAP:
            ext_counter[EXTENSION_MAP[f.suffix.lower()]] += 1
            source_files.append(rel)

        # Hardware API scanning
        try:
            content = f.read_text(encoding='utf-8', errors='ignore')
            total_lines += content.count('\n')
            for pattern, (description, category) in HARDWARE_API_PATTERNS.items():
                if pattern in content:
                    if pattern not in hardware_hits:
                        hardware_hits[pattern] = {
                            'pattern': pattern,
                            'description': description,
                            'category': category,
                            'files': [],
                        }
                    hardware_hits[pattern]['files'].append(rel)
        except Exception:
            pass

    languages = dict(ext_counter.most_common())
    primary = ext_counter.most_common(1)[0][0] if ext_counter else None

    # Infer platform
    categories = {h['category'] for h in hardware_hits.values()}
    if 'winapi' in categories:
        platform = 'Windows'
    elif 'posix' in categories:
        platform = 'Linux/Unix'
    else:
        platform = 'Unknown'

    return {
        'primary_language': primary,
        'languages': languages,
        'build_systems': build_systems,
        'hardware_apis': list(hardware_hits.values()),
        'platform': platform,
        'file_count': len(source_files),
        'total_lines': total_lines,
        'source_files': source_files,
    }


def _walk(path: Path):
    for f in path.rglob('*'):
        if f.is_file() and not any(p in IGNORE_DIRS for p in f.parts):
            yield f
