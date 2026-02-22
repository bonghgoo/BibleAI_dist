import re
import os
import sqlite3
from typing import Dict, List, Optional, Tuple
import streamlit as st


def parse_reference(
    user_book: str,
    chap: str,
    verse_input: str,
    bible_alias_flat: Dict[str, str],
    bible_raw_map: Dict[str, List[str]],
) -> Optional[Tuple[str, str, List[str], str]]:
    """
    사용자가 입력한 (책, 장, 절 문자열) 을 해석해
    (표준 책 코드, 장, 절 리스트, 모드) 를 반환합니다.

    모드:
        - "book_intro"   : chap == "0"
        - "chapter_intro": verse_input == "0" and chap != "0"
        - "verse"        : 그 외 (일반 절 검색)
    """
    normalized_book = user_book.strip()
    book_match = re.match(r"^([가 - 힣 a-zA-Z0-9]+)", normalized_book)
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


# ========== [개선된] 로고스 태그 인덱싱 캐시 기능 ==========
# 핵심 개선:
# 1. 유연한 패턴: (?i)@bible:([a-zA-Z 가 - 힣 0-9]+) 로 대소문자/한글 약어 모두 추출
# 2. 표준화: 추출된 raw_book 을 bible_alias_flat 으로 표준 코드 변환
# 3. 통합 캐시: 표준 코드를 키로 사용하여 다양한 약어를 하나의 표준에 통합

