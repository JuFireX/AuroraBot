# Aurora-Bot

**图 1. 总体系统层级图**

```mermaid
flowchart TB
    subgraph EXT["External World / External Systems"]
        QQ["QQ / OneBot v11"]
        CLOCK["Time / Scheduler"]
        USERDATA["Local Filesystem"]
    end

    subgraph BOOT["Boot And Runtime Entry"]
        NB["NoneBot Driver"]
        MAIN["src/main.py\nstartup_agent() / shutdown_agent()"]
        CFG["src/config.py\nConfig, env, paths"]
    end

    subgraph PLATFORM["Platform Layer: src/brain/platform"]
        DISC["app_discovery.py\nDiscover + instantiate apps"]
        APPCFG["app_config.py\nLoad apps/config.yaml"]
        HOST["application_host.py\nRegister apps, commands, event queue"]
        API["application_api.py\nPlatformAPI for apps"]
        MF["manifest.py\nManifest / CommandDecl"]
        LOOP["loop.py\nrun_app_loop()"]
        CONTRACT["contracts.py\nAppEvent / CommandSpec"]
        PROTO["application_protocol.py\nLifecycle protocol"]
    end

    subgraph APPS["Application Layer: apps/*"]
        QQAPP["apps/qq\nQQApplication"]
        ALARMAPP["apps/alarm\nAlarmApplication"]
        DIARYAPP["apps/diary\nDiaryApplication"]
        MANIFESTS["manifest.yaml files"]
        RUNTIMES["runtime.py files"]
    end

    subgraph CORE["Brain / Kernel Layer: src/brain/kernel"]
        AGENT["agent.py\nAgent"]
        KLOOP["kernel/loop.py\nrun_agent_loop()"]
        FUTURE["Future brain logic\nConsume AppEvent,\nDecide commands"]
    end

    NB --> MAIN
    CFG --> MAIN

    MAIN --> APPCFG
    MAIN --> DISC
    MAIN --> HOST
    MAIN --> LOOP

    APPCFG --> DISC
    DISC --> QQAPP
    DISC --> ALARMAPP
    DISC --> DIARYAPP

    QQAPP --> MANIFESTS
    QQAPP --> RUNTIMES
    ALARMAPP --> MANIFESTS
    ALARMAPP --> RUNTIMES
    DIARYAPP --> MANIFESTS
    DIARYAPP --> RUNTIMES

    HOST --> API
    HOST --> CONTRACT
    HOST --> MF
    HOST --> PROTO

    LOOP --> HOST
    HOST --> QQAPP
    HOST --> ALARMAPP
    HOST --> DIARYAPP

    QQ --> QQAPP
    CLOCK --> ALARMAPP
    USERDATA --> QQAPP
    USERDATA --> ALARMAPP
    USERDATA --> DIARYAPP

    QQAPP -->|"emit AppEvent(message.received)"| HOST
    ALARMAPP -->|"emit AppEvent(alarm_reminder / diary_prompt)"| HOST
    DIARYAPP -->|"emit AppEvent(diary.written)"| HOST

    HOST -.->|"future drain_events() -> brain consume"| FUTURE
    FUTURE -.->|"future invoke_command()"| HOST
    FUTURE --> AGENT
    AGENT --> KLOOP
```

**图 2. Platform 内部模块层级图**

```mermaid
flowchart LR
    subgraph CONFIG["Configuration"]
        C1["src/config.py\nPROJECT_ROOT / DATA_DIR / RUN_MODE / intervals"]
        C2["apps/config.yaml\nenabled + startup args"]
    end

    subgraph DISCOVERY["Discovery And Manifest"]
        D1["app_discovery.py\ndiscover_apps()"]
        D2["app_discovery.py\ninstantiate_app()"]
        D3["manifest.py\nManifest.load()"]
        D4["manifest.py\nCommandDecl -> JSON Schema"]
    end

    subgraph HOSTING["Hosting Runtime"]
        H1["application_host.py\n_apps"]
        H2["application_host.py\n_manifests"]
        H3["application_host.py\n_commands"]
        H4["application_host.py\n_events deque"]
        H5["register(app)"]
        H6["invoke_command()"]
        H7["tick()"]
        H8["stop_all()"]
    end

    subgraph APPAPI["App Facing API"]
        A1["application_api.py\nPlatformAPI"]
        A2["emit_event()"]
        A3["register_command()"]
        A4["data_dir"]
        A5["package / log()"]
    end

    subgraph CONTRACTS["Contracts"]
        P1["application_protocol.py\nmanifest_path / on_start / on_tick / on_stop"]
        P2["contracts.py\nAppEvent"]
        P3["contracts.py\nCommandSpec"]
    end

    subgraph SCHED["Scheduler"]
        S1["loop.py\nrun_app_loop()"]
    end

    C1 --> D1
    C2 --> D1
    C2 --> D2

    D1 --> D3
    D2 --> H5
    D3 --> D4
    D4 --> H3

    H5 --> H1
    H5 --> H2
    H5 --> H3
    H5 --> A1
    A1 --> A2
    A1 --> A3
    A1 --> A4
    A1 --> A5

    A2 --> H4
    A3 --> H3

    S1 --> H7
    H6 --> H3
    H7 --> H1
    H8 --> H1

    P1 --> H5
    P2 --> A2
    P3 --> A3
```

**图 3. App 生命周期与运行时序图**

