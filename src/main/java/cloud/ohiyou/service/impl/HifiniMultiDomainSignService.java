/// @Author: 袁凤鸣
/// @Date: 2026-08-05
/// @LastEditors: 袁凤鸣
/// @LastEditTime: 2026-08-05 15:15:00
/// @FilePath: src/main/java/cloud/ohiyou/service/impl/HifiniMultiDomainSignService.java
/// @Description: 支持账号密码模拟登录及多域名切用容错的 HiFiNi 签到服务

package cloud.ohiyou.service.impl;

import cloud.ohiyou.constant.HifiniConstants;
import cloud.ohiyou.service.ISignService;
import cloud.ohiyou.utils.OkHttpUtils;
import cloud.ohiyou.utils.ResponseUtils;
import cloud.ohiyou.vo.SignResultVO;
import cloud.ohiyou.vo.UserInfoVO;
import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import okhttp3.*;
import org.apache.commons.codec.digest.DigestUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * HiFiNi 通用多域名切用自动签到服务实现
 *
 * @author 袁凤鸣
 */
public class HifiniMultiDomainSignService implements ISignService {

    private static final Logger logger = LoggerFactory.getLogger(HifiniMultiDomainSignService.class);
    private static final OkHttpClient client = OkHttpUtils.getClient();
    private final Random random = new Random();

    private final List<String> domainList;
    private final String username;
    private final String password;
    private String workingDomain;
    private String activeCookie;

    public HifiniMultiDomainSignService(String domains, String username, String password) {
        if (domains != null && !domains.trim().isEmpty()) {
            this.domainList = Arrays.asList(domains.split(","));
        } else {
            this.domainList = HifiniConstants.COMMON_DOMAINS;
        }
        this.username = username;
        this.password = password;
    }

    /**
     * 在可用域名列表中轮询登录并执行签到
     *
     * @param initialCookie 初始传入的 Cookie（如果有）
     * @return 签到结果
     */
    @Override
    public SignResultVO signIn(String initialCookie) {
        this.activeCookie = initialCookie;

        for (String domain : domainList) {
            String baseUrl = domain.trim();
            if (baseUrl.endsWith("/")) {
                baseUrl = baseUrl.substring(0, baseUrl.length() - 1);
            }
            logger.info("尝试域名站点: {}", baseUrl);

            try {
                // 1. 检验已有 Cookie 或通过账号密码登录获取新 Cookie
                String cookieToUse = activeCookie;
                if (!isCookieValid(baseUrl, cookieToUse)) {
                    logger.info("域名 [{}] 的当前 Cookie 无效或不存在，尝试使用账号密码 [{}] 登录...", baseUrl, username);
                    cookieToUse = loginAndGetCookie(baseUrl, username, password);
                }

                if (cookieToUse == null || cookieToUse.trim().isEmpty()) {
                    logger.warn("域名 [{}] 登录未获取到有效 Cookie，尝试切换下一个备用域名", baseUrl);
                    continue;
                }

                // 2. 尝试该域名的签到
                SignResultVO result = doSignIn(baseUrl, cookieToUse);
                if (result != null) {
                    this.workingDomain = baseUrl;
                    this.activeCookie = cookieToUse;
                    logger.info("域名 [{}] 签到完成, 响应: {}", baseUrl, result.getMess());
                    return result;
                }

            } catch (Exception e) {
                logger.error("在域名站点 [{}] 上执行签到发生错误: {}, 正在自动切用备用域名...", baseUrl, e.getMessage());
            }
        }

        return new SignResultVO(2, "所有备用域名尝试签到均失败，请检查网络或账号密码");
    }