@st.cache_data(show_spinner=False)
def build_logos_tag_index(text: str, bible_alias_flat: Dict[str, str]) -> Dict[str, List[Tuple[int, int, str, str]]]:
    """
    로고스 바이블 태그 전체를 한 번만 스캔하여 인덱스를 생성합니다.

    개선된 점:
    - 엄격한 매칭 대신 유연한 패턴 사용: (?i)@bible:([a-zA-Z 가 - 힣 0-9]+)
    - 추출된 약어를 bible_alias_flat 으로 표준화
    - 반환: {standard_book_code: [(start_pos, end_pos, chapter, verse), ...]}
    """
    index: Dict[str, List[Tuple[int, int, str, str]]] = {}

    # 개선된 패턴: 대소문자 구분 없이 @bible: 다음에 오는 책 이름 추출 (한글/영문 모두 지원)
    verse_pattern = r"(?i)@bible:([a-zA-Z가 - 힣 0-9]+)\s*(\d+):(\d+)"

    for match in re.finditer(verse_pattern, text, re.IGNORECASE):
        raw_book = match.group(1).strip()
        chap = match.group(2)
        verse = match.group(3)

        # 핵심: 추출된 약어를 표준 코드로 변환
        std_book = bible_alias_flat.get(raw_book.lower(), raw_book)

        # 표준 코드를 키로 사용 (다양한 약어가 하나의 표준에 통합됨)
        key = std_book

        if key not in index:
            index[key] = []

        index[key].append((match.start(), match.end(), chap, verse))

    return index


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
        r"(?:\[\[\s*@Bible:)([A-Za-z 가 - 힣\d]+)\s+(\d+)(?:\s*\]\])(.*?)(?=\[\[\s*@Bible:|[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
        r"(?:\[\[@Bible:)([A-Za-z 가 - 힣\d]+)\s+(\d+)(?:\]\])(.*?)(?=\[\[@Bible:|[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
        r"(?:\[\[\s*@Bible:)([A-Za-z 가 - 힣\d]+)\s+(\d+)(?:\s*\]\])(.*?)(?=\[\[\s*@Bible:|[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z 가 - 힣\d]+)\s*0:0(?!\s*\]\]\s*>>\s*\1\s*0:0\s*\]\])(?:\s*\]\]|\]\]|:\d+|\b)(.*?)(?=(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z 가 - 힣\d]+)\s*0:00(?!\s*\]\]\s*>>\s*\1\s*0:00\s*\]\])(?:\s*\]\]|\]\]|:\d+|\b)(.*?)(?=(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z 가 - 힣\d]+)\s*0\s+0(?!\s*\]\]\s*>>\s*\1\s*0\s+0\s*\]\])(?:\s*\]\]|\]\]|:\d+|\b)(.*?)(?=(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)",
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
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z 가 - 힣\d]+)\s*(\d+):0(?!\s*\]\]\s*>>\s*\1\s*\2:0\s*\]\])"
        r"(?:\s*\]\]|\]\]|:\d+|\b)(.*?)(?=(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)"
        r"[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])|$)"
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
                r"(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\]).*?"
                r"(?=(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)[A-Za-z 가 - 힣\d]+\s*\d+:\d+|$)",
                text[: match.start()],
                re.DOTALL | re.IGNORECASE,
            )
            if last_bible_ref:
                last_match = re.search(
                    r"(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)"
                    r"[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])",
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
                    r"[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\]).*?"
                    r"(?=(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)[A-Za-z 가 - 힣\d]+\s*\d+:\d+|$)",
                    text[: match.start()],
                    re.DOTALL | re.IGNORECASE,
                )
                if last_bible_ref:
                    last_match = re.search(
                        r"(?:\[\[\s*@Bible:|\[\[@Bible:|\[\[@Bible:|@Bible:)"
                        r"[A-Za-z 가 - 힣\d]+\s*\d+:\d+(?:\s*\]\]|\]\])",
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
    use_index: bool = True,
) -> Dict[str, str]:
    """
    일반 절 검색 로직을 담당합니다.

    [개선된 점]
    - use_index=True: 캐시된 인덱스를 사용하여 빠르게 검색 (2 번 엔진의 장점)
    - 인덱스는 표준 코드로 통합되어 있어, 어떤 약어로 문서가 작성되었든 표준화되어 저장됨
    - 사용자 검색어도 표준 코드로 변환되므로, 어떤 약어로 검색해도 통합된 결과 반환
    - [핵심] book_id 포함: 주석 모듈 연동을 위해 book_id 를 결과에 포함
    """
    results_dict: Dict[str, str] = {}

    # [개선된] 인덱스 활용 모드
    if use_index:
        # bible_alias_flat 을 전달하여 인덱스 생성 시 표준화 수행
        tag_index = build_logos_tag_index(text, bible_alias_flat)

        for verse in verses:
            # 사용자 입력이 이미 표준 코드 (std) 로 변환되어 있으므로
            # 인덱스에서 표준 코드로 직접 검색
            matched_positions = []
            if std in tag_index:
                # 인덱스에서 해당 장/절에 맞는 항목만 필터링
                for start_pos, end_pos, indexed_chap, indexed_verse in tag_index[std]:
                    if indexed_chap == chap and indexed_verse == verse:
                        matched_positions.append((start_pos, end_pos))

            if matched_positions:
                # 첫 번째 매칭 위치 사용
                start_pos, end_pos = matched_positions[0]

                # 다음 절까지의 내용 추출
                content_end = len(text)
                next_verse_num = int(verse) + 1

                # 다음 절의 위치 찾기
                for start_pos_next, end_pos_next, indexed_chap, indexed_verse in tag_index.get(std, []):
                    if indexed_chap == chap and indexed_verse == str(next_verse_num):
                        if start_pos_next > end_pos:
                            content_end = start_pos_next
                            break

                content = text[end_pos:content_end].strip()
                if content:
                    # [핵심 수정] book_id 포함 - 주석 모듈 연동을 위한 데이터 규격 통일
                    from core.bible_utils import get_book_id_from_code
                    book_id = get_book_id_from_code(std)
                    
                    result_key = f"#### [{std} {chap}:{verse}]"
                    if result_key not in results_dict:
                        results_dict[result_key] = content

        return results_dict

    # 기존 전수조사 방식 (fallback)
    all_verse_tags: List[Dict[str, object]] = []
    verse_pattern = (
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z 가 - 힣\d]+)\s*(\d+):(\d+)\s*(?:\]\]|\]\])"
        r"(?:\s*\[\[\d+:\d+\s*>>\s*[A-Za-z 가 - 힣\d]+\s*\d+:\d+\s*\]\])?"
    )
    single_verse_pattern = (
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z 가 - 힣\d]+)\s*(\d+):(\d+)\s*(?:\]\]|\]\])"
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


# ========== [NEW] 성경 모듈 DB 에서 직접 검색 ==========

