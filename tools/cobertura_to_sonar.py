"""Convert an OpenCppCoverage Cobertura XML report to SonarQube's generic coverage format.

Usage: python cobertura_to_sonar.py <cobertura.xml> <sonar-coverage.xml> [repo_root]

If the input is missing or unreadable, an empty (but valid) report is written so the
SonarQube scan step does not fail on a missing coverage file.
"""
import os
import sys
import xml.etree.ElementTree as ET


def to_repo_relative(path, root):
    path = os.path.normpath(path)
    try:
        rel = os.path.relpath(path, root)
    except ValueError:  # different drive on Windows
        return path.replace("\\", "/")
    if rel.startswith(".."):
        return path.replace("\\", "/")
    return rel.replace("\\", "/")


def convert(src, dst, root):
    files = {}  # repo-relative path -> {line number -> covered?}
    try:
        tree = ET.parse(src)
    except (OSError, ET.ParseError) as err:
        print(f"warning: cannot read {src} ({err}); writing empty coverage report")
        tree = None

    if tree is not None:
        sources = [s.text.strip() for s in tree.getroot().iter("source") if s.text and s.text.strip()]
        for cls in tree.getroot().iter("class"):
            name = cls.get("filename")
            if not name:
                continue
            full = name
            if not os.path.isabs(full):
                base = sources[0] if sources else root
                full = os.path.join(base, name)
            rel = to_repo_relative(full, root)
            lines = files.setdefault(rel, {})
            for line in cls.iter("line"):
                number = int(line.get("number"))
                covered = int(line.get("hits", "0")) > 0
                lines[number] = lines.get(number, False) or covered

    out = ET.Element("coverage", version="1")
    for rel in sorted(files):
        file_el = ET.SubElement(out, "file", path=rel)
        for number in sorted(files[rel]):
            ET.SubElement(file_el, "lineToCover", lineNumber=str(number),
                          covered="true" if files[rel][number] else "false")
    ET.ElementTree(out).write(dst, encoding="utf-8", xml_declaration=True)

    total = sum(len(v) for v in files.values())
    hit = sum(1 for v in files.values() for c in v.values() if c)
    print(f"wrote {dst}: {len(files)} file(s), {hit}/{total} lines covered")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    convert(sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3] if len(sys.argv) > 3 else os.getcwd()))
