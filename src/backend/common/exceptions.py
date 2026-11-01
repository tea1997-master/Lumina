"""Lumina 共通例外クラス定義"""


class LuminaError(Exception):
    """アプリケーション共通基底例外"""
    pass


class ValidationError(LuminaError):
    """入力値・データ検証エラー"""
    pass


class NotFoundError(LuminaError):
    """リソース未検出エラー"""
    pass
