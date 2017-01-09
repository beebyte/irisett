class IrisettError(Exception):
    def __str__(self) -> str:
        if len(self.args) == 1:
            ret = self.args[0]
        else:
            ret = str(self.__class__.__name__)
        return ret


class InvalidArguments(IrisettError):
    pass
