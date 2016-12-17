"""Common webmgmt exceptions."""


class WebMgmtError(Exception):
    pass


class InvalidData(WebMgmtError):
    pass


class PermissionDenied(WebMgmtError):
    pass


class NotFound(WebMgmtError):
    pass


class MissingLogin(WebMgmtError):
    pass
