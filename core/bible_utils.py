import re
import streamlit as st


@st.cache_data(show_spinner=False)
def decode_rtf(raw):
    """Decode RTF text into plain text."""
    if not raw:
        return ""
    try:
        raw = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)

        def repl(m):
            try:
                return chr(int(m.group(1)))
            except Exception:
                return m.group(0)

        text = re.sub(r"\\u(-?\d+)\??", repl, raw)
        text = re.sub(r"\{\\.*?\}|\\([a-z]{1,10})(-?\d+)? ?|<.*?>", "", text)
        return re.sub(r"\s+", " ", text.replace("}", "").replace("{", "")).strip()
    except Exception:
        return str(raw)


def get_ultimate_bible_map():
    """
    Return flattened and raw mappings for Bible book aliases.

    This logic was originally defined in agape144000_enhanced_v4_updated.py
    and extracted here for reuse across multiple entrypoint scripts.
    """
    m = {
        "Gen": ["창세기", "창세", "창", "gen", "genesis"],
        "Exo": ["출애굽기", "출애굽", "출", "exo", "exod", "exodus"],
        "Lev": ["레위기", "레위", "레", "lev", "leviticus"],
        "Num": ["민수기", "민수", "민", "num", "numbers"],
        "Deu": ["신명기", "신명", "신", "deu", "deut", "deuteronomy"],
        "Jos": ["여호수아", "여호", "수", "jos", "josh", "joshua"],
        "Jud": ["사사기", "사사", "삿", "judg", "judges"],
        "Rut": ["룻기", "룻", "rut", "rth", "ruth"],
        "1Sa": ["사무엘상", "삼상", "1sa", "1samuel"],
        "2Sa": ["사무엘하", "삼하", "2sa", "2samuel"],
        "1Ki": ["열왕기상", "왕상", "1ki", "1kings"],
        "2Ki": ["열왕기하", "왕하", "2ki", "2kings"],
        "1Ch": ["역대기상", "대상", "1ch", "1chronicles"],
        "2Ch": ["역대기하", "대하", "2ch", "2chronicles"],
        "Ezr": ["에스라",  "스", "ezr", "ezra"],
        "Neh": ["느헤미야", "느헤", "느", "neh", "nehemiah"],
        "Est": ["에스더", "에", "에스", "est", "esth", "esther"],
        "Job": ["욥기", "욥", "job", "jb"],
        "Psa": ["시편", "시", "psa", "psalms"],
        "Pro": ["잠언", "잠", "pro", "prov", "proverbs"],
        "Ecc": ["전도서", "전도", "전", "ecc", "ecclesiastes"],
        "Sng": ["아가", "아", "sng", "song", "songofsongs"],
        "Isa": ["이사야", "이사", "사", "isa", "isaiah"],
        "Jer": ["예레미야", "예레", "렘", "jer", "jeremiah"],
        "Lam": ["예레미야애가", "애가", "애", "lam", "lamentations"],
        "Eze": ["에스겔", "겔", "eze", "ezek", "ezekiel"],
        "Dan": ["다니엘", "단", "dan", "daniel"],
        "Hos": ["호세아", "호세", "호", "hos", "hosea"],
        "Joe": ["요엘", "욜", "joe", "joel"],
        "Amo": ["아모스", "암", "amo", "am", "amos"],
        "Oba": ["오바댜", "오바", "옵", "oba", "obad", "obadiah"],
        "Jon": ["요나", "욘", "jon", "jonah"],
        "Mic": ["미가", "미", "mic", "micah"],
        "Nah": ["나훔", "나", "nah", "nahum"],
        "Hab": ["하박국", "하박", "합", "hab", "habakkuk"],
        "Zep": ["스바냐", "스바", "습", "zep", "zeph", "zephaniah"],
        "Hag": ["학개", "학", "hag", "haggai"],
        "Zec": ["스가랴", "슥", "zec", "zechariah"],
        "Mal": ["말라기", "말", "mal", "malachi"],
        "Mat": ["마태복음", "마태", "마", "mat", "matt", "matthew"],
        "Mar": ["마가복음", "마가", "막", "mar", "mrk", "mark"],
        "Luk": ["누가복음", "누가", "눅", "luk", "luke"],
        "Joh": ["요한복음", "요한", "요", "jo", "joh", "john"],
        "Act": ["사도행전", "사도", "행", "act", "acts"],
        "Rom": ["로마서", "로마", "롬", "ro", "rom", "romans"],
        "1Co": ["고린도전서", "고전", "1co", "1cor", "1corinthians"],
        "2Co": ["고린도후서", "고후", "2co", "2cor", "2corinthians"],
        "Gal": ["갈라디아서", "갈라", "갈", "gal", "galatians"],
        "Eph": ["에베소서", "에베", "엡", "eph", "ephesians"],
        "Phi": ["빌립보서", "빌립", "빌", "phi", "phil", "philippians"],
        "Col": ["골로새서", "골로", "골", "col", "colossians"],
        "1Th": ["데살로니가전서", "살전", "1th", "1thess", "1thessalonians"],
        "2Th": ["데살로니가후서", "살후", "2th", "2thess", "2thessalonians"],
        "1Ti": ["디모데전서", "딤전", "1tim", "1timothy"],
        "2Ti": ["디모데후서", "딤후", "2tim", "2timothy"],
        "Tit": ["디도서", "디도", "딛", "tit", "titus"],
        "Phm": ["빌레몬서", "빌레", "몬", "phm", "philemon"],
        "Heb": ["히브리서", "히브", "히", "heb", "hebrew", "hebrews"],
        "Jam": ["야고보서", "야고", "약", "jam", "jas", "james"],
        "1Pe": ["베드로전서", "벧전", "1pe", "1pet", "1peter"],
        "2Pe": ["베드로후서", "벧후", "2pe", "2pet", "2peter"],
        "1Jo": ["요한1서", "요일", "1jo", "1joh", "1john"],
        "2Jo": ["요한2서", "요이", "2jo", "2joh", "2john"],
        "3Jo": ["요한3서", "요삼", "3jo", "3joh", "3john"],
        "Jude": ["유다서", "유", "jud", "jude"],
        "Rev": ["요한계시록", "계시록", "계", "re", "rev", "revelation"],
    }

    flat = {}

    def smart_capitalize(s: str) -> str:
        for i, c in enumerate(s):
            if c.isalpha():
                return s[:i] + s[i:].capitalize()
        return s

    for std, aliases in m.items():
        flat[std.lower()] = std
        flat[std.upper()] = std
        flat[std.capitalize()] = std
        flat[std] = std

        for a in aliases:
            flat[a.lower()] = std
            flat[a.upper()] = std
            flat[a.capitalize()] = std
            flat[a] = std

            if a and a[0].isdigit():
                titled_version = smart_capitalize(a)
                if (
                    titled_version != a.lower()
                    and titled_version != a.upper()
                    and titled_version != a.capitalize()
                ):
                    flat[titled_version] = std

    additional_mappings = {
        "요": "Joh",
        "요일": "1Jo",
        "요이": "2Jo",
        "요삼": "3Jo",
        "롬": "Rom",
        "고전": "1Co",
        "고후": "2Co",
        "갈": "Gal",
        "엡": "Eph",
        "빌": "Phi",
        "골": "Col",
        "살전": "1Th",
        "살후": "2Th",
        "딤전": "1Ti",
        "딤후": "2Ti",
        "딛": "Tit",
        "빌레": "Phm",
        "몬": "Phm",
        "히": "Heb",
        "약": "Jam",
        "벧전": "1Pe",
        "벧후": "2Pe",
        "유": "Jude",
        "계": "Rev",
        "창": "Gen",
        "출": "Exo",
        "레": "Lev",
        "민": "Num",
        "신": "Deu",
        "수": "Jos",
        "삿": "Jud",
        "룻": "Rut",
        "삼상": "1Sa",
        "삼하": "2Sa",
        "왕상": "1Ki",
        "왕하": "2Ki",
        "대상": "1Ch",
        "대하": "2Ch",
        "스": "Ezr",
        "느": "Neh",
        "에": "Est",
        "욥": "Job",
        "시": "Psa",
        "잠": "Pro",
        "전": "Ecc",
        "아": "Sng",
        "사": "Isa",
        "렘": "Jer",
        "애": "Lam",
        "겔": "Eze",
        "단": "Dan",
        "호": "Hos",
        "욜": "Joe",
        "암": "Amo",
        "옵": "Oba",
        "욘": "Jon",
        "미": "Mic",
        "나": "Nah",
        "합": "Hab",
        "습": "Zep",
        "학": "Hag",
        "슥": "Zec",
        "말": "Mal",
        "마": "Mat",
        "막": "Mar",
        "눅": "Luk",
        "행": "Act",
    }

    for key, value in additional_mappings.items():
        flat[key.lower()] = value
        flat[key.upper()] = value
        flat[key.capitalize()] = value
        flat[key] = value

    return flat, m


# === 새로 추가: 성경 모듈 ID 변환 ===
def get_book_id_from_code(book_code):
    """
    표준 책 코드 (Gen, Exo 등) 를 성경 모듈 DB 의 book_id 로 변환
    """
    book_order = [
        "Gen", "Exo", "Lev", "Num", "Deu", "Jos", "Jud", "Rut",
        "1Sa", "2Sa", "1Ki", "2Ki", "1Ch", "2Ch", "Ezr", "Neh", "Est",
        "Job", "Psa", "Pro", "Ecc", "Sng", "Isa", "Jer", "Lam", "Eze",
        "Dan", "Hos", "Joe", "Amo", "Oba", "Jon", "Mic", "Nah", "Hab",
        "Zep", "Hag", "Zec", "Mal",
        "Mat", "Mar", "Luk", "Joh", "Act", "Rom", "1Co", "2Co", "Gal",
        "Eph", "Phi", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm",
        "Heb", "Jam", "1Pe", "2Pe", "1Jo", "2Jo", "3Jo", "Jude", "Rev"
    ]
    try:
        return book_order.index(book_code) + 1
    except ValueError:
        return None
