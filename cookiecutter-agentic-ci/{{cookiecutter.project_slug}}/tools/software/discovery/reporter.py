"""
Reporter
Generates a comprehensive retro-engineering report from analysis artifacts.
Supports Markdown (default), JSON, and DOT outputs.
"""

from pathlib import Path
import json
from datetime import datetime


def generate_report(
    target: Path,
    tech_stack: dict,
    structure: dict,
    call_tree: dict,
    api_calls: dict,
    decisions: dict,
    fmt: str = 'markdown',
) -> str:
    if fmt == 'json':
        return _to_json(target, tech_stack, structure, call_tree, api_calls, decisions)
    if fmt == 'dot':
        return call_tree.get('dot', '// no graph generated')
    return _to_markdown(target, tech_stack, structure, call_tree, api_calls, decisions)


# ─── Markdown ─────────────────────────────────────────────────────────────────

def _to_markdown(target, ts, st, ct, ac, dec) -> str:
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f'# Retro-Engineering Report',
        f'',
        f'**Target:** `{target}`  ',
        f'**Generated:** {now}  ',
        f'**Primary Language:** {ts.get("primary_language", "unknown")}  ',
        f'**Platform:** {ts.get("platform", "unknown")}  ',
        f'',
        '---',
        '',
    ]

    # 1. Technology Stack
    lines += ['## 1. Technology Stack', '']
    lines += [f'- **Languages:** {", ".join(f"{k} ({v} files)" for k, v in ts.get("languages", {}).items())}']
    lines += [f'- **Build Systems:** {", ".join(ts.get("build_systems", [])) or "none detected"}']
    lines += [f'- **Total Source Files:** {ts.get("file_count", 0)}']
    lines += [f'- **Total Lines:** {ts.get("total_lines", 0):,}']
    lines += ['']

    # Hardware APIs
    hw = ts.get('hardware_apis', [])
    if hw:
        lines += ['### Hardware / External APIs Detected', '']
        lines += ['| Pattern | Description | Category | Files |']
        lines += ['|---------|-------------|----------|-------|']
        for h in hw:
            files = ', '.join(f'`{f}`' for f in h['files'][:3])
            if len(h['files']) > 3:
                files += f' +{len(h["files"]) - 3} more'
            lines += [f'| `{h["pattern"]}` | {h["description"]} | {h["category"]} | {files} |']
        lines += ['']

    # 2. Structure
    lines += ['## 2. Architecture & Structure', '']

    entry_points = st.get('entry_points', [])
    if entry_points:
        lines += ['### Entry Points', '']
        for ep in entry_points:
            lines += [f'- `{ep}`']
        lines += ['']

    modules = st.get('modules', [])
    if modules:
        lines += [f'### Modules ({len(modules)} source files)', '']
        lines += ['| File | Language | Classes | Functions | Lines |']
        lines += ['|------|----------|---------|-----------|-------|']
        for m in sorted(modules, key=lambda x: -x.get('line_count', 0))[:30]:
            cls = len(m.get('classes', []))
            fns = len(m.get('functions', []))
            lines += [f'| `{m["path"]}` | {m["language"]} | {cls} | {fns} | {m.get("line_count", 0)} |']
        lines += ['']

    # Public API
    pub = st.get('public_api', [])
    if pub:
        lines += [f'### Public API Surface ({len(pub)} symbols)', '']
        for item in pub[:40]:
            lines += [f'- **{item["kind"]}** `{item["name"]}` — `{item["location"]}`']
        if len(pub) > 40:
            lines += [f'- ... and {len(pub) - 40} more']
        lines += ['']

    # 3. Call Tree
    lines += ['## 3. Call Tree', '']
    entry_flows = ct.get('entry_flows', [])
    if entry_flows:
        lines += ['### Entry Point Flows', '']
        for ef in entry_flows:
            lines += [f'#### `{ef["entry"]}` (`{ef["file"]}`)', '']
            lines += ['```']
            lines += [_render_flow(ef['entry'], ef['flow'], 0)]
            lines += ['```', '']
    else:
        lines += ['*No entry point flows detected.*', '']

    ext_calls = ct.get('external_calls', [])
    if ext_calls:
        lines += [f'### External/Hardware API Call Sites ({len(ext_calls)} calls)', '']
        lines += ['| Caller | Callee | File | Line |']
        lines += ['|--------|--------|------|------|']
        for e in ext_calls[:50]:
            lines += [f'| `{e["caller"]}` | `{e["callee"]}` | `{e["location"]}` | {e["line"]} |']
        lines += ['']

    edges = ct.get('edges', [])
    lines += [f'> Total call edges found: **{len(edges)}**', '']

    # 4. API Usage
    lines += ['## 4. External API Usage', '']
    summary = ac.get('summary', {})
    if summary:
        lines += ['| API Group | Call Count |']
        lines += ['|-----------|-----------|']
        for group, count in sorted(summary.items(), key=lambda x: -x[1]):
            lines += [f'| {group} | {count} |']
        lines += ['']

    by_group = ac.get('by_group', {})
    for group, calls in by_group.items():
        if group == 'unknown' or not calls:
            continue
        lines += [f'### {group} ({len(calls)} calls)', '']
        lines += ['| Function | File | Line | Args |']
        lines += ['|----------|------|------|------|']
        for c in calls[:20]:
            args = ', '.join(c.get('args_raw', []))[:60]
            lines += [f'| `{c["function"]}` | `{c["file"]}` | {c["line"]} | `{args}` |']
        lines += ['']

    # 5. Software Decisions
    lines += ['## 5. Software Decisions', '']
    lines += [f'> {dec.get("summary", "")}', '']

    critical = dec.get('critical', [])
    if critical:
        lines += [f'### Critical Decisions ({len(critical)})', '']
        for d in critical[:30]:
            lines += [f'- **[{d["kind"].upper()}]** `{d["file"]}:{d["line"]}` — {d["description"]}']
            if d.get('snippet'):
                lines += [f'  ```', f'  {d["snippet"]}', f'  ```']
        lines += ['']

    by_kind = dec.get('by_kind', {})
    for kind, items in by_kind.items():
        if not items:
            continue
        lines += [f'### {kind.capitalize()} Decisions ({len(items)})', '']
        for d in items[:15]:
            lines += [f'- `{d["file"]}:{d["line"]}` — {d["description"]}']
        if len(items) > 15:
            lines += [f'- *... and {len(items) - 15} more*']
        lines += ['']

    # 6. Cross-platform notes
    lines += ['## 6. Cross-Platform Porting Notes', '']
    platform = ts.get('platform', 'Unknown')
    lines += _porting_notes(platform, by_group)

    lines += ['', '---', f'*Generated by retro-engineer v1.0*']
    return '\n'.join(lines)


