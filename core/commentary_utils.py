import os
import sqlite3
from typing import List

from core.bible_utils import decode_rtf


def scan_commentary_files(selected_folders: List[str]) -> List[str]:
    """
    지정된 폴더(및 'commentaries/' 폴더가 있으면 자동 포함)를 모두 순회하며
    주석/성경 DB 파일(.sqlite3, .mybible, .twm, .cdb 등)을 실시간으로 스캔합니다.
    """
    exts = (".cmt.mybible", ".cmt.twm", ".mybible", ".twm", ".sqlite3", ".sqlite", ".cdb")
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
            # 이 단계는 실패해도 다음 PRAGMA 기반 추론으로 넘어갑니다.
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
            # 3차: 테이블명이 다른 경우(commentary 등) 재추론
            try:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                all_tables = [row[0].lower() for row in cur.fetchall()]
                table_name = "commentaries"
                if "commentary" in all_tables:
                    table_name = "commentary"
                cur.execute(f"PRAGMA table_info({table_name})")
                cols = [c[1].lower() for c in cur.fetchall()]
                c_from = "chapter_number_from" if "chapter_number_from" in cols else "chapter_number"
                c_to = "chapter_number_to" if "chapter_number_to" in cols else c_from
                v_from = "verse_number_from" if "verse_number_from" in cols else "verse_number"
                v_to = "verse_number_to" if "verse_number_to" in cols else v_from
                search_sql = f"""
                    SELECT text FROM {table_name}
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
            conn.close()  # type: ignore[name-defined]
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
            conn.close()  # type: ignore[name-defined]
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
            conn.close()  # type: ignore[name-defined]
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
            conn.close()  # type: ignore[name-defined]
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
        if not target_table:
            for table_name in all_tables:
                if any(
                    keyword in table_name.lower()
                    for keyword in ["comment", "note", "text", "content", "bible", "verse"]
                ):
                    target_table = table_name
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
                    # 숫자 캐스팅이 안 맞는 경우, 캐스팅 없이 재시도
                    try:
                        if verse_end_col:
                            cur.execute(
                                f"""
                                SELECT {text_col} FROM {target_table}
                                WHERE {book_col}=? AND {chapter_col}=? AND ? BETWEEN {verse_start_col} AND {verse_end_col}
                                """,
                                (book_id, chap, vers),
                            )
                        else:
                            cur.execute(
                                f"""
                                SELECT {text_col} FROM {target_table}
                                WHERE {book_col}=? AND {chapter_col}=? AND {verse_start_col}=?
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
        else:
            # 명시적인 target_table을 찾지 못한 경우, 몇 가지 가능성 탐색
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='commentary';"
            )
            if cur.fetchone():
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
                            results.append(f"#### 📚 [주석: {filename}]\n{decoded.strip()}")
            else:
                possible_tables = ["bible", "verses", "scripture", "content", "texts"]
                for table_name in possible_tables:
                    cur.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
                        (table_name,),
                    )
                    if cur.fetchone():
                        field_combinations = [
                            ("book", "chapter", "verse", "text"),
                            ("book_id", "chapter", "verse", "content"),
                            ("book_number", "chapter", "verse", "btext"),
                            ("bk", "ch", "vs", "content"),
                        ]

                        for book_f, chap_f, verse_f, text_f in field_combinations:
                            try:
                                cur.execute(
                                    f"""
                                    SELECT {text_f} FROM {table_name}
                                    WHERE {book_f}=? AND {chap_f}=? AND {verse_f}=?
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
                                break
                            except sqlite3.Error:
                                continue
                        break
    except Exception:
        pass
    finally:
        try:
            conn.close()  # type: ignore[name-defined]
        except Exception:
            pass

    return results

