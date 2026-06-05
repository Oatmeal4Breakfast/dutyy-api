class DomainValidationError(Exception):
    def __init__(self, entity: str, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{entity} validation failed {','.join(self.errors)}")
