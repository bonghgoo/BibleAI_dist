import re
from typing import Dict, List, Optional, Tuple


def parse_reference(
    user_book: str,
    chap: str,
    verse_input: str,
    bible_alias_flat: Dict[str, str],
    bible_raw_map: Dict[str, List[str]],
) -> Optional[Tuple[str, str, List[str], str]]:
    """
    사용자가 입력한 (책, 장, 절 문자열)을 해석해
    (표준 책 코드, 장, 절 리스트, 모드)를 반환합니다.

    모드:
        - "book_intro"   : chap == "0"
        - "chapter_intro": verse_input == "0" and chap != "0"
        - "verse"        : 그 외 (일반 절 검색)
    """
    normalized_book = user_book.strip()
    book_match = re.match(r"^([가-힣a-zA-Z0-9]+)", normalized_book)
    if book_match:
        book_part = book_match.group(1)
        std = bible_alias_flat.get(book_part.lower())
    else:
        std = bible_alias_flat.get(normalized_book.lower())

    if not std:
        return None

    # 절 범위 파싱 (예: "26-27")
    if "-" in verse_input:
        try:
            start, end = map(int, verse_input.split("-"))
            verses = [str(v) for v in range(start, end + 1)]
        except Exception:
            verses = [verse_input]
    else:
        verses = [verse_input]

    if chap == "0":
        mode = "book_intro"
    elif verse_input == "0":
        mode = "chapter_intro"
    else:
        mode = "verse"

    return std, chap, verses, mode


