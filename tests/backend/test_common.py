"""共通例外および基底モジュールの単体テスト"""

from common.exceptions import LuminaError, ValidationError, NotFoundError


def test_lumina_exceptions_hierarchy():
    """例外階層が正しく継承されていることを検証"""
    val_err = ValidationError("無効な入力値です")
    not_found = NotFoundError("見つかりません")

    assert isinstance(val_err, LuminaError)
    assert isinstance(not_found, LuminaError)
    assert str(val_err) == "無効な入力値です"
