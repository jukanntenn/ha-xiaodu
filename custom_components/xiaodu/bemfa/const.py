"""巴法云（Bemfa）同步模块的常量定义。"""

BEMFA_BROKER = "bemfa.com"
BEMFA_TLS_PORT = 9503

BEMFA_API_BASE_URL = "https://apis.bemfa.com/vb/ha/v1"
BEMFA_DEVICE_LIST_URL = f"{BEMFA_API_BASE_URL}/device"
BEMFA_DEVICE_CONTROL_URL = f"{BEMFA_API_BASE_URL}/postMassage"
BEMFA_CREATE_TOPIC_URL = "https://pro.bemfa.com/vs/web/v2/createTopic"
BEMFA_CHANGE_ROOM_URL = "http://apis.bemfa.com/vb/api/v1/changeTopicRoom"
BEMFA_CHANGE_GROUP_URL = "http://apis.bemfa.com/vb/api/v1/changeTopicGroup"
