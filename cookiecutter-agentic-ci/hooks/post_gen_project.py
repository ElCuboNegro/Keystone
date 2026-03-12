"""
Post-generation hook: substitutes placeholder tokens in _copy_without_render files.
"""
import os


SUBSTITUTIONS = {
    "__LIBRARY_PATH__": "{{ cookiecutter.library_path }}",
    "__PACKAGE_NAME__": "{{ cookiecutter.package_name }}",
    "__ADR_PATH__": "{{ cookiecutter.adr_path }}",
    "__PYTHON_VERSION__": "{{ cookiecutter.python_version }}",
}

FILES_TO_PATCH = [
    os.path.join("tools", "check_adr_gate.py"),
    os.path.join(".github", "workflows", "ci.yml"),
]


def patch_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for placeholder, value in SUBSTITUTIONS.items():
        content = content.replace(placeholder, value)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  patched: {path}")


if __name__ == "__main__":
    print("\nPatching template placeholders...")
    for file_path in FILES_TO_PATCH:
        patch_file(file_path)
    print("\nProject generated successfully!")
    print("  cd {{ cookiecutter.project_slug }}")
    print("  Open docs/adr/index.md — write ADR-0001 before any code.")
    print("  Copy skills/*.md to ~/.claude/skills/ to install agent skills globally.")
