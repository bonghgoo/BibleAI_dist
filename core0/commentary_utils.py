import os
import re
import sqlite3
from typing import List

from core.bible_utils import decode_rtf


def clean_rtf_html(text):
    """RTF/HTML 태그를 제거하여 순수 텍스트만 반환"""
    if not text:
        return ""
    
    # RTF 태그 제거
    text = re.sub(r'\\u(-?\d+)\??', lambda m: chr(int(m.group(1))) if int(m.group(1)) >= 0 else m.group(0), text)
    text = re.sub(r'\{\\[^\}]*\}', '', text)  # RTF 제어 블록 제거
    text = re.sub(r'\\[a-z]{1,10}(-?\d+)?\s?', '', text)  # RTF 제어어 제거
    text = text.replace('{', '').replace('}', '')
    
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', text)
    
    # 여러 공백을 하나로
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def scan_commentary_files(selected_folders: List[str]) -> List[str]:
    """
    지정된 폴더(및 'commentaries/' 폴더가 있으면 자동 포함)를 모두 순회하며
    주석/성경 DB 파일(.sqlite3, .mybible, .twm, .cdb, .cmti, .cmtx 등)을 실시간으로 스캔합니다.
    """
    exts = (".cmt.mybible", ".cmt.twm", ".mybible", ".twm", ".sqlite3", ".sqlite", ".cdb", ".cmti", ".cmtx")
    base_folders = set(selected_folders or ["."])

    # commentaries 폴더가 존재하면 자동 포함
    if os.path.isdir("commentaries"):
        base_folders.add("commentaries")

    files: List[str] = []
    for folder in base_folders:
        folder_path = folder if folder != "." else "."
        if not (os.path.exists(folder_path) and os.path.isdir(folder_path)):
            continue

        for root, dirs, file_names in os.walk(folder_path):
            for name in file_names:
                lower = name.lower()
                if lower.endswith(exts):
                    full_path = os.path.abspath(os.path.join(root, name))
                    if full_path not in files:
                        files.append(full_path)

    return files


def load_commentaries_for_path(path: str, book_id: int, chap: int, vers: int) -> List[str]:
    """
    주어진 주석/성경 DB 파일 하나에서 해당 절(book_id, chap, vers)에 대한 주석을 모두 읽어옵니다.

    반환 형식은 기존 구현과 동일하게, 이미 파일명까지 포함된 문자열 리스트입니다.
    예시: "#### 📚 [파일명]\n본문..."
    """
    # 파일이 삭제되었거나 접근 불가한 경우 안전하게 건너뜁니다.
    if not os.path.exists(path):
        return []

    lower = path.lower()

    # e-Sword .cmti 형식 (older format)
    if lower.endswith(".cmti"):
        return _load_from_esword_cmti(path, book_id, chap, vers)

    # e-Sword .cmtx 형식 (newer format)
    if lower.endswith(".cmtx"):
        return _load_from_esword_cmtx(path, book_id, chap, vers)

    # commentaries.sqlite3 (전용 스키마 처리 + fallback 처리)
    if lower.endswith("commentaries.sqlite3"):
        return _load_from_commentaries_sqlite(path, book_id, chap, vers)

    # MyBible commentary 형식
    if lower.endswith(".mybible"):
        return _load_from_mybible(path, book_id, chap, vers)

    # TheWord(TWM) commentary 형식
    if lower.endswith(".twm"):
        return _load_from_twm(path, book_id, chap, vers)

    # cdb 형식 (Bible table)
    if lower.endswith(".cdb"):
        return _load_from_cdb(path, book_id, chap, vers)

    # 일반 sqlite3 / sqlite 파일 (스키마 추론)
    if lower.endswith(".sqlite3") or lower.endswith(".sqlite") or ".sqlite3" in lower:
        return _load_from_generic_sqlite(path, book_id, chap, vers)

    return []


