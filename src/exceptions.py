from __future__ import annotations

"""
BerkHelperMarket Exception System

Единая система исключений проекта.

Правила:

1. Все пользовательские исключения наследуются от BerkHelperMarketError.
2. Не использовать ValueError, RuntimeError и подобные в бизнес-логике.
3. В Handler'ах ловится BerkHelperMarketError.
4. Repository не импортирует AI.
5. AI не импортирует Repository.
"""


# ==========================================================
# BASE
# ==========================================================

class BerkHelperMarketError(Exception):
    """Базовый класс всех исключений проекта."""


# ==========================================================
# BALANCE
# ==========================================================

class BalanceError(BerkHelperMarketError):
    """Ошибки работы с балансом."""


class InsufficientBalanceError(BalanceError):
    """Недостаточно генераций."""


class InvalidBalanceOperation(BalanceError):
    """Некорректная операция изменения баланса."""


class BalanceOverflow(BalanceError):
    """Переполнение баланса."""


# ==========================================================
# PAYMENTS
# ==========================================================

class PaymentError(BerkHelperMarketError):
    """Базовая ошибка оплаты."""


class PaymentNotFound(PaymentError):
    """Платёж не найден."""


class PaymentAlreadyConfirmed(PaymentError):
    """Платёж уже подтвержден."""


class PaymentVerificationError(PaymentError):
    """Ошибка проверки оплаты."""


class InvalidWebhookSignature(PaymentError):
    """Подпись webhook не совпадает."""


class InvalidPaymentPayload(PaymentError):
    """Некорректные данные webhook."""


class PaymentTimeout(PaymentError):
    """Истекло время ожидания оплаты."""


# ==========================================================
# AI
# ==========================================================

class AIServiceError(BerkHelperMarketError):
    """Базовая ошибка AI."""


class PromptBuildError(AIServiceError):
    """Ошибка построения промпта."""


class AIConnectionError(AIServiceError):
    """Нет соединения с AI."""


class AIResponseError(AIServiceError):
    """AI вернул некорректный ответ."""


class AIQuotaExceeded(AIServiceError):
    """Исчерпан лимит AI."""


class AIContentRejected(AIServiceError):
    """AI отказался генерировать."""


# ==========================================================
# GENERATION
# ==========================================================

class GenerationError(BerkHelperMarketError):
    """Ошибка генерации."""


class ProductValidationError(GenerationError):
    """Товар не прошёл проверку."""


class UnsupportedProductError(GenerationError):
    """Товар невозможно обработать."""


class InvalidTZError(GenerationError):
    """Некорректное ТЗ."""


class GenerationCanceled(GenerationError):
    """Генерация отменена."""


class GenerationFailed(GenerationError):
    """Ошибка генерации."""


# ==========================================================
# USER
# ==========================================================

class UserError(BerkHelperMarketError):
    """Ошибка пользователя."""


class UserNotFound(UserError):
    """Пользователь не найден."""


class UserBlocked(UserError):
    """Пользователь заблокирован."""


class UserAlreadyExists(UserError):
    """Пользователь уже существует."""


# ==========================================================
# DATABASE
# ==========================================================

class RepositoryError(BerkHelperMarketError):
    """Ошибка репозитория."""


class DatabaseConsistencyError(RepositoryError):
    """Нарушена целостность БД."""


class EntityNotFound(RepositoryError):
    """Запись не найдена."""


class DuplicateEntityError(RepositoryError):
    """Объект уже существует."""


# ==========================================================
# FILES
# ==========================================================

class FileError(BerkHelperMarketError):
    """Ошибка обработки файлов."""


class UnsupportedFileType(FileError):
    """Неподдерживаемый формат файла."""


class EmptyFileError(FileError):
    """Файл пуст."""


class FileTooLarge(FileError):
    """Файл слишком большой."""


class FileReadError(FileError):
    """Ошибка чтения файла."""


# ==========================================================
# IMAGE
# ==========================================================

class ImageGenerationError(BerkHelperMarketError):
    """Ошибка генерации изображения."""


class ImageValidationError(ImageGenerationError):
    """Ошибка проверки изображения."""


class ImageRenderError(ImageGenerationError):
    """Ошибка рендера изображения."""


# ==========================================================
# ADMIN
# ==========================================================

class AdminError(BerkHelperMarketError):
    """Ошибка администратора."""


class PermissionDenied(AdminError):
    """Недостаточно прав."""


# ==========================================================
# EXPORTS
# ==========================================================

__all__ = [
    "BerkHelperMarketError",

    "BalanceError",
    "InsufficientBalanceError",
    "InvalidBalanceOperation",
    "BalanceOverflow",

    "PaymentError",
    "PaymentNotFound",
    "PaymentAlreadyConfirmed",
    "PaymentVerificationError",
    "InvalidWebhookSignature",
    "InvalidPaymentPayload",
    "PaymentTimeout",

    "AIServiceError",
    "PromptBuildError",
    "AIConnectionError",
    "AIResponseError",
    "AIQuotaExceeded",
    "AIContentRejected",

    "GenerationError",
    "ProductValidationError",
    "UnsupportedProductError",
    "InvalidTZError",
    "GenerationCanceled",
    "GenerationFailed",

    "UserError",
    "UserNotFound",
    "UserBlocked",
    "UserAlreadyExists",

    "RepositoryError",
    "DatabaseConsistencyError",
    "EntityNotFound",
    "DuplicateEntityError",

    "FileError",
    "UnsupportedFileType",
    "EmptyFileError",
    "FileTooLarge",
    "FileReadError",

    "ImageGenerationError",
    "ImageValidationError",
    "ImageRenderError",

    "AdminError",
    "PermissionDenied",
]