def fetch_intro(
    text: str,
    std: str,
    chap: str,
    verse_input: str,
    bible_alias_flat: Dict[str, str],
    bible_raw_map: Dict[str, List[str]],
) -> Dict[str, str]:
    """
    책 서론 / 장 서론을 추출하는 로직을 담당합니다.
    기존 search_engine 내부의 서론 관련 정규식 로직을 그대로 이동했습니다.
    """
    results_dict: Dict[str, str] = {}

    # 책 서론 패턴
    book_intro_patterns = [
        r"(?:\[\[\s*@Bible:)([A-Za-z가-힣\d]+)\s+(\d+)(?:\s*\]\])(.*?)(?=\[\[\s*@Bible:|[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
        r"(?:\[\[@Bible:)([A-Za-z가-힣\d]+)\s+(\d+)(?:\]\])(.*?)(?=\[\[@Bible:|[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
        r"(?:\[\[\s*@Bible:)([A-Za-z가-힣\d]+)\s+(\d+)(?:\s*\]\])(.*?)(?=\[\[\s*@Bible:|[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z가-힣\d]+)\s*0:0(?!\s*\]\]\s*>>\s*\1\s*0:0\s*\]\])(?:\s*\]\]|\]\]|:\d+|\b)(.*?)(?=(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z가-힣\d]+)\s*0:00(?!\s*\]\]\s*>>\s*\1\s*0:00\s*\]\])(?:\s*\]\]|\]\]|:\d+|\b)(.*?)(?=(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z가-힣\d]+)\s*0\s+0(?!\s*\]\]\s*>>\s*\1\s*0\s+0\s*\]\])(?:\s*\]\]|\]\]|:\d+|\b)(.*?)(?=(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
    ]

    # verse_input != "0" 인 경우, 책/장 서론 패턴 먼저 스캔
    if verse_input != "0":
        for pattern in book_intro_patterns:
            matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
            for m in matches:
                groups = m.groups()
                if pattern in [book_intro_patterns[0], book_intro_patterns[1], book_intro_patterns[2]]:
                    book, chapter, content = groups
                    normalized_book = book.strip()
                    std_book = bible_alias_flat.get(normalized_book)
                    if std_book and std_book == std:
                        content = content.strip()
                        if content:
                            key = f"#### [{std_book} {chapter} (장 서론)]"
                            if key not in results_dict:
                                results_dict[key] = content
                else:
                    book, content = groups[:2]
                    normalized_book = book.strip()
                    std_book = bible_alias_flat.get(normalized_book)
                    if std_book and std_book == std:
                        content = content.strip()
                        if content:
                            key = f"#### [{std_book} 0:0 (서론)]"
                            if key not in results_dict:
                                results_dict[key] = content

    # 장 서론 패턴
    chapter_intro_pattern = (
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z가-힣\d]+)\s*(\d+):0(?!\s*\]\]\s*>>\s*\1\s*\2:0\s*\]\])"
        r"(?:\s*\]\]|\]\]|:\d+|\b)(.*?)(?=(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)"
        r"[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)"
    )
    matches = re.finditer(chapter_intro_pattern, text, re.DOTALL | re.IGNORECASE)
    for m in matches:
        book, chapter, content = m.groups()
        normalized_book = book.strip()
        std_book = bible_alias_flat.get(normalized_book)
        if std_book and std_book == std and chapter == chap:
            content = content.strip()
            if content:
                key = f"#### [{std_book} {chapter}:0 (장 서론)]"
                if key not in results_dict:
                    results_dict[key] = content

    # 책 서론 처리 (chap == "0")
    if chap == "0":
        intro_pattern = rf"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:){re.escape(std)}\s*1:1(?:\s*\]\]|\]\])"
        match = re.search(intro_pattern, text, re.IGNORECASE)
        if match:
            intro_content = text[: match.start()].strip()
            last_bible_ref = re.findall(
                r"(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\]).*?"
                r"(?=(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)[A-Za-z가-힣\d]+\s*\d+:\d+|$)",
                text[: match.start()],
                re.DOTALL | re.IGNORECASE,
            )
            if last_bible_ref:
                last_match = re.search(
                    r"(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)"
                    r"[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])",
                    last_bible_ref[-1],
                    re.IGNORECASE,
                )
                if last_match:
                    intro_content = last_bible_ref[-1][last_match.end() :].strip()
            else:
                intro_content = text[: match.start()].strip()

            if intro_content:
                key = f"#### [{std} 0:0 (서론)]"
                if key not in results_dict:
                    results_dict[key] = intro_content

    # 장 서론 처리 (chap != "0" 이고 verse_input == "0")
    elif verse_input == "0":
        all_names = [std] + bible_raw_map.get(std, [])
        intro_start_pattern = f"(?:"
        for i, name in enumerate(all_names):
            if i > 0:
                intro_start_pattern += "|"
            intro_start_pattern += (
                rf"\[\[\s*@Bible:{re.escape(name)}\s*{chap}\s*\]\]|"
                rf"\[\[@Bible:{re.escape(name)}\s*{chap}\s*\]\]|"
                rf"\[\[@Bible:{re.escape(name)}\s*{chap}\s*\]\]|"
                rf"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:){re.escape(name)}\s*{chap}:0(?:\s*\]\]|\]\])"
            )
        intro_start_pattern += ")"

        intro_end_pattern = f"(?:"
        for i, name in enumerate(all_names):
            if i > 0:
                intro_end_pattern += "|"
            intro_end_pattern += (
                rf"\[\[\s*@Bible:{re.escape(name)}\s*{chap}:1\s*\]\]|"
                rf"\[\[@Bible:{re.escape(name)}\s*{chap}:1\s*\]\]|"
                rf"\[\[@Bible:{re.escape(name)}\s*{chap}:1\s*\]\]|"
                rf"\[\[@Bible:{re.escape(name)}\s*{chap}:1\s*\]\]|"
                rf"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:){re.escape(name)}\s*{chap}:1(?:\s*\]\]|\]\])"
            )
        intro_end_pattern += ")"

        start_match = re.search(intro_start_pattern, text, re.IGNORECASE)
        end_match = re.search(intro_end_pattern, text, re.IGNORECASE)

        if start_match and end_match and start_match.start() < end_match.start():
            intro_content = text[start_match.end() : end_match.start()].strip()
            if intro_content:
                key = f"#### [{std} {chap}:0 (장 서론)]"
                if key not in results_dict:
                    results_dict[key] = intro_content
        else:
            fallback_pattern = f"(?:"
            for i, name in enumerate(all_names):
                if i > 0:
                    fallback_pattern += "|"
                fallback_pattern += (
                    rf"\[\[\s*@Bible:{re.escape(name)}\s*{chap}:1\s*\]\]|"
                    rf"\[\[@Bible:{re.escape(name)}\s*{chap}:1\s*\]\]|"
                    rf"\[\[@Bible:{re.escape(name)}\s*{chap}:1\s*\]\]|"
                    rf"\[\[@Bible:{re.escape(name)}\s*{chap}:1\s*\]\]|"
                    rf"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:){re.escape(name)}\s*{chap}:1(?:\s*\]\]|\]\])"
                )
            fallback_pattern += ")"

            match = re.search(fallback_pattern, text, re.IGNORECASE)
            if match:
                intro_content = text[: match.start()].strip()
                last_bible_ref = re.findall(
                    r"(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)"
                    r"[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\]).*?"
                    r"(?=(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)[A-Za-z가-힣\d]+\s*\d+:\d+|$)",
                    text[: match.start()],
                    re.DOTALL | re.IGNORECASE,
                )
                if last_bible_ref:
                    last_match = re.search(
                        r"(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)"
                        r"[A-Za-z가-힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])",
                        last_bible_ref[-1],
                        re.IGNORECASE,
                    )
                    if last_match:
                        intro_content = last_bible_ref[-1][last_match.end() :].strip()
                else:
                    intro_content = text[: match.start()].strip()

                if intro_content:
                    key = f"#### [{std} {chap}:0 (장 서론)]"
                    if key not in results_dict:
                        results_dict[key] = intro_content

    return results_dict