def _render_flow(name: str, children: dict, depth: int) -> str:
    indent = '  ' * depth
    result = f'{indent}└─ {name}'
    if children:
        sub = []
        for child, grandchildren in list(children.items())[:8]:
            sub.append(_render_flow(child, grandchildren or {}, depth + 1))
        result += '\n' + '\n'.join(sub)
    return result


def _porting_notes(platform: str, by_group: dict) -> list[str]:
    notes = []
    if platform == 'Windows':
        notes += [
            '**Current platform: Windows-only**',
            '',
            '| Windows API | Linux Equivalent | Notes |',
            '|-------------|-----------------|-------|',
        ]
        if 'winapi' in by_group:
            notes += ['| `CreateFile` | `open()` / `libusb_open()` | Device paths differ |']
            notes += ['| `DeviceIoControl` | `ioctl()` | Different call signature |']
            notes += ['| `RegisterDeviceNotification` | `udev` / `libudev` | Completely different model |']
    return notes


# ─── JSON ─────────────────────────────────────────────────────────────────────

def _to_json(target, ts, st, ct, ac, dec) -> str:
    payload = {
        'target': str(target),
        'generated': datetime.now().isoformat(),
        'tech_stack': ts,
        'structure': {
            'entry_points': st.get('entry_points'),
            'module_count': len(st.get('modules', [])),
            'public_api': st.get('public_api'),
        },
        'call_tree': {
            'edge_count': len(ct.get('edges', [])),
            'entry_flows': ct.get('entry_flows'),
            'external_calls': ct.get('external_calls'),
        },
        'api_calls': {
            'summary': ac.get('summary'),
            'by_group': ac.get('by_group'),
        },
        'decisions': {
            'summary': dec.get('summary'),
            'critical': dec.get('critical'),
            'by_kind': dec.get('by_kind'),
        },
    }
    return json.dumps(payload, indent=2, default=str)
