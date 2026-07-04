from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationPackage:
    id: str
    title: str
    price_rub: int
    generations: int


GENERATION_PACKAGES: dict[str, GenerationPackage] = {
    "start": GenerationPackage(
        id="start",
        title="Старт",
        price_rub=99,
        generations=10,
    ),
    "business": GenerationPackage(
        id="business",
        title="Бизнес",
        price_rub=399,
        generations=50,
    ),
    "pro": GenerationPackage(
        id="pro",
        title="PRO",
        price_rub=999,
        generations=150,
    ),
}


def get_package(package_id: str) -> GenerationPackage | None:
    return GENERATION_PACKAGES.get(package_id)
