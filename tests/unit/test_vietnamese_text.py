from src.core.vietnamese_text import slugify_vietnamese, transliterate_vietnamese


def test_transliterate_vietnamese_maps_full_alphabet_groups() -> None:
    assert transliterate_vietnamese("ÀÁẢÃẠ ÂẦẤẨẪẬ ĂẰẮẲẴẶ") == ("AAAAA AAAAAA AAAAAA")
    assert transliterate_vietnamese("àáảãạ âầấẩẫậ ăằắẳẵặ") == ("aaaaa aaaaaa aaaaaa")
    assert transliterate_vietnamese("ÈÉẺẼẸ ÊỀẾỂỄỆ") == "EEEEE EEEEEE"
    assert transliterate_vietnamese("èéẻẽẹ êềếểễệ") == "eeeee eeeeee"
    assert transliterate_vietnamese("ÌÍỈĨỊ ÒÓỎÕỌ ÔỒỐỔỖỘ ƠỜỚỞỠỢ") == (
        "IIIII OOOOO OOOOOO OOOOOO"
    )
    assert transliterate_vietnamese("ìíỉĩị òóỏõọ ôồốổỗộ ơờớởỡợ") == (
        "iiiii ooooo oooooo oooooo"
    )
    assert transliterate_vietnamese("ÙÚỦŨỤ ƯỪỨỬỮỰ ỲÝỶỸỴ Đđ") == (
        "UUUUU UUUUUU YYYYY Dd"
    )
    assert transliterate_vietnamese("ùúủũụ ưừứửữự ỳýỷỹỵ Đđ") == (
        "uuuuu uuuuuu yyyyy Dd"
    )


def test_slugify_vietnamese_uses_requested_separator_and_fallback() -> None:
    assert (
        slugify_vietnamese("Điều trị nội trú - Đồng hành trọn đời")
        == "dieu-tri-noi-tru-dong-hanh-tron-doi"
    )
    assert (
        slugify_vietnamese(
            "Quyền lợi Điều trị nội trú",
            separator="_",
            fallback="unknown",
        )
        == "quyen_loi_dieu_tri_noi_tru"
    )
    assert slugify_vietnamese("!!!", fallback="unknown") == "unknown"
