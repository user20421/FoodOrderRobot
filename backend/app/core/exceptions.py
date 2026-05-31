"""
业务异常定义
统一异常体系，便于API层统一处理
"""


class AppException(Exception):
    """应用基础异常"""
    def __init__(self, message: str = "应用错误", status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationException(AppException):
    """参数校验异常"""
    def __init__(self, message: str = "参数校验失败"):
        super().__init__(message, status_code=400)


class AuthenticationException(AppException):
    """认证异常"""
    def __init__(self, message: str = "认证失败"):
        super().__init__(message, status_code=401)


class AuthorizationException(AppException):
    """权限异常"""
    def __init__(self, message: str = "权限不足"):
        super().__init__(message, status_code=403)


class NotFoundException(AppException):
    """资源不存在异常"""
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, status_code=404)


class BusinessException(AppException):
    """业务逻辑异常"""
    def __init__(self, message: str = "业务处理失败"):
        super().__init__(message, status_code=422)


class AIServiceException(AppException):
    """AI服务异常"""
    def __init__(self, message: str = "AI服务暂时不可用"):
        super().__init__(message, status_code=503)
