"""Android 技术标签体系（全局唯一口径）。

面试官侧和候选人侧必须共用同一套词表，否则按标签过滤会失效：
模型自由输出「桌面UI开发」，而库里存的是「Launcher3定制」，两边对不上。
"""

# 层级标签：用来做向量检索前的硬过滤，解决"都写 Android 但层级错配"
ANDROID_LEVELS = [
    "内核&底层",
    "通信&协议栈",
    "HAL & 硬件抽象层",
    "Framework框架层",
    "系统服务 & 定制ROM",
    "App & 应用层",
    "XTS/GTS测试",
    "车机专项",
]

# 技能标签：细粒度方向，用于同层级内部的语义匹配
ANDROID_TAGS = [
    # 内核 & 底层
    "Linux内核", "设备驱动", "电源管理", "Binder底层原理",
    # 通信 & 协议栈
    "蓝牙协议栈", "Wi-Fi协议", "RIL通信", "音视频协议",
    # HAL & 硬件抽象层
    "HIDL/AIDL底层设计", "HAL硬件抽象层开发",
    # Framework 框架层
    "AMS/WMS/PMS框架开发", "SELinux底层安全策略",
    # 系统服务 & 定制 ROM
    "SystemUI定制", "Launcher3定制", "Settings系统应用定制",
    "Provision开机向导", "Overlay资源替换", "GMS集成", "CTA认证",
    "系统应用预制", "JNI/NDK开发",
    # 性能
    "Perfetto性能调优", "ANR/卡顿问题定位", "高通QCM平台定制",
    # App 应用层
    "普通业务App开发", "Jetpack应用开发",
    # 测试
    "XTS/GTS/CTS兼容性测试",
    # 车机
    "车机HMI", "Flyme Auto车机定制",
]

# 面试轮次角色
INTERVIEW_ROLES = ["技术面", "主管/技术负责人面", "HR面"]

# 社招 / 校招默认流程（W6 之后搬进飞书多维表格做可配置）
SLOT_RULES = {
    "校招": [
        {"round": 1, "role": "技术面"},
        {"round": 2, "role": "HR面"},
    ],
    "社招": [
        {"round": 1, "role": "技术面"},
        {"round": 2, "role": "主管/技术负责人面"},
        {"round": 3, "role": "HR面"},
    ],
}
