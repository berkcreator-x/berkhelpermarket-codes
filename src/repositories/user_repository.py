from __future__ import annotations

from dataclasses import dataclass
import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import InsufficientBalanceError
from src.models import GenerationLog, GenerationType, PlanType, User
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GenerationStats:
    total: int
    new_count: int
    improve_count: int
    total_cost: int
    avg_quality: float | None
    avg_duration_ms: float | None
    last_generation_at: datetime.datetime | None


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

        logger.info(
            "user_created",
            telegram_id=telegram_id,
        )

        return user

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[User]:
        stmt = (
            select(User)
            .order_by(User.id)
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(stmt)

        return list(result.scalars().all())

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(User)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def add_generations(
        self,
        user: User,
        amount: int,
    ) -> User:

        if amount <= 0:
            return user

        user.generation_balance += amount

        logger.info(
            "generation_balance_added",
            user_id=user.id,
            amount=amount,
            balance=user.generation_balance,
        )

        await self._session.flush()

        return user

    async def deduct_generations(
        self,
        user: User,
        amount: int,
    ) -> User:

        if amount <= 0:
            return user

        if user.generation_balance < amount:
            raise InsufficientBalanceError(
                f"Недостаточно генераций. "
                f"Нужно {amount}, "
                f"доступно {user.generation_balance}."
            )

        user.generation_balance -= amount

        logger.info(
            "generation_balance_deducted",
            user_id=user.id,
            amount=amount,
            balance=user.generation_balance,
        )

        await self._session.flush()

        return user

    async def deduct_generations_safe(
        self,
        user: User,
        amount: int,
    ) -> User:
        """
        Атомарное списание с SELECT FOR UPDATE.
        """

        stmt = (
            select(User)
            .where(User.id == user.id)
            .with_for_update()
        )

        result = await self._session.execute(stmt)

        locked_user = result.scalar_one()

        if locked_user.generation_balance < amount:
            raise InsufficientBalanceError(
                f"Недостаточно генераций. "
                f"Нужно {amount}, "
                f"доступно {locked_user.generation_balance}."
            )

        locked_user.generation_balance -= amount

        user.generation_balance = locked_user.generation_balance

        logger.info(
            "generation_balance_deducted_safe",
            user_id=locked_user.id,
            amount=amount,
            balance=locked_user.generation_balance,
        )

        await self._session.flush()

        return locked_user

    async def set_balance(
        self,
        user: User,
        balance: int,
    ) -> User:

        if balance < 0:
            raise ValueError("Balance cannot be negative")

        user.generation_balance = balance

        logger.info(
            "generation_balance_set",
            user_id=user.id,
            balance=balance,
        )

        await self._session.flush()

        return user

    async def log_generation(
        self,
        user: User,
        gen_type: GenerationType,
        product_title: str | None = None,
        cost: int = 1,
        quality_score: int | None = None,
        duration_ms: int | None = None,
        status: str = "success",
    ) -> GenerationLog:


        log = GenerationLog(
            user_id=user.id,
            type=gen_type,
            product_title=product_title,
            cost=cost,
            quality_score=quality_score,
            duration_ms=duration_ms,
            status=status,
        )


        self._session.add(log)

        await self._session.flush()


        logger.info(
            "generation_logged",
            user_id=user.id,
            generation_type=gen_type.value,
            product_title=product_title,
            cost=cost,
            quality_score=quality_score,
            duration_ms=duration_ms,
            status=status,
        )


        return log

    async def count_generations(
        self,
        user: User,
        gen_type: GenerationType | None = None,
    ) -> int:

        stmt = (
            select(func.count())
            .select_from(GenerationLog)
            .where(
                GenerationLog.user_id == user.id
            )
        )

        if gen_type is not None:
            stmt = stmt.where(
                GenerationLog.type == gen_type
            )

        result = await self._session.execute(stmt)

        return int(result.scalar_one())

    async def get_recent_generations(
        self,
        user: User,
        limit: int = 10,
    ) -> list[GenerationLog]:

        stmt = (
            select(GenerationLog)
            .where(GenerationLog.user_id == user.id)
            .order_by(GenerationLog.created_at.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)

        return list(result.scalars().all())

    async def get_generation_stats(
        self,
        user: User,
    ) -> GenerationStats:
        """
        Одним запросом собирает агрегированную статистику
        генераций пользователя для раздела "Моя статистика".
        """

        stmt = select(
            func.count(GenerationLog.id),
            func.sum(
                case(
                    (GenerationLog.type == GenerationType.NEW, 1),
                    else_=0,
                )
            ),
            func.sum(
                case(
                    (GenerationLog.type == GenerationType.IMPROVE, 1),
                    else_=0,
                )
            ),
            func.coalesce(func.sum(GenerationLog.cost), 0),
            func.avg(GenerationLog.quality_score),
            func.avg(GenerationLog.duration_ms),
            func.max(GenerationLog.created_at),
        ).where(GenerationLog.user_id == user.id)

        result = await self._session.execute(stmt)

        (
            total,
            new_count,
            improve_count,
            total_cost,
            avg_quality,
            avg_duration_ms,
            last_generation_at,
        ) = result.one()

        return GenerationStats(
            total=int(total or 0),
            new_count=int(new_count or 0),
            improve_count=int(improve_count or 0),
            total_cost=int(total_cost or 0),
            avg_quality=(
                float(avg_quality)
                if avg_quality is not None
                else None
            ),
            avg_duration_ms=(
                float(avg_duration_ms)
                if avg_duration_ms is not None
                else None
            ),
            last_generation_at=last_generation_at,
        )
