# Problem 网络拓扑

```mermaid
graph LR

    %% 节点定义
    N__[N  ]
    Problem[Problem]:::center
    Switch_A[Switch A]
    Switch_B[Switch B]

    %% 链路定义
    Problem -->|GigabitEthernet1/0/1 → TenGigabitEthernet0/1|] Switch_A
    Problem -->|GigabitEthernet1/0/1 → TenGigabitEthernet0/1|] Switch_B
    Problem -->|GigabitEthernet1/0/2 → -|] N__

    %% 样式定义
    classDef center fill:#e6f7ff,stroke:#1890ff,stroke-width:3px
    classDef suspect fill:#ffe6e6,stroke:#ff4d4f,stroke-width:2px
    classDef trunk stroke:#52c41a,stroke-width:3px
```