def fetch_bible_text(
    text: str,
    std: str,
    chap: str,
    verses: List[str],
    bible_alias_flat: Dict[str, str],
    bible_raw_map: Dict[str, List[str]],
) -> Dict[str, str]:
    """
    일반 절 검색 로직을 담당합니다.
    기존 search_engine의 '일반 절 검색' 부분을 그대로 이동했습니다.
    """
    results_dict: Dict[str, str] = {}

    all_verse_tags: List[Dict[str, object]] = []
    verse_pattern = (
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z가-힣\d]+)\s*(\d+):(\d+)\s*(?:\]\]|\]\])"
        r"(?:\s*\[\[\d+:\d+\s*>>\s*[A-Za-z가-힣\d]+\s*\d+:\d+\s*\]\])?"
    )
    single_verse_pattern = (
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z가-힣\d]+)\s*(\d+):(\d+)\s*(?:\]\]|\]\])"
    )

    for match in re.finditer(verse_pattern, text, re.IGNORECASE):
        book_found = match.group(1)
        chap_found = match.group(2)
        verse_found = match.group(3)
        normalized_book = book_found.strip()
        std_book_found = bible_alias_flat.get(normalized_book)
        if std_book_found:
            all_verse_tags.append(
                {
                    "book": std_book_found,
                    "chapter": chap_found,
                    "verse": verse_found,
                    "start": match.start(),
                    "end": match.end(),
                }
            )

    for match in re.finditer(single_verse_pattern, text, re.IGNORECASE):
        book_found = match.group(1)
        chap_found = match.group(2)
        verse_found = match.group(3)
        normalized_book = book_found.strip()
        std_book_found = bible_alias_flat.get(normalized_book)
        if std_book_found:
            is_duplicate = False
            for tag in all_verse_tags:
                if tag["start"] == match.start() and tag["end"] == match.end():
                    is_duplicate = True
                    break
            if not is_duplicate:
                all_verse_tags.append(
                    {
                        "book": std_book_found,
                        "chapter": chap_found,
                        "verse": verse_found,
                        "start": match.start(),
                        "end": match.end(),
                    }
                )

    all_verse_tags.sort(key=lambda x: x["start"])  # type: ignore[index]
    requested_verses_set = set(str(v) for v in verses)
    processed_ranges: List[Tuple[int, int]] = []

    for i, tag_info in enumerate(all_verse_tags):
        if (
            tag_info["book"] == std
            and tag_info["chapter"] == chap
            and str(tag_info["verse"]) in requested_verses_set
        ):
            is_duplicate = False
            for start_range, end_range in processed_ranges:
                if tag_info["start"] >= start_range and tag_info["end"] <= end_range:  # type: ignore[operator]
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            content_start = int(tag_info["end"])
            content_end = len(text)

            for j in range(i + 1, len(all_verse_tags)):
                next_tag = all_verse_tags[j]
                if (
                    next_tag["book"] == std
                    and next_tag["chapter"] == chap
                    and next_tag["verse"] not in requested_verses_set
                ):
                    content_end = int(next_tag["start"])
                    break
                if next_tag["book"] == std and next_tag["chapter"] != chap:
                    content_end = int(next_tag["start"])
                    break
                if next_tag["book"] != std:
                    content_end = int(next_tag["start"])
                    break

            processed_ranges.append((content_start, content_end))
            content = text[content_start:content_end].strip()

            if content:
                key = f"#### [{std} {chap}:{tag_info['verse']}]"
                if key not in results_dict:
                    results_dict[key] = content

    return results_dict

