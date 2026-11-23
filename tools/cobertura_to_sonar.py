"""Convert an OpenCppCoverage Cobertura XML report to SonarQube's generic coverage format.

Usage: python cobertura_to_sonar.py <cobertura.xml> <sonar-coverage.xml> [repo_root]

If the input is missing or unreadable, an empty (but valid) report is written so the
SonarQube scan step does not fail on a missing coverage file.
"""
import os
import sys
import xml.etree.ElementTree as ET


def to_repo_relative(path, root):
    """Map a path from the coverage report to a repo-relative path SonarQube can match.

    OpenCppCoverage can write Windows paths without the drive letter (for example
    "a/repo/repo/PrettyPrint.cpp"), so a plain relpath() gives a path that does not
    exist. Drop leading folders until the remaining path exists under the repo root.
    """
    parts = [p for p in path.replace("\\", "/").split("/") if p and not p.endswith(":")]
    for i in range(len(parts)):
        candidate = "/".join(parts[i:])
        if os.path.isfile(os.path.join(root, candidate)):
            return candidate
    return None


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
            rel = to_repo_relative(name, root)
            if rel is None:
                for base in sources:  # fall back to the report's <source> roots
                    rel = to_repo_relative(os.path.join(base, name), root)
                    if rel:
                        break
            if rel is None:
                print(f"warning: {name} not found under {root}; skipped")
                continue
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
