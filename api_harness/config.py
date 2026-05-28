"""api_harness 配置:端点 + 公共 header + 认证 + 轮询参数。

参考: SPEC.md §1。
约束(CLAUDE.md 第 3 条):密钥/token 只从环境变量读,绝不写进文件;
`x-gateway-checked` 是非密网关 header,可硬编码。
"""
from __future__ import annotations

import os

# 后端基址(开发环境)。scheme/host 可用环境变量覆盖(默认 https,失败再试 http)。
BASE_URL = os.environ.get("SEENFUL_API_BASE", "https://api-dev.haoduo.vip").rstrip("/")

# 三个端点(SPEC §1)
SUBMIT_PATH = "/api/v1/yxh-service/photo-meta/mockL1Finish"      # API#1 提交
RESULT_PATH = "/api/v1/yxh-service/photo-meta/mockL1Result"      # API#2 取结果
DELETE_PATH = "/api/v1/yxh-service/photo-meta/mockL1Result/del"  # API#3 删除(按 mockBizId)

SUBMIT_URL = BASE_URL + SUBMIT_PATH
RESULT_URL = BASE_URL + RESULT_PATH
DELETE_URL = BASE_URL + DELETE_PATH

# 轮询 / 超时(SPEC §9 待定,先给保守默认,均可环境变量覆盖)
POLL_INTERVAL_S = float(os.environ.get("SEENFUL_POLL_INTERVAL", "2.0"))
POLL_TIMEOUT_S = float(os.environ.get("SEENFUL_POLL_TIMEOUT", "60.0"))
REQUEST_TIMEOUT_S = float(os.environ.get("SEENFUL_REQUEST_TIMEOUT", "30.0"))


# 租户(网关要求,缺则 403「租户不能为空」)。非密配置,可硬编码,可环境变量覆盖。
# 实测有效的是 x-permission-tenant header(值=租户 code);tenantinfo 一并保留。
TENANT_CODE = os.environ.get("SEENFUL_TENANT_CODE", "92")
USER_ID = os.environ.get("SEENFUL_USER_ID", "16069")  # 服务层用户身份(缺则 500)
TENANT_INFO = os.environ.get(
    "SEENFUL_TENANT_INFO",
    '{"tenantList":[{"tenantCode":92,"tenantId":""}]}',
)


# developerTest 是 query 参数(开发/mock 模式开关;缺则后端走真实链路 → 500)。
DEVELOPER_TEST = os.environ.get("SEENFUL_DEVELOPER_TEST", "1")


def default_params() -> dict[str, str]:
    """所有请求公共 query 参数。sign 为鉴权签名,只从环境变量 SEENFUL_SIGN 读(CLAUDE 第3条)。"""
    params = {"developerTest": DEVELOPER_TEST}
    sign = os.environ.get("SEENFUL_SIGN")
    if sign:
        params["sign"] = sign
    return params


def default_headers() -> dict[str, str]:
    """公共 header。x-permission-tenant 为网关必需;可选 token 仅从环境变量 SEENFUL_API_TOKEN 读。"""
    headers = {
        "Content-Type": "application/json",
        "x-gateway-checked": "true",
        "x-permission-tenant": TENANT_CODE,
        "x-user-id": USER_ID,
        "tenantinfo": TENANT_INFO,
    }
    token = os.environ.get("SEENFUL_API_TOKEN")
    if token:
        headers["Authorization"] = token
    return headers
