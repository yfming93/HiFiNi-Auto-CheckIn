package cloud.ohiyou.config;

import lombok.Getter;

@Getter
public class EnvConfig {

    private final static EnvConfig INSTANCE = new EnvConfig();
    private final String serverChan;
    private final String wxworkrobotkey;
    private final String wxWorkRobotMessageType;
    private final String dingTalkRobotKey;
    private final String cookie;
    private final String hifihiCookie;
    private final String tgChatId;
    private final String tgBotToken;
    private final String gotifyUrl;
    private final String gotifyAppToken;
    private final String wxPusherAppToken;
    private final String wxPusherUid;
    private final String username;
    private final String password;
    private final String domains;


    private EnvConfig() {
        cookie = System.getenv("COOKIE");
        hifihiCookie = System.getenv("HIFIHI_COOKIE");
        serverChan = System.getenv("SERVER_CHAN");
        wxworkrobotkey = System.getenv("WXWORK_WEBHOOK");
        wxWorkRobotMessageType = System.getenv().getOrDefault("WXWORK_MSG_TYPE", "markdown");
        dingTalkRobotKey = System.getenv("DINGTALK_WEBHOOK");
        tgBotToken = System.getenv("TG_BOT_TOKEN");
        tgChatId = System.getenv("TG_CHAT_ID");
        gotifyUrl = System.getenv("GOTIFY_URL");
        gotifyAppToken = System.getenv("GOTIFY_APP_TOKEN");

        String wpToken = System.getenv("WXPUSHER_APP_TOKEN");
        if (wpToken == null || wpToken.trim().isEmpty()) {
            wpToken = System.getenv("WXPUSHER_TOKEN");
        }
        if (wpToken == null || wpToken.trim().isEmpty()) {
            wpToken = "AT_qRDXs7tySLf9gIV6dTEawsDVqkAJUJa4";
        }
        wxPusherAppToken = wpToken;

        String wpUid = System.getenv("WXPUSHER_UID");
        if (wpUid == null || wpUid.trim().isEmpty()) {
            wpUid = "UID_dC7k857XvOhGTdetiAHJdGUvDQKV";
        }
        wxPusherUid = wpUid;

        String uName = System.getenv("HIFINI_USERNAME");
        if (uName == null || uName.trim().isEmpty()) {
            uName = System.getenv("USERNAME");
        }
        if (uName == null || uName.trim().isEmpty()) {
            uName = "yfming93";
        }
        username = uName;

        String pWord = System.getenv("HIFINI_PASSWORD");
        if (pWord == null || pWord.trim().isEmpty()) {
            pWord = System.getenv("PASSWORD");
        }
        if (pWord == null || pWord.trim().isEmpty()) {
            pWord = "yy123456??";
        }
        password = pWord;

        String dMains = System.getenv("HIFINI_DOMAINS");
        if (dMains == null || dMains.trim().isEmpty()) {
            dMains = "https://www.hifihi.com,https://www.hifini.net,https://www.hifini.com.cn";
        }
        domains = dMains;
    }

    public static EnvConfig get() {
        return INSTANCE;
    }


    public String getWXWorkMessageType() {
        return wxWorkRobotMessageType;
    }
}
