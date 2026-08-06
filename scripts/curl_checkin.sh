#!/bin/bash
# GitHub Actions 专用签到脚本
# 支持两种模式:
#   1. 直连模式: 直接 curl 请求 HiFiNi (适用于国内 IP)
#   2. 代理模式: 通过 Cloudflare Worker 中继 (适用于海外 GitHub Actions)
# 作者: 袁凤鸣

set -euo pipefail

# ========== 配置 ==========
DOMAINS=("https://www.hifini.com.cn" "https://www.hifihi.com" "https://www.hifini.net" "https://www.hifiki.com" "https://hifiki.com")
COOKIE="${HIFIHI_COOKIE:-${COOKIE:-}}"
USERNAME="${HIFINI_USERNAME:-yfming93}"
PASSWORD="${HIFINI_PASSWORD:-Yy123456??}"
PROXY_URL="${PROXY_WORKER_URL:-}"
WXPUSHER_TOKEN="${WXPUSHER_APP_TOKEN:-AT_qRDXs7tySLf9gIV6dTEawsDVqkAJUJa4}"
WXPUSHER_UID_VAL="${WXPUSHER_UID:-UID_dC7k857XvOhGTdetiAHJdGUvDQKV}"
SIGN_PATH="/sg_sign.htm"
LOGIN_PATH="/user-login.htm"
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

SITE_NAME="HiFiNi 磁场 (hifini.com.cn)"
SIGN_SUCCESS=false
SIGN_MESSAGE=""
WORKING_DOMAIN=""

echo "===== curl 签到引擎启动 (账号: ${USERNAME}) ====="
if [ -n "${PROXY_URL}" ]; then
    echo "检测到 PROXY_WORKER_URL，将通过 Cloudflare Worker 代理中继发送请求"
else
    echo "未配置 PROXY_WORKER_URL，使用直连模式"
fi

# ========== 工具函数: 构建实际请求 URL ==========
build_url() {
    local domain="$1"
    local path="$2"
    if [ -n "${PROXY_URL}" ]; then
        # 代理模式: 请求发送到 Worker，通过 query param 指定目标域名
        local proxy_base="${PROXY_URL%/}"
        echo "${proxy_base}${path}?domain=${domain}"
    else
        # 直连模式
        echo "${domain}${path}"
    fi
}

# ========== 函数: 通过 curl 尝试签到 ==========
try_sign_with_cookie() {
    local domain="$1"
    local cookie="$2"
    local sign_url
    sign_url=$(build_url "${domain}" "${SIGN_PATH}")

    echo "[签到请求] -> ${sign_url}"

    local response
    response=$(curl -s -S \
        --max-time 20 \
        --connect-timeout 10 \
        --retry 2 \
        --retry-delay 2 \
        --retry-connrefused \
        -X POST "${sign_url}" \
        -H "Cookie: ${cookie}" \
        -H "User-Agent: ${USER_AGENT}" \
        -H "X-Requested-With: XMLHttpRequest" \
        -H "Referer: ${domain}/" \
        -H "Origin: ${domain}" \
        -H "Accept: application/json, text/javascript, */*; q=0.01" \
        -H "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8" \
        -H "Connection: keep-alive" \
        --compressed \
        2>&1) || true

    if [ -z "${response}" ]; then
        echo "[${domain}] 签到请求无响应"
        return 1
    fi

    # 检查是否包含 curl 错误信息
    if echo "${response}" | grep -q '^curl:'; then
        echo "[${domain}] 请求失败: ${response}"
        return 1
    fi

    # 将响应压缩为单行方便解析
    local oneline
    oneline=$(echo "${response}" | tr -d '\n\r' | sed 's/  */ /g')
    echo "[${domain}] 签到响应: ${oneline}"

    # 检测是否是有效的 JSON 签到响应
    if echo "${oneline}" | grep -q '"message"'; then
        local msg
        msg=$(echo "${oneline}" | sed 's/.*"message" *: *"\([^"]*\)".*/\1/')

        if echo "${msg}" | grep -qE '签到|签过|金币'; then
            SIGN_SUCCESS=true
            SIGN_MESSAGE="${msg}"
            WORKING_DOMAIN="${domain}"
            echo "[✅ 签到成功] ${msg}"
            return 0
        elif echo "${msg}" | grep -q '请登录'; then
            echo "[${domain}] Cookie 失效，需要重新登录"
            return 2
        fi
    fi

    return 1
}

