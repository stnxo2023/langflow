import os
import sys
import re

import packaging.version

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def update_base_dep(pyproject_path: str, new_version: str) -> None:
    """Update the langflow-base dependency in pyproject.toml."""
    filepath = os.path.join(BASE_DIR, pyproject_path)
    with open(filepath, "r") as file:
        content = file.read()

    replacement = f'langflow-base-nightly = "{new_version}"'

    # Updates the pattern for poetry
    pattern = re.compile(r'langflow-base = \{ path = "\./src/backend/base", develop = true \}')
    if not pattern.search(content):
        raise Exception(f'langflow-base poetry dependency not found in "{filepath}"')
    content = pattern.sub(replacement, content)
    with open(filepath, "w") as file:
        file.write(content)


def verify_pep440(version):
    """
    Verify if version is PEP440 compliant.

    https://github.com/pypa/packaging/blob/16.7/packaging/version.py#L191
    """

    try:
        return packaging.version.Version(version)
    except packaging.version.InvalidVersion as e:
        raise e


def main() -> None:
    if len(sys.argv) != 2:
        raise Exception("New version not specified")
    base_version = sys.argv[1]

    # Strip "v" prefix from version if present
    if base_version.startswith("v"):
        base_version = base_version[1:]

    verify_pep440(base_version)
    update_base_dep("pyproject.toml", base_version)


if __name__ == "__main__":
    main()
