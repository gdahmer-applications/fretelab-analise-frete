
from typing import List, Tuple

class LabelGenerator:
    """
    Responsável por montar bins e labels de faixas de peso.
    """
    def __init__(self, max_step: int, max_limit: int, overflow_limit: int):
        self.max_step = max_step
        self.max_limit = max_limit
        self.overflow_limit = overflow_limit

    def generate(self) -> Tuple[list, list]:
        bins = list(range(0, self.max_limit + self.max_step, self.max_step))
        if bins[-1] != self.overflow_limit:
            bins.append(self.overflow_limit)

        labels: List[str] = []
        for i in range(len(bins) - 1):
            low = bins[i] + (1 if i != 0 else 0)
            high = bins[i+1]
            if i == 0:
                labels.append(f"0-{high}")
            else:
                labels.append(f"{low}-{high}")
        return bins, labels
