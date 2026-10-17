from pydantic import ValidationError


class CvTailorError(Exception):
    pass


class ConfigurationError(CvTailorError):
    pass


class TailoringError(CvTailorError):
    pass


class RenderingError(CvTailorError):
    pass


class DeliveryError(CvTailorError):
    pass


class JobFailedError(CvTailorError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def describe_validation_error(subject: str, error: ValidationError) -> str:
    details = "; ".join(
        f"{'.'.join(str(part) for part in detail['loc'])}: {detail['msg']}"
        for detail in error.errors(include_input=False, include_url=False)
    )
    return f"invalid {subject}: {details}"
