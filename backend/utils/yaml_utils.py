"""
YAML processing utilities
"""
import os
import re


def resolve_yaml_imports(yaml_content: str, base_dir: str) -> str:
    """
    Recursively resolves `import: <file>` statements in a YAML string.
    This is a simple text-based substitution that respects indentation.

    Args:
        yaml_content: YAML content with potential import statements
        base_dir: Base directory for resolving relative import paths

    Returns:
        Resolved YAML content with all imports expanded
    """
    # Regex to find 'import: "path"' and capture the indentation
    import_pattern = re.compile(r'^(?P<indent>\s*)-?\s*import:\s*["\']?(?P<path>[\w\./\\-]+)["\']?\s*$', re.MULTILINE)

    def replacer(match):
        indent = match.group('indent')
        import_path = match.group('path')

        # For security, ensure the path is relative and within the project.
        if ".." in import_path:
            return f"{indent}# ERROR: Directory traversal is not allowed."

        abs_path = os.path.normpath(os.path.join(base_dir, import_path))

        if not abs_path.startswith(os.path.abspath(base_dir)):
            return f"{indent}# ERROR: Import path is outside the allowed directory."

        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                imported_content = f.read()

                # Indent the imported content to match the `import:` line's base indentation
                indented_content = '\n'.join([f"{indent}{line}" for line in imported_content.splitlines()])

                # Recursively resolve imports in the newly imported content
                return resolve_yaml_imports(indented_content, base_dir=os.path.dirname(abs_path))
        except FileNotFoundError:
            return f"{indent}# ERROR: Imported file not found at {import_path}"
        except Exception as e:
            return f"{indent}# ERROR: Failed to import file: {e}"

    # Keep replacing until no more imports are found
    resolved_content = yaml_content
    for _ in range(10):  # Max 10 levels of recursion
        new_content = import_pattern.sub(replacer, resolved_content)
        if new_content == resolved_content:
            break
        resolved_content = new_content
    else:
        # If the loop completes, there might be a circular import.
        # We return the content as is and let the YAML parser fail.
        pass

    return resolved_content
