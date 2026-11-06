class AppError(Exception):
    """An error that is safe to show to the user. `status` is the HTTP status code."""

    def __init__(self, message, status=400, extra=None):
        super().__init__(message)
        self.status = status
        self.extra = extra or {}