def _load_from_esword_cmti(path: str, book_id: int, chap: int, vers: int) -> List[str]:
    """
    e-Sword .cmti 형식 주석 로더
    구조:
    - BookCommentary (Book INT, Comments TEXT)
    - ChapterCommentary (Book INT, Chapter INT, Comments TEXT)
    - VerseCommentary (Book INT, ChapterBegin INT, ChapterEnd INT, VerseBegin INT, VerseEnd INT, Comments TEXT)
    """
    results: List[str] = []
    filename = os.path.basename(path)
    name_without_ext = os.path.splitext(filename)[0]

    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()

        # 1. Verse Commentary 검색
        try:
            cur.execute(
                """
                SELECT Comments FROM VerseCommentary
                WHERE Book=? 
                AND ? BETWEEN ChapterBegin AND ChapterEnd
                AND ? BETWEEN VerseBegin AND VerseEnd
                """,
                (book_id, chap, vers),
            )
            rows = cur.fetchall()
            for row in rows:
                content = row[0]
                if content:
                    decoded = clean_rtf_html(content)
                    if decoded.strip():
                        results.append(f"#### 📚 [{name_without_ext}]\n{decoded.strip()}")
        except Exception:
            pass

        # 2. Chapter Commentary 검색 (vers가 0이거나 절 주석이 없을 때)
        if vers == 0 or not results:
            try:
                cur.execute(
                    """
                    SELECT Comments FROM ChapterCommentary
                    WHERE Book=? AND Chapter=?
                    """,
                    (book_id, chap),
                )
                rows = cur.fetchall()
                for row in rows:
                    content = row[0]
                    if content:
                        decoded = clean_rtf_html(content)
                        if decoded.strip():
                            results.append(f"#### 📚 [{name_without_ext} - 장 서론]\n{decoded.strip()}")
            except Exception:
                pass

        # 3. Book Commentary 검색 (chap가 0일 때)
        if chap == 0:
            try:
                cur.execute(
                    """
                    SELECT Comments FROM BookCommentary
                    WHERE Book=?
                    """,
                    (book_id,),
                )
                rows = cur.fetchall()
                for row in rows:
                    content = row[0]
                    if content:
                        decoded = clean_rtf_html(content)
                        if decoded.strip():
                            results.append(f"#### 📚 [{name_without_ext} - 책 서론]\n{decoded.strip()}")
            except Exception:
                pass

    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return results


def _load_from_esword_cmtx(path: str, book_id: int, chap: int, vers: int) -> List[str]:
    """
    e-Sword .cmtx 형식 주석 로더
    구조:
    - Books (Book INT, Comments TEXT)
    - Chapters (Book INT, Chapter INT, Comments TEXT)
    - Verses (Book INT, ChapterBegin INT, ChapterEnd INT, VerseBegin INT, VerseEnd INT, Comments TEXT)
    """
    results: List[str] = []
    filename = os.path.basename(path)
    name_without_ext = os.path.splitext(filename)[0]

    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()

        # 1. Verses Commentary 검색
        try:
            cur.execute(
                """
                SELECT Comments FROM Verses
                WHERE Book=? 
                AND ? BETWEEN ChapterBegin AND ChapterEnd
                AND ? BETWEEN VerseBegin AND VerseEnd
                """,
                (book_id, chap, vers),
            )
            rows = cur.fetchall()
            for row in rows:
                content = row[0]
                if content:
                    decoded = clean_rtf_html(content)
                    if decoded.strip():
                        results.append(f"#### 📚 [{name_without_ext}]\n{decoded.strip()}")
        except Exception:
            pass

        # 2. Chapters Commentary 검색 (vers가 0이거나 절 주석이 없을 때)
        if vers == 0 or not results:
            try:
                cur.execute(
                    """
                    SELECT Comments FROM Chapters
                    WHERE Book=? AND Chapter=?
                    """,
                    (book_id, chap),
                )
                rows = cur.fetchall()
                for row in rows:
                    content = row[0]
                    if content:
                        decoded = clean_rtf_html(content)
                        if decoded.strip():
                            results.append(f"#### 📚 [{name_without_ext} - 장 서론]\n{decoded.strip()}")
            except Exception:
                pass

        # 3. Books Commentary 검색 (chap가 0일 때)
        if chap == 0:
            try:
                cur.execute(
                    """
                    SELECT Comments FROM Books
                    WHERE Book=?
                    """,
                    (book_id,),
                )
                rows = cur.fetchall()
                for row in rows:
                    content = row[0]
                    if content:
                        decoded = clean_rtf_html(content)
                        if decoded.strip():
                            results.append(f"#### 📚 [{name_without_ext} - 책 서론]\n{decoded.strip()}")
            except Exception:
                pass

    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return results


