#!/usr/bin/env python3
"""통합 문서(project-docs-merged-v2.md)를 장별 파일 docs/00~08로 나눈다.

사용:
    python scripts/split_docs.py <통합 문서 경로>            # 쓰기
    python scripts/split_docs.py <통합 문서 경로> --check    # 쓰지 않고 차이만 보고

만드는 파일
    docs/NN-이름.md       생성물. 실행할 때마다 통합 문서와 같게 맞춘다. 직접 고치지 않는다.
    docs/gate-results.md  빈 파일. 이미 있으면 건드리지 않는다.
    README.md             2장의 README 본문. 이미 있으면 건드리지 않는다.

규칙
    - 장 경계는 `<a id="part-N"></a>` 줄이다. 0~8이 순서대로 한 번씩 있어야 한다.
    - 파일 이름은 각 장 첫 문단의 `docs/NN-이름.md`에서 읽는다. 추측하지 않는다.
    - 제목을 한 단계 올린다 (## → #). 코드 블록 안은 건드리지 않는다.
    - `(#part-N)` 링크는 해당 파일 링크로 바꾼다.
    - 첫 장 앞의 머리말(개정 요약, 검증 범위, 목차)은 옮기지 않는다.
    - 구조가 예상과 다르면 아무것도 쓰지 않고 실패한다.
    - docs/에 예상하지 못한 NN-*.md가 있으면 지우지 않고 실패한다 (이전 버전 문서 혼입 방지).
    - 같은 입력으로 다시 실행하면 파일이 바뀌지 않는다.

종료 코드: 0 정상, 1 --check에서 차이 발견, 2 입력 구조 오류.
"""

import argparse
import pathlib
import re
import sys

EXPECTED_PARTS = tuple(range(9))
GENERATED_GLOB = "[0-9][0-9]-*.md"
GATE_RESULTS = "gate-results.md"
README_PART = 2

ANCHOR = re.compile(r'^<a id="part-(\d+)"></a>\s*$')
CHAPTER_HEADING = re.compile(r"^## (\d+)\. \S")
DOC_PATH = re.compile(r"^`docs/((\d{2})-[a-z0-9-]+\.md)`")
PART_LINK = re.compile(r"\]\(#part-(\d+)\)")
HEADING = re.compile(r"^#(#{1,5} .*)$")  # ##~###### 제목. 첫 #을 떼면 한 단계 올라간다
FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")


class SplitError(Exception):
    """통합 문서의 구조가 예상과 다르다."""


def outside_fences(lines):
    """(줄 번호, 줄, 코드 블록 밖 여부)를 차례로 돌려준다. 여닫는 줄은 블록 안으로 본다."""
    fence = None
    for i, line in enumerate(lines):
        m = FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
                yield i, line, False
            else:
                yield i, line, True
            continue
        yield i, line, False
        closes = m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence)
        if closes and not m.group(2).strip():
            fence = None
    if fence is not None:
        raise SplitError("닫히지 않은 코드 블록이 있다")


def split_chapters(lines):
    """장 번호 → 그 장의 줄 목록 (앵커 줄 제외)."""
    starts = []
    for i, line, outside in outside_fences(lines):
        m = ANCHOR.match(line) if outside else None
        if m:
            starts.append((int(m.group(1)), i))
    found = tuple(n for n, _ in starts)
    if found != EXPECTED_PARTS:
        raise SplitError(f"part 앵커가 {EXPECTED_PARTS}가 아니다: {found}")
    ends = [i for _, i in starts[1:]] + [len(lines)]
    return {n: lines[i + 1 : end] for (n, i), end in zip(starts, ends, strict=True)}