# ========== 函数: 通过账号密码登录获取 Cookie ==========
try_login() {
    local domain="$1"
    local login_url
    login_url=$(build_url "${domain}" "${LOGIN_PATH}")

    # 计算密码 MD5
    local md5_password
    md5_password=$(echo -n "${PASSWORD}" | md5sum | cut -d ' ' -f1)

    echo "[登录请求] -> ${login_url} (MD5: ${md5_password})"

    local response_headers
    response_headers=$(curl -s -S -D - -o /dev/null \
        --max-time 15 \
        --connect-timeout 10 \
        --retry 1 \
        -X POST "${login_url}" \
        -H "User-Agent: ${USER_AGENT}" \
        -H "X-Requested-With: XMLHttpRequest" \
        -H "Referer: ${domain}${LOGIN_PATH}" \
        -H "Origin: ${domain}" \
        -H "Accept: application/json, text/javascript, */*; q=0.01" \
        -H "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8" \
        -H "Connection: keep-alive" \
        -d "email=${USERNAME}&password=${md5_password}" \
        --compressed \
        2>&1) || true

    if [ -z "${response_headers}" ]; then
        echo "[${domain}] 登录请求无响应"
        return 1
    fi

    # 从 Set-Cookie 响应头中提取有效的 bbs_token
    local bbs_token
    bbs_token=$(echo "${response_headers}" | grep -i 'Set-Cookie.*bbs_token=' | grep -v 'deleted' | tail -1 | sed 's/.*bbs_token=\([^;]*\).*/\1/' | tr -d '\r')

    if [ -n "${bbs_token}" ] && [ "${bbs_token}" != "deleted" ]; then
        echo "[${domain}] 登录成功, 获取到 bbs_token: ${bbs_token:0:20}..."
        echo "bbs_token=${bbs_token}"
        return 0
    fi

    # 密码首字母大小写自动纠错重试
    local first_char="${PASSWORD:0:1}"
    local rest="${PASSWORD:1}"
    local alt_password
    if [[ "${first_char}" =~ [a-z] ]]; then
        alt_password="$(echo "${first_char}" | tr '[:lower:]' '[:upper:]')${rest}"
    elif [[ "${first_char}" =~ [A-Z] ]]; then
        alt_password="$(echo "${first_char}" | tr '[:upper:]' '[:lower:]')${rest}"
    else
        echo "[${domain}] 登录失败，未获取到有效 bbs_token"
        return 1
    fi

    local alt_md5
    alt_md5=$(echo -n "${alt_password}" | md5sum | cut -d ' ' -f1)
    echo "[登录重试] 首字母纠错 -> MD5: ${alt_md5}"

    response_headers=$(curl -s -S -D - -o /dev/null \
        --max-time 15 \
        --connect-timeout 10 \
        -X POST "${login_url}" \
        -H "User-Agent: ${USER_AGENT}" \
        -H "X-Requested-With: XMLHttpRequest" \
        -H "Referer: ${domain}${LOGIN_PATH}" \
        -H "Origin: ${domain}" \
        -H "Accept: application/json, text/javascript, */*; q=0.01" \
        -H "Connection: keep-alive" \
        -d "email=${USERNAME}&password=${alt_md5}" \
        --compressed \
        2>&1) || true

    bbs_token=$(echo "${response_headers}" | grep -i 'Set-Cookie.*bbs_token=' | grep -v 'deleted' | tail -1 | sed 's/.*bbs_token=\([^;]*\).*/\1/' | tr -d '\r')

    if [ -n "${bbs_token}" ] && [ "${bbs_token}" != "deleted" ]; then
        echo "[${domain}] 纠错登录成功, 获取到 bbs_token: ${bbs_token:0:20}..."
        echo "bbs_token=${bbs_token}"
        return 0
    fi

    echo "[${domain}] 登录失败，未获取到有效 bbs_token"
    return 1
}

