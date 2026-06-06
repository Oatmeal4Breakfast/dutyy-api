from uuid import UUID


class DomainValidationError(Exception):
    def __init__(self, entity: str, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{entity} validation failed {','.join(self.errors)}")


class DutyyAssignedError(Exception):
    def __init__(self, id: UUID) -> None:
        self.id = id
        super().__init__(f"Dutyy with id {self.id} already assigned to project")


class DutyyNotAssignedError(Exception):
    def __init__(self, id: UUID) -> None:
        self.id = id
        super().__init__(f"Dutyy with id {self.id} is not assigned to project")
