class InvalidCredentialsError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InvalidRefreshTokenError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid or expired refresh token")


class InactiveUserError(Exception):
    def __init__(self) -> None:
        super().__init__("User is inactive")


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


class LoanPermissionDeniedError(Exception):
    def __init__(self) -> None:
        super().__init__("Insufficient permissions")


class InvalidLoanStateError(Exception):
    pass


class LoanEquipmentUnavailableError(Exception):
    def __init__(self, ids: list[int]) -> None:
        self.ids = ids
        super().__init__(f"Equipment does not exist, is inactive or is already reserved: {ids}")


class UserNotFoundError(Exception):
    def __init__(self, id: int) -> None:
        super().__init__(f"No user with {id} ID was found")


class UserAlreadyExistsError(Exception):
    def __init__(self) -> None:
        super().__init__("A user with this email or phone already exists")


class InvalidUserPromotionError(Exception):
    def __init__(self) -> None:
        super().__init__("Only students can be promoted to manager")


class UserPermissionDeniedError(Exception):
    def __init__(self) -> None:
        super().__init__("Insufficient permissions")


class LoanNotFoundError(Exception):
    def __init__(self, id: int) -> None:
        super().__init__(f"No loan with {id} ID was found")