def trim(lines):
    """앞뒤 빈 줄과 장 끝의 구분선(---)을 뗀다."""
    lines = list(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and (not lines[-1].strip() or lines[-1].strip() == "---"):
        lines.pop()
    return lines


def doc_name(part, lines):
    """장 제목과 첫 문단을 확인하고 파일 이름을 돌려준다."""
    m = CHAPTER_HEADING.match(lines[0]) if lines else None
    if not m or int(m.group(1)) != part:
        raise SplitError(f"part-{part}: 첫 줄이 '## {part}. 제목'이 아니다")
    body = [line for line in lines[1:] if line.strip()]
    m = DOC_PATH.match(body[0]) if body else None
    if not m or int(m.group(2)) != part:
        raise SplitError(f"part-{part}: 첫 문단이 `docs/{part:02d}-이름.md`로 시작하지 않는다")
    return m.group(1)


def render(lines, names, link_prefix=""):
    """제목을 한 단계 올리고 part 링크를 파일 링크로 바꾼다. 코드 블록 안은 그대로 둔다."""

    def link(m):
        part = int(m.group(1))
        if part not in names:
            raise SplitError(f"없는 장을 가리키는 링크: #part-{part}")
        return f"]({link_prefix}{names[part]})"

    out = []
    for _, line, outside in outside_fences(lines):
        if outside:
            line = HEADING.sub(r"\1", line)
            line = PART_LINK.sub(link, line)
            if "#part-" in line:
                raise SplitError(f"바꾸지 못한 part 링크: {line.strip()[:60]}")
        out.append(line)
    return "\n".join(out) + "\n"


def readme_lines(lines):
    """2장에서 README 본문을 꺼낸다. 첫 ### 제목이 README의 제목이다."""
    for i, line, outside in outside_fences(lines):
        if outside and line.startswith("### "):
            # 제목만 한 단계 먼저 올린다. render가 한 단계를 더 올려 # 제목이 된다.
            return [line[1:], *lines[i + 1 :]]
    raise SplitError(f"part-{README_PART}: README 제목(###)을 찾지 못했다")


def build(source_text):
    """(생성물 {이름: 내용}, README 내용)을 돌려준다. 파일을 쓰지 않는다."""
    lines = source_text.replace("\r\n", "\n").split("\n")
    chapters = {n: trim(body) for n, body in split_chapters(lines).items()}
    names = {n: doc_name(n, body) for n, body in chapters.items()}
    docs = {names[n]: render(body, names) for n, body in chapters.items()}
    readme = render(readme_lines(chapters[README_PART]), names, link_prefix="docs/")
    return docs, readme


def sync(path, content, check, keep_existing=False):
    """파일을 내용과 맞추고 상태를 돌려준다. check면 쓰지 않는다."""
    if path.exists():
        if keep_existing:
            return "kept"
        if path.read_bytes() == content.encode("utf-8"):
            return "unchanged"
        status = "updated"
    else:
        status = "created"
    if not check:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description="통합 문서를 docs/00~08로 나눈다.")
    parser.add_argument("source", type=pathlib.Path, help="project-docs-merged-v2.md 경로")
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parents[1],
        help="레포 루트 (기본: 이 스크립트의 상위 폴더)",
    )
    parser.add_argument("--check", action="store_true", help="쓰지 않고 차이만 보고한다")
    args = parser.parse_args(argv)

    docs_dir = args.root / "docs"
    try:
        docs, readme = build(args.source.read_text(encoding="utf-8"))
        stale = sorted(p.name for p in docs_dir.glob(GENERATED_GLOB) if p.name not in docs)
        if stale:
            raise SplitError(f"docs/에 예상하지 못한 파일이 있다 (직접 확인 후 정리): {stale}")
    except (SplitError, OSError, UnicodeDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    results = [
        (f"docs/{name}", sync(docs_dir / name, content, args.check))
        for name, content in sorted(docs.items())
    ]
    results.append(
        (f"docs/{GATE_RESULTS}", sync(docs_dir / GATE_RESULTS, "", args.check, keep_existing=True))
    )
    results.append(("README.md", sync(args.root / "README.md", readme, args.check, True)))

    # --check에서는 쓰지 않았으므로 "만들었다/고쳤다"가 아니라 "없다/다르다"로 보고한다.
    labels = {"created": "missing", "updated": "differs"} if args.check else {}
    for rel, status in results:
        print(f"{labels.get(status, status):<9} {rel}")
    pending = [rel for rel, status in results if status in ("created", "updated")]
    if args.check and pending:
        print(f"error: 통합 문서와 다르다: {pending}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
