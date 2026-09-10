"""provider 注册表的领域异常。

与 exam_errors 同理放在 errors/：api 层要在 @errorhandler 里注册它，
若留在 repository 里，api 就得反向依赖仓储层。
"""

from __future__ import annotations


class RegistryLoadError(RuntimeError):
    """The provider registry exists but cannot be trusted or recovered automatically."""
