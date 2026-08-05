package cloud.ohiyou;

import cloud.ohiyou.config.EnvConfig;
import cloud.ohiyou.executor.SignTaskExecutor;
import cloud.ohiyou.factory.PushStrategyFactory;
import cloud.ohiyou.handler.CookieHandler;
import cloud.ohiyou.handler.ResultPublisher;
import cloud.ohiyou.service.ISignService;
import cloud.ohiyou.service.impl.HifihiSignService;
import cloud.ohiyou.service.impl.HifitiSignService;
import cloud.ohiyou.service.push.IMessagePushStrategy;
import cloud.ohiyou.utils.OkHttpUtils;
import cloud.ohiyou.vo.CookieSignResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;

/**
 * HiFiNi 自动签到应用入口
 * 支持 HiFiTi 和 HiFiHi 两个站点的签到
 *
 * @author ohiyou
 */
public class HifiniApplication {

    private static final Logger logger = LoggerFactory.getLogger(HifiniApplication.class);

    public static void main(String[] args) {
        logger.info("自动签到任务开始");

        List<CookieSignResult> allResults = new ArrayList<>();
        CookieHandler cookieHandler = new CookieHandler();
        SignTaskExecutor executor = new SignTaskExecutor();

        try {
            EnvConfig config = EnvConfig.get();

            // 可选的凌晨随机等待（防止集中整点打卡触发风控）
            applyRandomDelay();

            // 1. 通用多域名（hifihi.com / hifini.net / hifini.com.cn）切用自动签到
            if (config.getUsername() != null && !config.getUsername().trim().isEmpty()) {
                logger.info("===== 通用站点多域名自动登录签到开始 (账号: {}) =====", config.getUsername());
                ISignService multiDomainService = new cloud.ohiyou.service.impl.HifiniMultiDomainSignService(
                        config.getDomains(), config.getUsername(), config.getPassword());
                
                String initialCookie = config.getHifihiCookie();
                String cookiesToPass = (initialCookie != null && !initialCookie.trim().isEmpty()) ? initialCookie : "AUTO_LOGIN";
                List<CookieSignResult> multiResults = executeSignIn(
                        cookiesToPass, multiDomainService, cookieHandler, executor, "HiFiNi");
                allResults.addAll(multiResults);
            }

            // 2. 兼容老的 HiFiTi 站点独立 Cookie 签到（若有配置）
            String hifitiCookies = config.getCookie();
            if (hifitiCookies != null && !hifitiCookies.trim().isEmpty()) {
                logger.info("===== HiFiTi 站点 Cookie 签到开始 =====");
                List<CookieSignResult> hifitiResults = executeSignIn(
                        hifitiCookies, new HifitiSignService(), cookieHandler, executor, "HiFiTi");
                allResults.addAll(hifitiResults);
            }

            // 检查是否有任何签到任务
            if (allResults.isEmpty()) {
                logger.warn("未配置任何账号或 Cookie，无签到任务执行");
                return;
            }

            // 发布汇总结果（含 WxPusher 及其他配置平台）
            List<IMessagePushStrategy> strategies = PushStrategyFactory.createStrategies();
            ResultPublisher publisher = new ResultPublisher(strategies);
            publisher.publish(allResults);

        } catch (Exception e) {
            logger.error("签到任务执行失败: {}", e.getMessage(), e);
        } finally {
            executor.shutdown();
            OkHttpUtils.shutdown();
            logger.info("自动签到任务完成");
        }
    }

    /**
     * 凌晨随机打卡延迟，模拟真人行为
     */
    private static void applyRandomDelay() {
        String delayEnv = System.getenv("ENABLE_RANDOM_DELAY");
        if ("true".equalsIgnoreCase(delayEnv) || "1".equals(delayEnv)) {
            try {
                int delayMinutes = new java.util.Random().nextInt(15) + 1;
                logger.info("已开启凌晨随机延时，随机休眠 {} 分钟后开始签到...", delayMinutes);
                Thread.sleep(delayMinutes * 60 * 1000L);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }
    }

    /**
     * 执行指定站点的签到任务
     *
     * @param cookies       cookie字符串
     * @param signService   签到服务
     * @param cookieHandler cookie处理器
     * @param executor      任务执行器
     * @param siteName      站点名称
     * @return 签到结果列表
     */
    private static List<CookieSignResult> executeSignIn(
            String cookies,
            ISignService signService,
            CookieHandler cookieHandler,
            SignTaskExecutor executor,
            String siteName) {

        String[] cookieArray = cookieHandler.splitCookies(cookies);
        logger.info("{}: 检测到 {} 个cookie，开始签到", siteName, cookieArray.length);

        List<CookieSignResult> results = executor.executeSignTasks(cookieArray, signService, cookieHandler);

        // 为结果添加站点标识
        for (CookieSignResult result : results) {
            if (result.getSignResult() != null) {
                String originalUserName = result.getSignResult().getUserName();
                result.getSignResult().setUserName("[" + siteName + "] " +
                        (originalUserName != null ? originalUserName : "未知用户"));
            }
        }

        logger.info("{}: 签到任务完成，共 {} 个结果", siteName, results.size());
        return results;
    }
}
