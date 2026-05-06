import re
import unicodedata

_VIETNAMESE_ASCII_GROUPS = {
    "A": "ÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶ",
    "a": "àáảãạâầấẩẫậăằắẳẵặ",
    "D": "Đ",
    "d": "đ",
    "E": "ÈÉẺẼẸÊỀẾỂỄỆ",
    "e": "èéẻẽẹêềếểễệ",
    "I": "ÌÍỈĨỊ",
    "i": "ìíỉĩị",
    "O": "ÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ",
    "o": "òóỏõọôồốổỗộơờớởỡợ",
    "U": "ÙÚỦŨỤƯỪỨỬỮỰ",
    "u": "ùúủũụưừứửữự",
    "Y": "ỲÝỶỸỴ",
    "y": "ỳýỷỹỵ",
}

_VIETNAMESE_ASCII_TRANSLATION = str.maketrans(
    {
        source_character: ascii_character
        for ascii_character, source_characters in _VIETNAMESE_ASCII_GROUPS.items()
        for source_character in source_characters
    }
)


def transliterate_vietnamese(value: str) -> str:
    """Return an ASCII representation of Vietnamese text."""
    translated_value = value.translate(_VIETNAMESE_ASCII_TRANSLATION)
    normalized_value = unicodedata.normalize("NFKD", translated_value)
    without_combining_marks = "".join(
        character
        for character in normalized_value
        if not unicodedata.combining(character)
    )
    return without_combining_marks.encode("ascii", "ignore").decode("ascii")


def slugify_vietnamese(
    value: str,
    *,
    separator: str = "-",
    fallback: str = "section",
) -> str:
    """Build a deterministic ASCII slug from Vietnamese text."""
    ascii_value = transliterate_vietnamese(value)
    slug = re.sub(r"[^a-zA-Z0-9]+", separator, ascii_value.lower()).strip(separator)
    return slug or fallback
