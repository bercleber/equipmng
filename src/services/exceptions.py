class CategoryNotFoundError(Exception):
    def __init__(self, id: int) -> None:
        super().__init__(f"No category with {id} ID was found")


class CategoryAlreadyExistsError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"Category with {name} already exists")


class CategoryInUseError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"Category {name} contains registered equipment")


class EquipmentAlreadyExistsError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(f"Equipment with code '{code}' already exists")


class EquipmentNotFoundError(Exception):
    def __init__(self, id: int) -> None:
        super().__init__(f"No equipment with {id} ID was found")


class NoEquipmentsLoanError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__("Cannot create a loan without any equipment")


class LoanNotFoundError(Exception):
    def __init__(self, id: int) -> None:
        super().__init__(f"No loan with {id} ID was found")
