"""试卷领域异常。

status_code 与 HTTP 契约一一对应，由 app/api/error_handler.py 统一翻译成响应体。

放在 errors/ 而不是仓储或服务模块里：异常是领域词汇，api、service、infra
三层都要用它，谁也不该为了拿一个异常类去 import 另一层。
"""

from __future__ import annotations


# ====================== 服务错误（HTTP 状态码契约） ======================
class ExamServiceError(Exception):
    """基类：status_code 与 HTTP 契约一一对应。"""

    status_code = 500
    code = "exam_service_error"

    @property
    def message(self) -> str:
        return str(self)


class InvalidExamRequestError(ExamServiceError):
    """参数不符合契约（多余题号、类型错误等）。"""

    status_code = 422
    code = "invalid_exam_request"


class ModelMismatchError(InvalidExamRequestError):
    """判卷模型与生成试卷时锁定的模型不一致。"""

    code = "exam_model_mismatch"


class ExamGoneError(ExamServiceError):
    """试卷不存在或已过期。"""

    status_code = 410
    code = "exam_gone"


class ExamBusyError(ExamServiceError):
    """生成/判分并发闸门已满。"""

    status_code = 429
    code = "exam_busy"


class UpstreamLLMError(ExamServiceError):
    """LLM 拒绝、网络失败或连续输出非法 JSON。"""

    status_code = 502
    code = "upstream_llm_error"


class UpstreamTimeoutError(ExamServiceError):
    """LLM 调用超时。"""

    status_code = 504
    code = "upstream_timeout"
