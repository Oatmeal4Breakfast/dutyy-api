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


class UserAlreadyExistsError(Exception):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"user with email {self.email} already exists")


class ProjectAlreadyExistsError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"project with name {self.name} already exists")


class DeviceCodeCollisionError(Exception):
    def __init__(self) -> None:
        super().__init__("device_code collision error")
