# 长江雨课堂视频与图文自动工具

一个用于自动观看长江雨课堂视频与图文（课件）的Python工具，支持批量处理、并发观看、进度跟踪以及自动图文打卡等功能。

## 功能特性

- 🎥 **自动视频观看** - 模拟真实的视频观看行为，发送心跳数据
- 📄 **自动图文浏览** - 自动识别并完成课程中的图文、外部链接等任务打卡
- 📊 **进度跟踪** - 自动获取和更新视频与图文的学习进度
- 🔄 **批量处理** - 自动发现课程中的所有任务节点并批量执行
- ⚡ **并发观看** - 支持多线程并发观看多个视频，提高效率
- 📈 **智能跳过** - 自动跳过已完成的任务
- 🎛️ **可配置参数** - 支持自定义播放速度、阅读停留时间、心跳间隔等参数
- 🐛 **调试模式** - 提供详细的调试信息和日志

## 安装

1. 克隆或下载项目文件
2. 安装依赖包：

```bash
pip install -r requirements.txt
```

## 配置

1. 复制配置文件模板：

```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的实际参数：

### 获取配置参数

#### 1. 获取课堂参数

打开雨课堂课程页面，从URL中提取参数：

```
https://changjiang.yuketang.cn/pro/livecast/12345678?sign=your_sign_here
```

- `CLASSROOM_ID`: 12345678
- `SIGN`: your_sign_here

#### 2. 获取Cookie参数

在浏览器中按 F12 打开开发者工具：

1. 切换到 **Application** 标签页
2. 在左侧选择 **Cookies** → `https://changjiang.yuketang.cn`
3. 找到以下值：
   - `CSRF_TOKEN`: csrftoken 的值
   - `SESSION_ID`: sessionid 的值
   - `UNIVERSITY_ID`: university_id 或 uv_id 的值

#### 3. 配置示例

```env
# 课堂信息
CLASSROOM_ID=12345678
SIGN=your_sign_here
UNIVERSITY_ID=1234

# 用户认证信息
CSRF_TOKEN=your_csrf_token_here
SESSION_ID=your_session_id_here

# 视频观看配置
VIDEO_SPEED=1.5
HEARTBEAT_INTERVAL=5
MAX_CONCURRENT_VIDEOS=3
SKIP_COMPLETED=true
TEST_MODE=false
TEST_VIDEO_COUNT=5

# 图文自动浏览配置
AUTO_RICHTEXT=true
RICHTEXT_STAY_SECONDS=3
RICHTEXT_SKIP_DELAY=1

# 系统配置
USE_CONCURRENT=true
DEBUG=false
```

## 使用方法

配置完成后，直接运行：

```bash
python main.py
```

### 配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `VIDEO_SPEED` | 视频播放速度倍数 | 1.5 |
| `HEARTBEAT_INTERVAL` | 心跳发送间隔（秒） | 5 |
| `MAX_CONCURRENT_VIDEOS` | 最大并发观看视频数 | 3 |
| `AUTO_RICHTEXT` | 是否开启图文自动浏览 | false |
| `RICHTEXT_STAY_SECONDS` | 每篇图文模拟停留时间（秒） | 3 |
| `RICHTEXT_SKIP_DELAY` | 篇间切换的延迟时间（秒） | 1 |
| `SKIP_COMPLETED` | 是否跳过已完成的任务 | true |
| `USE_CONCURRENT` | 是否使用并发模式（仅限视频） | true |
| `TEST_MODE` | 测试模式（只处理前几个视频） | false |
| `TEST_VIDEO_COUNT` | 测试模式下处理的视频数量 | 5 |
| `DEBUG` | 是否显示调试信息 | false |

## 工作原理

1. **课程分析** - 自动深度遍历课程章节结构，识别视频、图文及外部链接。
2. **任务筛选** - 提取所有未完成或需要处理的 leaf 节点。
3. **视频观看模拟** - 发送标准的视频播放事件序列（loadstart, play, playing, videoend 等）及定时心跳。
4. **图文打卡模拟** - 模拟真实的阅读停留，并调用隐藏的 `user_article_finish` 接口进行已读确认。
5. **进度同步** - 实时更新任务状态，支持断点续看，确保学习记录准确上传。

## 注意事项

⚠️ **重要提醒**

- 本工具仅供学习研究使用
- 请遵守学校的相关规定和政策
- 建议合理使用，避免对服务器造成过大压力
- 使用前请确保已经正常登录雨课堂

## 故障排除

### 常见问题

1. **"CLASSROOM ID IS REQUIRED" 错误**
   - 检查 `.env` 文件中的 `CLASSROOM_ID` 是否正确配置

2. **"Objects does not exist" 错误**
   - 检查视频ID是否正确
   - 确认你有权限访问该课程的视频

3. **认证失败**
   - 检查 `CSRF_TOKEN` 和 `SESSION_ID` 是否正确
   - Cookie可能已过期，请重新获取

4. **无法找到视频**
   - 检查 `SIGN` 参数是否正确
   - 确认课程中确实包含视频内容

### 调试模式

开启调试模式查看详细信息：

```env
DEBUG=true
```

## 技术架构

- **主要依赖**: requests, python-dotenv
- **并发处理**: ThreadPoolExecutor
- **会话管理**: requests.Session
- **配置管理**: 环境变量 + .env文件

## 文件结构

```
├── main.py              # 主程序文件
├── requirements.txt     # 依赖包列表
├── .env.example        # 配置文件模板
├── .env               # 实际配置文件（需要创建）
└── README.md          # 使用说明
```

## 许可证

本项目仅供学习和研究使用，请勿用于商业用途。