```mermaid
flowchart TB
    NB["NoneBot"]
    MAIN["main.py"]
    CFG["app_config.py"]
    DISC["app_discovery.py"]
    HOST["ApplicationHost"]
    APP["App Runtime"]
    API["PlatformAPI"]
    LOOP["App Loop"]
    FS["App Data Dir"]

    NB -->|"startup"| MAIN
    MAIN -->|"load app config"| CFG
    CFG -->|"enabled apps"| MAIN

    MAIN -->|"create app instance"| DISC
    DISC -->|"app instance"| MAIN
    MAIN -->|"register app"| HOST

    HOST -->|"get manifest path"| APP
    HOST -->|"load manifest"| HOST
    HOST -->|"build command specs"| HOST
    HOST -->|"bind platform api"| APP
    HOST -->|"start app"| APP
    APP -->|"load local state"| FS
    HOST -->|"app registered"| MAIN

    MAIN -->|"start app loop"| LOOP
    LOOP -->|"tick"| HOST
    HOST -->|"run tick"| APP
    APP -->|"emit event"| API
    API -->|"append to event queue"| HOST

    HOST -->|"invoke command handler"| APP
    APP -->|"persist state"| FS
    APP -->|"result dict"| HOST

    NB -->|"shutdown"| MAIN
    MAIN -->|"stop all"| HOST
    HOST -->|"stop app"| APP
    APP -->|"save local state"| FS
```

**图 4. App 族谱与职责边界图**

```mermaid
flowchart TB
    subgraph PLATFORM["Platform"]
        HOST["ApplicationHost"]
        APIQQ["PlatformAPI(im.polaris.qq)"]
        APIALARM["PlatformAPI(im.polaris.alarm)"]
        APIDIARY["PlatformAPI(im.polaris.diary)"]
        QUEUE["AppEvent Queue"]
    end

    subgraph QQAPP["apps/qq"]
        QQM["manifest.yaml\nCommands:\n- send_qq_message\n- send_qq_private_message\n- at_user_in_group"]
        QQR["runtime.py\nQQApplication"]
        QQIN["Input:\nNoneBot on_message"]
        QQOUT["Output:\nOneBot send_group_msg / send_private_msg"]
        QQDATA["data/app_data/im_polaris_qq\n- qq_events.json\n- session_targets.json"]
    end

    subgraph ALARMAPP["apps/alarm"]
        AM["manifest.yaml\nCommands:\n- set_alarm"]
        AR["runtime.py\nAlarmApplication"]
        AIN["Input:\non_tick time check"]
        AOUT["Output:\nAppEvent alarm_reminder\nAppEvent diary_prompt"]
        ADATA["data/app_data/im_polaris_alarm\n- alarms.json\n- config.json"]
    end

    subgraph DIARYAPP["apps/diary"]
        DM["manifest.yaml\nCommands:\n- write_diary"]
        DR["runtime.py\nDiaryApplication"]
        DIN["Input:\nwrite_diary command"]
        DOUT["Output:\nAppEvent diary.written"]
        DDATA["data/app_data/im_polaris_diary\n- diaries.json"]
    end

    HOST --> APIQQ
    HOST --> APIALARM
    HOST --> APIDIARY

    APIQQ --> QQR
    APIALARM --> AR
    APIDIARY --> DR

    QQM --> QQR
    AM --> AR
    DM --> DR

    QQIN --> QQR
    QQR --> QQOUT
    QQR --> QQDATA
    QQR -->|"message.received"| QUEUE

    AIN --> AR
    AR --> ADATA
    AR -->|"alarm_reminder / diary_prompt"| QUEUE

    DIN --> DR
    DR --> DDATA
    DR -->|"diary.written"| QUEUE
```

**现状解读**

- `platform` 的职责已经比较完整: 发现应用, 读取 manifest, 注册命令, 注入 `PlatformAPI`, 调度 `on_tick`, 管理事件队列. 这一套主要落在 [application_host.py](file:///e:/Coding%20Projects/Bot-Polaris/AuroraBot/src/brain/platform/application_host.py#L17-L115), [app_discovery.py](file:///e:/Coding%20Projects/Bot-Polaris/AuroraBot/src/brain/platform/app_discovery.py#L17-L128), [manifest.py](file:///e:/Coding%20Projects/Bot-Polaris/AuroraBot/src/brain/platform/manifest.py#L10-L106).
- `app` 的职责边界也很明确: 只做环境感知, 原子命令执行, 本地状态持久化, 向上抛 `AppEvent`. 这和 [APP_DEVELOPMENT_GUIDE.md](file:///e:/Coding%20Projects/Bot-Polaris/AuroraBot/docs/APP_DEVELOPMENT_GUIDE.md#L5-L127) 完全一致.
- 当前实际启用的是 `diary` 和 `alarm`, `qq` 在 `apps/config.yaml` 里默认是关闭的, 依据 [config.yaml](file:///e:/Coding%20Projects/Bot-Polaris/AuroraBot/apps/config.yaml#L1-L10).
- `brain/kernel` 目前只有最小骨架, 还没有真正消费 `ApplicationHost.drain_events()` 并决策 `invoke_command()`, 所以如果你要画"完整闭环", 最严谨的表达就是"平台层已就绪, 核心认知闭环预留中", 依据 [main.py](file:///e:/Coding%20Projects/Bot-Polaris/AuroraBot/src/main.py#L37-L48), [kernel/loop.py](file:///e:/Coding%20Projects/Bot-Polaris/AuroraBot/src/brain/kernel/loop.py#L11-L24).

**建议**

- 如果你要放进文档首页, 建议用 "图 1 + 图 4", 最容易让人一眼看懂.
- 如果你要给开发者讲框架实现, 建议用 "图 2 + 图 3", 更适合说明注册流程和运行机制.
- 如果你愿意, 我下一步可以直接把这 4 张图整理成一个 `docs/platform_app_architecture.md` 文件, 并顺手补一版"现状图"和"目标图"双版本文档.
