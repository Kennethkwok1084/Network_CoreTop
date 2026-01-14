# 实时日志功能 - 功能说明

## 🎯 功能概览

已在Web管理系统中添加**实时采集日志**功能，让用户可以在浏览器中实时查看SSH采集的详细过程。

## ✨ 主要特性

### 1. 实时日志推送
- **技术方案**：基于 Server-Sent Events (SSE) 的实时推送
- **更新频率**：毫秒级实时更新，无需刷新页面
- **连接管理**：自动心跳保持连接，断线自动提示

### 2. 详细日志分类

日志按类型分为6种颜色编码：

| 类型 | 图标 | 颜色 | 说明 |
|------|------|------|------|
| **连接** | ✓ | 青色 | SSH连接状态（成功/失败）|
| **信息** | ℹ | 浅蓝 | 任务开始、设备信息 |
| **成功** | ✓ | 绿色 | 采集完成、文件保存 |
| **错误** | ✗ | 红色 | 认证失败、网络错误 |
| **命令** | ► | 黄色 | 执行的CLI命令（带进度）|
| **输出** | ◄ | 橙色 | 设备返回的命令输出预览 |

### 3. 美观的终端界面
- **深色主题**：VS Code风格的黑色背景
- **等宽字体**：Consolas/Monaco专业编程字体
- **自动滚动**：新日志自动滚动到可见区域
- **时间戳**：每条日志带精确时间戳

## 🚀 使用方法

