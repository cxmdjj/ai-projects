"""业务异常与全局处理。"""


class BizError(Exception):
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)


class AuthError(BizError):
    def __init__(self, message: str = "未登录或登录已过期"):
        super().__init__(message, code=401)


class PathTraversalError(BizError):
    def __init__(self, message: str = "非法文件路径"):
        super().__init__(message, code=400)
