/// @Author: 袁凤鸣
/// @Date: 2026-08-05
/// @LastEditors: 袁凤鸣
/// @LastEditTime: 2026-08-05 15:15:00
/// @FilePath: src/main/java/cloud/ohiyou/service/push/impl/WxPusherPushStrategy.java
/// @Description: WxPusher 消息推送策略实现

package cloud.ohiyou.service.push.impl;

import cloud.ohiyou.config.EnvConfig;
import cloud.ohiyou.constant.PushPlatform;
import cloud.ohiyou.service.push.AbstractPushStrategy;
import com.alibaba.fastjson.JSONObject;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import java.util.Collections;

/**
 * WxPusher 消息推送策略
 *
 * @author 袁凤鸣
 */
public class WxPusherPushStrategy extends AbstractPushStrategy {

    private static final String WX_PUSHER_URL = "https://wxpusher.zjiecode.com/api/send/message";
    private final String appToken;
    private final String uid;

    public WxPusherPushStrategy(OkHttpClient client) {
        super(client, PushPlatform.WX_PUSHER);
        EnvConfig config = EnvConfig.get();
        this.appToken = config.getWxPusherAppToken();
        this.uid = config.getWxPusherUid();
    }

    public WxPusherPushStrategy(OkHttpClient client, String appToken, String uid) {
        super(client, PushPlatform.WX_PUSHER);
        this.appToken = appToken;
        this.uid = uid;
    }

    @Override
    protected void doPush(String title, String message) throws Exception {
        JSONObject bodyJson = new JSONObject();
        bodyJson.put("appToken", appToken);
        bodyJson.put("content", message);
        bodyJson.put("summary", title);
        bodyJson.put("contentType", 1);
        bodyJson.put("uids", Collections.singletonList(uid));

        RequestBody body = RequestBody.create(
                bodyJson.toJSONString(),
                MediaType.parse("application/json; charset=utf-8")
        );

        Request request = new Request.Builder()
                .url(WX_PUSHER_URL)
                .post(body)
                .addHeader("Content-Type", "application/json")
                .build();

        try (Response response = executeRequest(request)) {
            if (!response.isSuccessful()) {
                throw new RuntimeException("WxPusher 推送失败，HTTP 状态码: " + response.code());
            }
        }
    }
}
