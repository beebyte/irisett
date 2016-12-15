"""Common webapi exceptions."""


class WebAPIError(Exception):
    pass


class InvalidData(WebAPIError):
    pass


class PermissionDenied(WebAPIError):
    pass


class NotFound(WebAPIError):
    pass