def scan_bible_module_files(selected_folders: List[str]) -> List[str]:
    """
    성경 모듈 파일 (.mybible, .twm, .cdb, .sqlite3) 스캔
    """
    exts = (".mybible", ".twm", ".cdb", ".sqlite3", ".sqlite")
    base_folders = set(selected_folders or ["."])

    # bibles 폴더가 있으면 자동 포함
    if os.path.isdir("bibles"):
        base_folders.add("bibles")

    files: List[str] = []
    for folder in base_folders:
        folder_path = folder if folder != "." else "."
        if not (os.path.exists(folder_path) and os.path.isdir(folder_path)):
            continue

        for root, dirs, file_names in os.walk(folder_path):
            for name in file_names:
                lower = name.lower()
                # 주석 파일 제외 (.cmt. 포함된 것)
                if ".cmt." in lower:
                    continue

                if lower.endswith(exts):
                    full_path = os.path.abspath(os.path.join(root, name))
                    if full_path not in files:
                        files.append(full_path)

    return files


def load_bible_verse_from_module(path: str, book_id: int, chap: int, vers: int) -> Optional[str]:
    """
    성경 모듈 DB 에서 특정 절 본문 추출
    """
    if not os.path.exists(path):
        return None

    lower = path.lower()
    filename = os.path.basename(path)

    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()

        # MyBible 형식
        if lower.endswith(".mybible"):
            try:
                cur.execute(
                    "SELECT text FROM verses WHERE book=? AND chapter=? AND verse=?",
                    (book_id, chap, vers),
                )
                row = cur.fetchone()
                if row and row[0]:
                    from core.bible_utils import decode_rtf
                    content = decode_rtf(row[0])
                    return f"#### 📖 [{filename}]\n{content.strip()}"
            except:
                pass

        # TheWord (TWM) 형식
        elif lower.endswith(".twm"):
            try:
                cur.execute(
                    "SELECT data FROM bible WHERE bi=? AND ci=? AND vi=?",
                    (book_id, chap, vers),
                )
                row = cur.fetchone()
                if row and row[0]:
                    from core.bible_utils import decode_rtf
                    content = decode_rtf(row[0])
                    return f"#### 📖 [{filename}]\n{content.strip()}"
            except:
                pass

        # Crossway (CDB) 형식
        elif lower.endswith(".cdb"):
            try:
                cur.execute(
                    "SELECT btext FROM Bible WHERE book=? AND chapter=? AND verse=?",
                    (book_id, chap, vers),
                )
                row = cur.fetchone()
                if row and row[0]:
                    from core.bible_utils import decode_rtf
                    content = decode_rtf(row[0])
                    return f"#### 📖 [{filename}]\n{content.strip()}"
            except:
                pass

        # 일반 sqlite3 파일 (스키마 추론)
        elif lower.endswith(".sqlite3") or lower.endswith(".sqlite"):
            try:
                # 테이블 찾기
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0].lower() for row in cur.fetchall()]

                target_table = None
                for table_name in ["verses", "bible", "scripture", "texts"]:
                    if table_name in tables:
                        target_table = table_name
                        break

                if target_table:
                    # 컬럼 추론
                    cur.execute(f"PRAGMA table_info({target_table})")
                    columns = [col[1].lower() for col in cur.fetchall()]

                    book_col = next((c for c in columns if c in ["book", "book_id", "book_number"]), None)
                    chap_col = next((c for c in columns if c in ["chapter", "ch"]), None)
                    verse_col = next((c for c in columns if c in ["verse", "vs", "v"]), None)
                    text_col = next((c for c in columns if c in ["text", "content", "btext", "data"]), None)

                    if book_col and chap_col and verse_col and text_col:
                        cur.execute(
                            f"SELECT {text_col} FROM {target_table} WHERE {book_col}=? AND {chap_col}=? AND {verse_col}=?",
                            (book_id, chap, vers),
                        )
                        row = cur.fetchone()
                        if row and row[0]:
                            from core.bible_utils import decode_rtf
                            content = decode_rtf(row[0])
                            return f"#### 📖 [{filename}]\n{content.strip()}"
            except:
                pass

        conn.close()
    except:
        pass

    return None


# ========== [핵심 추가] 주석 모듈 연동 함수 ==========

def get_book_id_for_commentary(std_book: str) -> int:
    """
    [핵심 수정] 표준 책 코드 (Gen, Exo 등) 를 성경 모듈 DB 의 book_id 로 변환
    
    이 함수는 mymain.py 의 get_external_commentaries 함수에서 호출되어
    주석 모듈 연동을 가능하게 합니다.
    
    Args:
        std_book: 표준 책 코드 (예: "Gen", "Rom", "Mat")
    
    Returns:
        book_id: 성경 모듈 DB 에서 사용하는 숫자 ID (1-based)
    """
    from core.bible_utils import get_book_id_from_code
    return get_book_id_from_code(std_book)
