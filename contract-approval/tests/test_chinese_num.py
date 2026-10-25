from app.utils.chinese_num import chinese_amount_to_int


def test_basic():
    assert chinese_amount_to_int("伍拾万元整") == 500000
    assert chinese_amount_to_int("壹拾贰万捌仟元整") == 128000
    assert chinese_amount_to_int("捌万陆仟元整") == 86000
    assert chinese_amount_to_int("壹佰万") == 1000000


def test_edge():
    assert chinese_amount_to_int("拾万元") == 100000  # 省略开头的"一"
    assert chinese_amount_to_int("一万二千三百四十五") == 12345
    assert chinese_amount_to_int("abc") is None
    assert chinese_amount_to_int("") is None
