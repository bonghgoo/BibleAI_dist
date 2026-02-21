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


# ========== [NEW] 로고스 태그 인덱싱 캐시 기능 ==========

@st.cache_data(show_spinner=False)
def build_logos_tag_index(text: str) -> Dict[str, List[Tuple[int, int]]]:
    """
    로고스 바이블 태그 전체를 한 번만 스캔하여 인덱스를 생성합니다.
    반환: {book_code: [(start_pos, end_pos), ...]}
    """
    index = {}
    verse_pattern = (
        r"(?:\[\[\s*@Bible:|\[\[@Bible:|@Bible:)([A-Za-z가-힣\d]+)\s*(\d+):(\d+)\s*(?:\]\]|\]\])"
        r"(?:\s*\[\[\d+:\d+\s*>>\s*[A-Za-z가-힣\d]+\s*\d+:\d+\s*\]\])?"
    )
    
    for match in re.finditer(verse_pattern, text, re.IGNORECASE):
        book = match.group(1).strip()
        chap = match.group(2)
        verse = match.group(3)
        key = f"{book}_{chap}_{verse}"
        
        if key not in index:
            index[key] = []
        
        index[key].append((match.start(), match.end()))
    
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
    use_index: bool = True,
) -> Dict[str, str]:
    """
    일반 절 검색 로직을 담당합니다.
    [NEW] use_index=True일 경우 캐시된 인덱스를 사용하여 빠르게 검색합니다.
    """
    results_dict: Dict[str, str] = {}

    # [NEW] 인덱스 활용 모드
    if use_index:
        tag_index = build_logos_tag_index(text)
        
        for verse in verses:
            # 인덱스에서 해당 구절 찾기
            key_candidates = []
            for alias in [std] + bible_raw_map.get(std, []):
                key_candidates.append(f"{alias}_{chap}_{verse}")
            
            matched_positions = []
            for key_candidate in key_candidates:
                if key_candidate in tag_index:
                    matched_positions.extend(tag_index[key_candidate])
            
            if matched_positions:
                # 첫 번째 매칭 위치 사용
                start_pos, end_pos = matched_positions[0]
                
                # 다음 절까지의 내용 추출
                content_end = len(text)
                next_verse_num = int(verse) + 1
                next_key_candidates = []
                for alias in [std] + bible_raw_map.get(std, []):
                    next_key_candidates.append(f"{alias}_{chap}_{next_verse_num}")
                
                for next_key in next_key_candidates:
                    if next_key in tag_index and tag_index[next_key]:
                        next_start, _ = tag_index[next_key][0]
                        if next_start > end_pos:
                            content_end = next_start
                            break
                
                content = text[end_pos:content_end].strip()
                if content:
                    result_key = f"#### [{std} {chap}:{verse}]"
                    if result_key not in results_dict:
                        results_dict[result_key] = content
        
        return results_dict

    # 기존 전수조사 방식 (fallback)
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


# ========== [NEW] 성경 모듈 DB에서 직접 검색 ==========

def scan_bible_module_files(selected_folders: List[str]) -> List[str]:
    """
    성경 모듈 파일(.mybible, .twm, .cdb, .sqlite3) 스캔
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
    성경 모듈 DB에서 특정 절 본문 추출
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
