package cloud.ohiyou.config;

public class EnvConfig {

    private final static EnvConfig INSTANCE = new EnvConfig();
    private final String serverChan;
    private final String wxworkrobotkey;
    private final String wxWorkRobotMessageType;
    private final String dingTalkRobotKey;
    private final String cookie;
    private final String tgChatId;
    private final String tgBotToken;
    private final String gotifyUrl;
    private final String gotifyAppToken;


    private EnvConfig() {
        cookie = "bbs_sid=8o6rk2oagb88abk9g8jrgb4mf0; Hm_lvt_23819a3dd53d3be5031ca942c6cbaf25=1762436911; HMACCOUNT=25F9049004D86C0D; bbs_token=si0yaWEunuGlFnGo01sIMZw1Wzm1FJmGgp9KcDcvoaF_2B0im9srNmkwrH6NJC5Sa4GNZH4Qa88w4nI9q6NkzBRZb_2BbFs_3D; Hm_lpvt_23819a3dd53d3be5031ca942c6cbaf25=1762477668";
        serverChan = "SCT301782T5pl5qKqGpBVSIpceSCjBQt47";
        wxworkrobotkey = System.getenv("WXWORK_WEBHOOK");
        wxWorkRobotMessageType = System.getenv().getOrDefault("WXWORK_MSG_TYPE", "markdown");
        dingTalkRobotKey = System.getenv("DINGTALK_WEBHOOK");
        tgBotToken = System.getenv("TG_BOT_TOKEN");
        tgChatId = System.getenv("TG_CHAT_ID");
        gotifyUrl = System.getenv("GOTIFY_URL");
        gotifyAppToken = System.getenv("GOTIFY_APP_TOKEN");
    }

    public static EnvConfig get() {
        return INSTANCE;
    }


    public String getServerChan() {
        return serverChan;
    }

    public String getWxworkrobotkey() {
        return wxworkrobotkey;
    }

    public String getDingTalkRobotKey() {
        return dingTalkRobotKey;
    }

    public String getCookie() {
        return cookie;
    }

    public String getTgChatId() {
        return tgChatId;
    }

    public String getTgBotToken() {
        return tgBotToken;
    }

    public String getGotifyUrl() {
        return gotifyUrl;
    }

    public String getGotifyAppToken() {
        return gotifyAppToken;
    }

    public String getWXWorkMessageType() {
        return wxWorkRobotMessageType;
    }
}
