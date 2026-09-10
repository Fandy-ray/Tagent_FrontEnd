class AgentAPIError(Exception):
    def __init__(self, message: str, status: int, code: str, error_type: str = "invalid_request_error"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.error_type = error_type


class ModelNotFoundError(AgentAPIError):
    def __init__(self, model_id: str):
        super().__init__(
            f"Model not found or disabled: {model_id}",
            status=404,
            code="model_not_found",
        )
