from enum import Enum


class Statuses(Enum):
    expected_production = 1,
    exists_production = 2,
    expected_buffer = 3,
    exists_buffer = 4
