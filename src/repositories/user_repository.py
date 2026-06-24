from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import GenerationLog, GenerationType, PlanType, User


class UserRepository:
    """Data access layer для сущности User."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, telegram_id: int, username: str | None) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is not None:
            if username and user.username != username:
                user.username = username
                await self._session.flush()
            return user

        user = User(
            telegram_id=telegram_id,
            username=username,
            plan=PlanType.FREE,
            generation_balance=1,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        stmt = select(User).order_by(User.id).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_all(self) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(User)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def add_generations(self, user: User, amount: int) -> User:
        """Начислить генерации. Не защищает от гонок — используй только в платёжном flow."""
        user.generation_balance += amount
        await self._session.flush()
        return user

    async def deduct_generations(self, user: User, amount: int) -> User:
        """Простое списание без блокировки (для обратной совместимости)."""
        if user.generation_balance < amount:
            raise ValueError("Insufficient generation balance")
        user.generation_balance -= amount
        await self._session.flush()
        return user

    async def deduct_generations_safe(self, user: User, amount: int) -> User:
        """Атомарное списание с SELECT FOR UPDATE — защита от race conditions.

        Перечитывает запись пользователя с блокировкой, проверяет баланс и
        списывает атомарно. Используется в GenerationService.
        """
        from src.ai.generation_service import InsufficientBalanceError

        # Перечитываем с блокировкой строки
        stmt = (
            select(User)
            .where(User.id == user.id)
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        locked_user = result.scalar_one()

        if locked_user.generation_balance < amount:
            raise InsufficientBalanceError(
                f"Недостаточно генераций: нужно {amount}, "
                f"доступно {locked_user.generation_balance}"
            )

        locked_user.generation_balance -= amount
        # Синхронизируем in-memory объект
        user.generation_balance = locked_user.generation_balance
        await self._session.flush()
        return locked_user

    async def set_balance(self, user: User, balance: int) -> User:
        """Установить баланс напрямую (только для админа)."""
        if balance < 0:
            balance = 0
        user.generation_balance = balance
        await self._session.flush()
        return user

    async def log_generation(self, user: User, gen_type: GenerationType) -> GenerationLog:
        log = GenerationLog(user_id=user.id, type=gen_type)
        self._session.add(log)
        await self._session.flush()
        return log

    async def count_generations(
        self, user: User, gen_type: GenerationType | None = None
    ) -> int:
        from sqlalchemy import func
        stmt = (
            select(func.count())
            .select_from(GenerationLog)
            .where(GenerationLog.user_id == user.id)
        )
        if gen_type is not None:
            stmt = stmt.where(GenerationLog.type == gen_type)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