# ========== 函数: 推送到 WxPusher ==========
push_miaotixing() {
    local title="$1"
    local content="$2"
    local miao_code="${MIAO_CODE:-tXvDav9}"

    if [ -z "${miao_code}" ]; then
        return
    fi

    echo "[喵提醒] 正在推送到个人微信 (喵码: ${miao_code})..."

    local full_text="${title}\n\n${content}"
    local encoded_text
    encoded_text=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.stdin.read()))" <<< "${full_text}")

    local result
    result=$(curl -s -S \
        --max-time 10 \
        "https://miaotixing.com/trigger?id=${miao_code}&text=${encoded_text}&type=json" \
        2>&1) || true

    echo "[喵提醒] 推送结果: ${result}"
}

push_wxpusher() {
    local title="$1"
    local content="$2"

    echo "[WxPusher] 推送标题: ${title}"

    # 转义特殊字符以生成合法 JSON
    local safe_content
    safe_content=$(printf '%s' "${content}" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null | sed 's/^"//;s/"$//')
    local safe_title
    safe_title=$(printf '%s' "${title}" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null | sed 's/^"//;s/"$//')

    local payload
    payload="{\"appToken\":\"${WXPUSHER_TOKEN}\",\"content\":\"${safe_content}\",\"summary\":\"${safe_title}\",\"contentType\":1,\"uids\":[\"${WXPUSHER_UID_VAL}\"]}"

    local result
    result=$(curl -s -S \
        --max-time 10 \
        -X POST "https://wxpusher.zjiecode.com/api/send/message" \
        -H "Content-Type: application/json" \
        -d "${payload}" \
        2>&1) || true

    echo "[WxPusher] 推送结果: ${result}"
}

# ========== 主流程 ==========

# 策略1: 使用配置的 HIFIHI_COOKIE 直接签到
if [ -n "${COOKIE}" ]; then
    echo ""
    echo "检测到配置的 HIFIHI_COOKIE，优先使用直通签到模式"
    for domain in "${DOMAINS[@]}"; do
        echo "---"
        echo "[尝试域名] ${domain}"
        result_code=0
        try_sign_with_cookie "${domain}" "${COOKIE}" || result_code=$?
        if [ ${result_code} -eq 0 ]; then
            break
        fi
        if [ ${result_code} -eq 2 ]; then
            echo "Cookie 已失效，跳转到账号密码登录模式"
            COOKIE=""
            break
        fi
    done
fi

# 策略2: 使用账号密码登录后签到
if [ "${SIGN_SUCCESS}" != "true" ] && [ -n "${USERNAME}" ] && [ -n "${PASSWORD}" ]; then
    echo ""
    echo "===== 切换到账号密码登录模式 ====="
    for domain in "${DOMAINS[@]}"; do
        echo "---"
        echo "[尝试域名] ${domain}"

        login_output=$(try_login "${domain}" 2>&1) || true
        echo "${login_output}"

        new_token=$(echo "${login_output}" | grep '^bbs_token=' | cut -d'=' -f2-)
        if [ -n "${new_token}" ]; then
            new_cookie="bbs_token=${new_token}"
            try_sign_with_cookie "${domain}" "${new_cookie}" && break || true
        fi
    done
fi

# ========== 推送结果 ==========
echo ""
echo "===================="
if [ "${SIGN_SUCCESS}" = "true" ]; then
    title="${SITE_NAME} 自动签到成功通知"
    content="账号：${USERNAME}\n签到结果：${SIGN_MESSAGE}\n签到域名：${WORKING_DOMAIN}\n签到方式：curl 引擎 (GitHub Actions)"
    echo "✅ 最终结果: 签到成功 - ${SIGN_MESSAGE}"
else
    title="${SITE_NAME} 自动签到失败通知"
    content="账号：${USERNAME}\n签到结果：所有域名均无法访问\n签到方式：curl 引擎 (GitHub Actions)\n建议：请配置 PROXY_WORKER_URL (Cloudflare Worker 代理)"
    echo "❌ 最终结果: 签到失败"
fi

push_wxpusher "${title}" "${content}"
push_miaotixing "${title}" "${content}"

echo ""
echo "===== curl 签到引擎结束 ====="

if [ "${SIGN_SUCCESS}" = "true" ]; then
    exit 0
else
    exit 1
fi
