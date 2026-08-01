"""巴法云（Bemfa）同步模块的常量定义。"""

BEMFA_BROKER = "bemfa.com"
BEMFA_TLS_PORT = 9503
BEMFA_USE_TLS = True

BEMFA_API_BASE_URL = "https://apis.bemfa.com/vb/ha/v1"
BEMFA_DEVICE_LIST_URL = f"{BEMFA_API_BASE_URL}/device"
BEMFA_DEVICE_CONTROL_URL = f"{BEMFA_API_BASE_URL}/postMassage"
BEMFA_CREATE_TOPIC_URL = "https://pro.bemfa.com/vs/web/v2/createTopic"
BEMFA_CREATE_TOPIC_V1_URL = "https://pro.bemfa.com/v1/createTopic"
BEMFA_DELETE_TOPIC_URL = "https://pro.bemfa.com/v1/deleteTopic"
BEMFA_CHANGE_ROOM_URL = "http://apis.bemfa.com/vb/api/v1/changeTopicRoom"
BEMFA_CHANGE_GROUP_URL = "http://apis.bemfa.com/vb/api/v1/changeTopicGroup"
BEMFA_MODIFY_NAME_URL = "https://apis.bemfa.com/va/modifyName"
BEMFA_ALL_TOPIC_URL = "http://apis.bemfa.com/vb/api/v2/allTopic"
BEMFA_RETRY_INTERVAL_SECONDS = 300

# topic 命名空间：前缀 + 稳定哈希 + 3 位类型后缀。
# 前缀标识集成归属，任何删除/操作前必须校验，绝不触碰用户自建 topic；
# 哈希由 appliance_id 确定性生成，改名/改昵称不影响关联。
BEMFA_TOPIC_PREFIX = "xdu"
BEMFA_TOPIC_HASH_LENGTH = 12