def _load_from_commentaries_sqlite(path: str, book_id: int, chap: int, vers: int) -> List[str]:
    results: List[str] = []
    filename = os.path.basename(path)
    name_without_ext = os.path.splitext(filename)[0]

    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()

        # 1차: 고정 스키마 commentaries 테이블
        try:
            cur.execute(
                """
                SELECT text FROM commentaries
                WHERE book_number=? AND ? BETWEEN chapter_number_from AND chapter_number_to
                AND ? BETWEEN verse_number_from AND verse_number_to
                """,
                (book_id, chap, vers),
            )
            rows = cur.fetchall()
            for row in rows:
                content = row[0]
                if content:
                    decoded = decode_rtf(content)
                    if decoded.strip():
                        results.append(f"#### 📚 [{name_without_ext}]\n{decoded.strip()}")
        except Exception:
            pass

        # 2차: PRAGMA 기반으로 컬럼명을 유연하게 추론
        try:
            cur.execute("PRAGMA table_info(commentaries)")
            cols = [c[1].lower() for c in cur.fetchall()]
            c_from = "chapter_number_from" if "chapter_number_from" in cols else "chapter_number"
            c_to = "chapter_number_to" if "chapter_number_to" in cols else c_from
            v_from = "verse_number_from" if "verse_number_from" in cols else "verse_number"
            v_to = "verse_number_to" if "verse_number_to" in cols else v_from
            search_sql = f"""
                SELECT text FROM commentaries
                WHERE book_number = ?
                AND ? BETWEEN {c_from} AND {c_to}
                AND ? BETWEEN {v_from} AND {v_to}
            """
            cur.execute(search_sql, (int(book_id), int(chap), int(vers)))
            rows = cur.fetchall()
            for row in rows:
                if row[0]:
                    raw_data = row[0]
                    decoded = decode_rtf(raw_data)
                    if decoded.strip():
                        results.append(f"#### 📚 [{filename}]\n{decoded.strip()}")
        except Exception:
            pass
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return results


def _load_from_mybible(path: str, book_id: int, chap: int, vers: int) -> List[str]:
    results: List[str] = []
    filename = os.path.basename(path)
    name_without_ext = os.path.splitext(filename)[0]

    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT data FROM commentary
            WHERE book=? AND chapter=? AND ? BETWEEN fromverse AND toverse
            """,
            (book_id, chap, vers),
        )
        rows = cur.fetchall()
        for row in rows:
            content = row[0]
            if content:
                decoded = decode_rtf(content)
                if decoded.strip():
                    results.append(f"#### 📚 [{name_without_ext}]\n{decoded.strip()}")
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return results


def _load_from_twm(path: str, book_id: int, chap: int, vers: int) -> List[str]:
    results: List[str] = []
    filename = os.path.basename(path)
    name_without_ext = os.path.splitext(filename)[0]

    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT topic_id FROM bible_refs
            WHERE bi=? AND ci=? AND ? BETWEEN fvi AND tvi
            """,
            (book_id, chap, vers),
        )
        rows = cur.fetchall()
        for row in rows:
            topic_id = row[0]
            cur.execute("SELECT data FROM content WHERE topic_id=?", (topic_id,))
            content_rows = cur.fetchall()
            for content_row in content_rows:
                content = content_row[0]
                if content:
                    decoded = decode_rtf(content)
                    if decoded.strip():
                        results.append(f"#### 📚 [{name_without_ext}]\n{decoded.strip()}")
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return results