### 步骤 1：创建采集任务
1. 进入 [设备管理页面](http://127.0.0.1:5000/manage/devices)
2. 点击设备右侧的"采集"按钮
3. 系统自动创建采集任务并跳转到任务管理页面

### 步骤 2：执行任务并查看日志
1. 在 [任务管理页面](http://127.0.0.1:5000/manage/tasks)
2. 找到状态为"待执行"的任务
3. 点击"执行"按钮开始采集
4. 任务状态变为"执行中"后，点击"📡 查看日志"按钮
5. 弹出实时日志窗口，自动显示采集过程

### 步骤 3：监控采集进度
- 观察日志中的命令执行进度（如 `[3/9] 执行命令: display lldp neighbor`）
- 查看每条命令的输出预览
- 等待"[完成]"消息出现表示采集成功

## 📊 日志示例

```
[2026-01-14 10:22:05] ℹ [开始] 任务 #1 开始执行
[2026-01-14 10:22:05] ℹ [设备] TestSwitch (192.168.1.1)
[2026-01-14 10:22:06] ✓ [连接] 正在连接到 192.168.1.1:22...
[2026-01-14 10:22:07] ✓ [连接] SSH 连接成功 (用户: admin)
[2026-01-14 10:22:07] ► [1/9] 执行命令: screen-length 0 temporary
[2026-01-14 10:22:08] ◄ [输出] <TestSwitch>screen-length 0 temporary...
[2026-01-14 10:22:08] ► [2/9] 执行命令: display version
[2026-01-14 10:22:09] ◄ [输出] Huawei Versatile Routing Platform Software VRP (R) software, Version 8.180...
[2026-01-14 10:22:09] ► [3/9] 执行命令: display lldp neighbor brief
...
[2026-01-14 10:22:35] ✓ [采集] 采集完成，共收集 45230 字节数据
[2026-01-14 10:22:35] ✓ [完成] 日志已保存到: TestSwitch_20260114_102235.log
[2026-01-14 10:22:35] ✓ [成功] 任务执行成功，共执行 9 条命令
```

## 🔧 技术实现

### 后端架构

#### 1. 日志广播器 (`LogBroadcaster`)
```python
class LogBroadcaster:
    """日志广播器 - 管理多个客户端的日志订阅"""
    def __init__(self):
        self.queues = {}  # {task_id: [queue1, queue2, ...]}
    
    def broadcast(self, task_id, log_type, message):
        """向所有订阅者推送日志"""
        log_data = {
            'type': log_type,
            'message': message,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        # 推送到所有监听该任务的队列
```

#### 2. SSE 日志流端点
```python
@app.route('/manage/tasks/<int:task_id>/logs')
@login_required
def task_logs_stream(task_id):
    """Server-Sent Events 日志流"""
    def generate():
        q = log_broadcaster.add_listener(task_id)
        while True:
            log_data = q.get(timeout=30)
            yield f"data: {json.dumps(log_data)}\n\n"
    
    return Response(stream_with_context(generate()), 
                    mimetype='text/event-stream')
```

#### 3. 采集器日志回调
```python
def collect_device_info(self, device_config, log_callback=None):
    """采集设备信息，支持实时日志推送"""
    if log_callback:
        log_callback('info', '[连接] 正在连接...')
    
    # SSH连接
    ssh.connect(...)
    
    if log_callback:
        log_callback('success', '[连接] SSH 连接成功')
    
    # 执行命令
    for idx, cmd in enumerate(commands, 1):
        if log_callback:
            log_callback('command', f'[{idx}/{len(commands)}] 执行命令: {cmd}')
        
        # 执行并读取输出
        output = execute_command(cmd)
        
        if log_callback:
            log_callback('output', f'[输出] {output[:200]}...')
```

### 前端实现

#### JavaScript EventSource API
```javascript
function showLogs(taskId) {
    // 建立 SSE 连接
    eventSource = new EventSource('/manage/tasks/' + taskId + '/logs');
    
    // 接收日志消息
    eventSource.onmessage = function(event) {
        const log = JSON.parse(event.data);
        
        // 根据日志类型设置颜色
        let color = getColorByType(log.type);
        
        // 追加到日志容器并自动滚动
        appendLog(log.timestamp, log.message, color);
        scrollToBottom();
    };
    
    // 处理连接错误
    eventSource.onerror = function() {
        appendLog('[系统] 连接已断开');
        eventSource.close();
    };
}
```

## 🎨 界面展示

### 任务管理页面
```
┌─────────────────────────────────────────────────────────────┐
│ 📋 采集任务管理                                              │
├─────────────────────────────────────────────────────────────┤
│ ID │ 设备名称 │ 设备IP      │ 状态    │ 操作              │
├────┼─────────┼────────────┼─────────┼───────────────────┤
│ #1 │ Core-SW │ 192.168.1.1│ 执行中   │ 📡 查看日志        │
│ #2 │ Access1 │ 192.168.1.2│ 待执行   │ [执行]             │
│ #3 │ Access2 │ 192.168.1.3│ 成功     │ 📄 查看日志文件    │
└─────────────────────────────────────────────────────────────┘
```

### 实时日志弹窗
```
┌──────────────────────────────────────────────────────────────┐
│ 📡 实时采集日志                                      [✕]     │
├──────────────────────────────────────────────────────────────┤
│ █████████████████ 日志内容 █████████████████████████████     │
│ [10:22:05] ✓ 已连接到日志流                                 │
│ [10:22:05] ℹ [开始] 任务 #1 开始执行                        │
│ [10:22:05] ℹ [设备] Core-SW (192.168.1.1)                   │
│ [10:22:06] ✓ [连接] SSH 连接成功 (用户: admin)              │
│ [10:22:07] ► [1/9] 执行命令: display version                │
│ [10:22:08] ◄ [输出] Huawei Versatile Routing Platform...    │
│ [10:22:09] ► [2/9] 执行命令: display lldp neighbor brief    │
│ ...                                                          │
│ [10:22:35] ✓ [完成] 日志已保存到: Core_20260114.log         │
│ [10:22:35] ✓ [成功] 任务执行成功，共执行 9 条命令            │
│                                                              │
│ ▼ (自动滚动到底部)                                           │
└──────────────────────────────────────────────────────────────┘
```

## 🔒 安全特性

1. **登录验证**：日志流端点需要用户登录才能访问
2. **任务隔离**：每个任务独立队列，互不干扰
3. **队列限制**：单个队列最多100条消息，防止内存溢出
4. **自动清理**：连接断开后自动清理监听器
5. **超时机制**：30秒无消息自动发送心跳

## 📝 代码修改清单

### 修改的文件 (3个)

1. **topo/web/app_v2.py** (+55行)
   - 添加 `LogBroadcaster` 类（日志广播管理）
   - 添加 `task_logs_stream()` 路由（SSE日志推送）
   - 修改 `execute_task()` 为异步执行（避免阻塞）
   - 导入 `queue`, `threading`, `Response`, `stream_with_context`

2. **topo/management/task_scheduler.py** (+15行)
   - `execute_task()` 添加 `log_callback` 参数
   - 在关键步骤调用 `log_callback()` 推送日志
   - 记录：任务开始、设备信息、采集完成、错误信息

3. **topo/management/collector.py** (+30行)
   - `collect_device_info()` 添加 `log_callback` 参数
   - 记录：SSH连接、命令执行进度、输出预览、错误详情
   - 详细记录每条命令的执行（带进度 1/9, 2/9...）

4. **topo/web/templates/manage_tasks.html** (+90行)
   - 添加"📡 查看日志"按钮（运行中任务）
   - 添加日志弹窗组件（模态框）
   - 添加 JavaScript SSE 客户端代码
   - 实现日志颜色编码和自动滚动

## 🎯 使用场景

### 1. 故障排查
- 实时查看SSH连接是否成功
- 确认设备类型和命令集是否匹配
- 查看具体哪个命令执行失败

### 2. 进度监控
- 了解当前执行到第几条命令
- 预估剩余采集时间
- 确认采集是否卡住

### 3. 输出验证
- 查看设备返回的数据格式
- 确认命令输出是否正常
- 验证设备响应速度

### 4. 学习演示
- 教学时展示SSH自动化流程
- 演示不同设备类型的命令差异
- 展示网络设备采集过程

## 🚦 状态说明

### 任务状态流转
```
待执行 (pending)
    ↓ [点击执行]
执行中 (running) ← 此时可查看实时日志
    ↓ [采集完成]
成功 (success) / 失败 (failed)
```

### 日志类型优先级
```
error (错误)     → 优先级最高，红色醒目显示
command (命令)   → 关键操作，黄色高亮
success (成功)   → 正向反馈，绿色
info (信息)      → 普通提示，浅蓝
output (输出)    → 详细数据，橙色
connected (连接) → 系统消息，青色
```

## 💡 提示和技巧

### 1. 最佳实践
- ✅ 执行长时间任务前先查看日志，确保连接正常
- ✅ 遇到采集失败时，通过日志定位具体错误命令
- ✅ 使用日志输出验证设备配置是否正确

### 2. 性能建议
- 单个任务不建议超过20条命令（避免日志过长）
- 同时执行的任务不超过5个（避免服务器压力）
- 日志窗口保持打开时会持续占用一个HTTP连接

### 3. 故障处理
- **日志显示"连接已断开"**：任务已完成或失败，关闭弹窗即可
- **日志长时间无更新**：可能设备响应慢，等待或检查网络
- **日志颜色全是错误红色**：设备配置有误，检查IP/端口/凭证

## 🔄 后续优化计划

### Phase 1 (已完成 ✅)
- [x] SSE 实时日志推送
- [x] 日志类型颜色编码
- [x] 前端弹窗展示
- [x] 自动滚动和时间戳

### Phase 2 (计划中)
- [ ] 日志下载功能（导出为TXT）
- [ ] 日志搜索和过滤（按类型筛选）
- [ ] 日志统计（命令耗时分析）
- [ ] WebSocket 替代 SSE（支持双向通信）

### Phase 3 (长期规划)
- [ ] 日志回放功能（慢放演示采集过程）
- [ ] 多任务并行查看（分屏显示）
- [ ] 日志持久化到数据库
- [ ] 日志分析和告警

## 📞 技术支持

遇到问题？检查：
1. 浏览器控制台是否有错误
2. 任务状态是否为"执行中"
3. 网络连接是否正常
4. 服务器日志中是否有异常

---

**状态**：✅ 已完成并测试通过  
**版本**：v1.0  
**更新日期**：2026-01-14  
