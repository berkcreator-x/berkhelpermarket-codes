from dataclasses import dataclass


@dataclass
class GenerationPackage:
    price_rub: int
    generations: int