def _load_from_cdb(path: str, book_id: int, chap: int, vers: int) -> List[str]:
    results: List[str] = []
    filename = os.path.basename(path)
    name_without_ext = os.path.splitext(filename)[0]

    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT btext FROM Bible
            WHERE book=? AND chapter=? AND verse=?
            """,
            (book_id, chap, vers),
        )
        rows = cur.fetchall()
        for row in rows:
            content = row[0]
            if content:
                decoded = decode_rtf(content)
                if decoded.strip():
                    results.append(f"#### 📚 [{name_without_ext}]\n{decoded.strip()}")
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return results


def _load_from_generic_sqlite(path: str, book_id: int, chap: int, vers: int) -> List[str]:
    """
    commentaries.sqlite3 이외의 sqlite3 / sqlite 파일에 대해
    테이블/컬럼명을 추론하여 주석/본문 텍스트를 추출합니다.
    """
    results: List[str] = []
    filename = os.path.basename(path)

    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        all_tables = [row[0].lower() for row in cur.fetchall()]

        potential_tables = [
            "commentaries",
            "commentary",
            "texts",
            "words",
            "notes",
            "content",
            "bible",
            "verses",
            "scripture",
        ]
        target_table = None
        for table_candidate in potential_tables:
            if table_candidate in all_tables:
                target_table = table_candidate
                break

        if target_table:
            cur.execute(f"PRAGMA table_info({target_table});")
            all_columns = [col[1].lower() for col in cur.fetchall()]
            book_col = next(
                (col for col in all_columns if col in ["book_number", "book", "book_id", "bk", "b"]), None
            )
            chapter_col = next(
                (col for col in all_columns if col in ["chapter_number", "chapter", "ch", "c"]), None
            )
            verse_start_col = next(
                (
                    col
                    for col in all_columns
                    if col in ["verse_start", "verse", "vs", "v", "verse_number", "verse_num"]
                ),
                None,
            )
            verse_end_col = next(
                (
                    col
                    for col in all_columns
                    if col in ["verse_end", "to_verse", "toverse", "end_verse", "verse_to"]
                ),
                None,
            )
            text_col = next(
                (
                    col
                    for col in all_columns
                    if col in ["commentary", "text", "data", "content", "body", "notes", "comments", "content_text"]
                ),
                None,
            )

            if book_col and chapter_col and verse_start_col and text_col:
                try:
                    if verse_end_col:
                        cur.execute(
                            f"""
                            SELECT {text_col} FROM {target_table}
                            WHERE CAST({book_col} AS INTEGER)=?
                              AND CAST({chapter_col} AS INTEGER)=?
                              AND ? BETWEEN CAST({verse_start_col} AS INTEGER) AND CAST({verse_end_col} AS INTEGER)
                            """,
                            (book_id, chap, vers),
                        )
                    else:
                        cur.execute(
                            f"""
                            SELECT {text_col} FROM {target_table}
                            WHERE CAST({book_col} AS INTEGER)=?
                              AND CAST({chapter_col} AS INTEGER)=?
                              AND CAST({verse_start_col} AS INTEGER)=?
                            """,
                            (book_id, chap, vers),
                        )

                    rows = cur.fetchall()
                    for row in rows:
                        content = row[0]
                        if content:
                            decoded = decode_rtf(content)
                            if decoded.strip():
                                results.append(f"#### 📚 [주석: {filename}]\n{decoded.strip()}")
                except sqlite3.Error:
                    pass
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return results
