from enum import StrEnum, auto


class DutyyStatus(StrEnum):
    NEW = auto()
    IN_PROGRESS = auto()
    COMPLETE = auto()


class ProjectStatus(StrEnum):
    NEW = auto()
    IN_PROGRESS = auto()
    COMPLETE = auto()
    ABANDONED = auto()


class UserStatus(StrEnum):
    ACTIVE = auto()
    INACTIVE = auto()
    BLOCKED = auto()
