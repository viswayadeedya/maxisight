class MaxisightError(Exception):
    pass


class CrawlerError(MaxisightError):
    pass


class StorageError(MaxisightError):
    pass


class AuthError(MaxisightError):
    pass
