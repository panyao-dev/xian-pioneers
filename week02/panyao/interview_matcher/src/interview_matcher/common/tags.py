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
    "系统应用",
    "App & 应用层",
    "XTS/GTS测试",
    "车机专项",
]

# 技能标签：细粒度方向，用于同层级内部的语义匹配（括号内为所属层级口径）
ANDROID_TAGS = [
    # 内核 & 底层
    "Linux内核", "设备驱动", "电源管理", "Binder底层原理",
    "内存管理/进程调度",
    # 通信 & 协议栈
    "蓝牙协议栈", "BLE低功耗蓝牙", "Wi-Fi协议", "RIL通信", "音视频协议",
    # HAL & 硬件抽象层
    "HIDL/AIDL底层设计", "HAL硬件抽象层开发", "串口/外设通信",
    # Framework 框架层
    "AMS/WMS/PMS框架开发", "SELinux底层安全策略",
    "四大组件框架", "Handler/消息机制", "事件分发机制",
    # 系统应用（SystemUI / 桌面 / Settings / 预装与定制）
    "SystemUI定制", "Launcher3定制", "Settings系统应用定制",
    "锁屏/Keyguard定制", "AOD灭屏显示", "通知栏定制",
    "系统时钟/日历应用", "系统相机应用", "系统联系人/拨号应用",
    "Provision开机向导", "Overlay资源替换", "GMS集成", "CTA认证",
    "系统应用预制", "JNI/NDK开发",
    "分屏/悬浮窗/折叠屏适配", "插件化/动态加载",
    # 性能优化
    "Perfetto性能调优", "ANR/卡顿问题定位", "冷启动优化", "内存泄漏治理",
    "包体积瘦身", "功耗优化", "高通QCM平台定制",
    # App 应用层
    "普通业务App开发", "Jetpack应用开发", "Jetpack Compose",
    "MVVM/MVI架构", "Dagger/Hilt依赖注入", "网络框架(OkHttp/Retrofit)",
    "自定义View/UI", "Flutter跨端",
    # WebView / 浏览器类系统应用
    "WebView/浏览器系统应用", "下载管理模块",
    # 测试
    "XTS/GTS/CTS兼容性测试", "自动化测试(UiAutomator/JUnit)",
    # 车机 / 行业终端
    "车机HMI", "Flyme Auto车机定制", "行业终端定制(记录仪/车台)",
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
