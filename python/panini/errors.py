class PaniniError(Exception):
    pass


class ParseError(PaniniError):
    def __init__(self, location: str, message: str):
        super().__init__(f"parse error at {location}: {message}")
        self.location = location


class TypeError_(PaniniError):
    pass


class SemanticError(PaniniError):
    pass


class UnsupportedError(PaniniError):
    def __init__(self, required, backend: str):
        super().__init__(
            f"COMPILE_UNSUPPORTED: required {required!r} not available on backend {backend}"
        )
        self.required = required
        self.backend = backend


class ConstraintError(PaniniError):
    pass