    /**
     * 实际执行指定域名的签到 POST 请求
     */
    private SignResultVO doSignIn(String baseUrl, String cookie) throws Exception {
        String userAgent = getRandomUserAgent();
        String signUrl = baseUrl + HifiniConstants.SIGN_PATH;

        RequestBody emptyBody = RequestBody.create("",
                MediaType.get("application/x-www-form-urlencoded; charset=UTF-8"));

        Request request = new Request.Builder()
                .url(signUrl)
                .post(emptyBody)
                .addHeader("Cookie", cookie)
                .addHeader("User-Agent", userAgent)
                .addHeader("X-Requested-With", "XMLHttpRequest")
                .addHeader("Referer", signUrl)
                .addHeader("Accept", "application/json, text/javascript, */*; q=0.01")
                .addHeader("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
                .build();

        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                logger.warn("请求 [{}] 状态码: {}", signUrl, response.code());
                return new SignResultVO(2, "HTTP状态码：" + response.code());
            }

            String responseBody = ResponseUtils.readResponse(response);
            logger.info("站点 [{}] 签到响应内容: {}", baseUrl, responseBody);
            try {
                return JSON.parseObject(responseBody, SignResultVO.class);
            } catch (Exception parseException) {
                SignResultVO fallbackVO = new SignResultVO();
                fallbackVO.setCode(0);
                fallbackVO.setMess(responseBody);
                return fallbackVO;
            }
        }
    }

    /**
     * 账号密码模拟登录并获取登录态 Cookie
     */
    public String loginAndGetCookie(String baseUrl, String username, String password) {
        if (username == null || password == null || username.trim().isEmpty() || password.trim().isEmpty()) {
            return null;
        }

        String loginUrl = baseUrl + HifiniConstants.LOGIN_PATH;
        String userAgent = getRandomUserAgent();
        String md5Password = DigestUtils.md5Hex(password);

        // 先尝试 MD5 密码提交
        String cookieResult = tryLoginPost(loginUrl, username, md5Password, userAgent);
        if (cookieResult != null && !cookieResult.isEmpty()) {
            return cookieResult;
        }

        // 若 MD5 失败，再尝试明文密码提交
        return tryLoginPost(loginUrl, username, password, userAgent);
    }

    private String tryLoginPost(String loginUrl, String username, String passValue, String userAgent) {
        try {
            FormBody formBody = new FormBody.Builder()
                    .add("email", username)
                    .add("password", passValue)
                    .build();

            Request request = new Request.Builder()
                    .url(loginUrl)
                    .post(formBody)
                    .addHeader("User-Agent", userAgent)
                    .addHeader("X-Requested-With", "XMLHttpRequest")
                    .addHeader("Referer", loginUrl)
                    .addHeader("Accept", "application/json, text/javascript, */*; q=0.01")
                    .build();

            try (Response response = client.newCall(request).execute()) {
                if (!response.isSuccessful()) {
                    return null;
                }

                List<String> setCookies = response.headers("Set-Cookie");
                if (setCookies == null || setCookies.isEmpty()) {
                    return null;
                }

                List<String> cookieParts = new ArrayList<>();
                for (String setCookie : setCookies) {
                    String[] parts = setCookie.split(";");
                    if (parts.length > 0) {
                        cookieParts.add(parts[0].trim());
                    }
                }

                String cookieStr = String.join("; ", cookieParts);
                logger.info("模拟登录请求成功，获取 Cookie: {}", cookieStr);
                return cookieStr;
            }
        } catch (Exception e) {
            logger.debug("登录请求 [{}] 抛出异常: {}", loginUrl, e.getMessage());
            return null;
        }
    }

    /**
     * 校验当前 Cookie 是否在对应域名有效
     */
    private boolean isCookieValid(String baseUrl, String cookie) {
        if (cookie == null || cookie.trim().isEmpty()) {
            return false;
        }
        try {
            UserInfoVO info = getUserInfoFromUrl(baseUrl, cookie);
            return info != null && info.getUserName() != null && !info.getUserName().trim().isEmpty();
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    public UserInfoVO getUserInfo(String cookie) {
        String targetDomain = (workingDomain != null) ? workingDomain : domainList.get(0);
        String cookieToUse = (activeCookie != null) ? activeCookie : cookie;
        try {
            return getUserInfoFromUrl(targetDomain, cookieToUse);
        } catch (Exception e) {
            logger.error("获取用户信息异常: {}", e.getMessage());
            return new UserInfoVO();
        }
    }

    private UserInfoVO getUserInfoFromUrl(String baseUrl, String cookie) throws Exception {
        String url = baseUrl + HifiniConstants.USER_INFO_PATH;
        String userAgent = getRandomUserAgent();

        Request request = new Request.Builder()
                .url(url)
                .get()
                .addHeader("Cookie", cookie)
                .addHeader("User-Agent", userAgent)
                .addHeader("Referer", baseUrl + "/")
                .addHeader("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
                .build();

        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new RuntimeException("获取用户信息 HTTP 状态码: " + response.code());
            }
            String pageContent = ResponseUtils.readResponse(response);
            return parseUserInfo(pageContent);
        }
    }

    @Override
    public Integer getSignStreak(String cookie) {
        String targetDomain = (workingDomain != null) ? workingDomain : domainList.get(0);
        String cookieToUse = (activeCookie != null) ? activeCookie : cookie;
        try {
            String url = targetDomain + HifiniConstants.SIGN_PATH;
            String userAgent = getRandomUserAgent();

            Request request = new Request.Builder()
                    .url(url)
                    .get()
                    .addHeader("Cookie", cookieToUse)
                    .addHeader("User-Agent", userAgent)
                    .addHeader("Referer", targetDomain + "/")
                    .addHeader("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
                    .build();

            try (Response response = client.newCall(request).execute()) {
                if (!response.isSuccessful()) {
                    return null;
                }
                String pageContent = ResponseUtils.readResponse(response);
                return parseSignStreak(pageContent);
            }
        } catch (Exception e) {
            logger.error("获取连续签到天数异常: {}", e.getMessage());
            return null;
        }
    }

    private UserInfoVO parseUserInfo(String pageContent) {
        UserInfoVO userInfo = new UserInfoVO();
        try {
            Pattern namePattern = Pattern.compile(HifiniConstants.REGEX_USERNAME);
            Matcher nameMatcher = namePattern.matcher(pageContent);
            if (nameMatcher.find()) {
                userInfo.setUserName(nameMatcher.group(1).trim());
            }

            Pattern coinPattern = Pattern.compile(HifiniConstants.REGEX_COINS);
            Matcher coinMatcher = coinPattern.matcher(pageContent);
            if (coinMatcher.find()) {
                userInfo.setCoins(Integer.parseInt(coinMatcher.group(1)));
            }
        } catch (Exception e) {
            logger.error("解析用户信息出错: {}", e.getMessage());
        }
        return userInfo;
    }

    private Integer parseSignStreak(String signPageContent) {
        try {
            Pattern streakPattern = Pattern.compile(HifiniConstants.REGEX_SIGN_STREAK);
            Matcher streakMatcher = streakPattern.matcher(signPageContent);
            if (streakMatcher.find()) {
                return Integer.parseInt(streakMatcher.group(1));
            } else {
                Pattern fallbackPattern = Pattern.compile(HifiniConstants.REGEX_SIGN_STREAK_FALLBACK);
                Matcher fallbackMatcher = fallbackPattern.matcher(signPageContent);
                if (fallbackMatcher.find()) {
                    return Integer.parseInt(fallbackMatcher.group(1));
                }
            }
        } catch (Exception e) {
            logger.error("解析连续签到天数出错: {}", e.getMessage());
        }
        return null;
    }

    private String getRandomUserAgent() {
        return HifiniConstants.USER_AGENTS.get(random.nextInt(HifiniConstants.USER_AGENTS.size()));
    }
}
